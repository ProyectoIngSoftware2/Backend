"""Unit tests for the shared security layer (Phase 1).

No network and no database: ``shared.security`` is standalone and uses
fallback settings, so these tests run with or without a local ``.env``.
"""

from datetime import timedelta

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from shared.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    require_role,
    settings,
    verify_password,
)

# ---------------------------------------------------------------------
# Settings fallbacks
# ---------------------------------------------------------------------


def test_settings_have_fallback_values():
    """Missing env vars must not break the module: defaults apply."""
    assert settings.JWT_SECRET  # non-empty
    assert settings.JWT_ALGORITHM == "HS256"
    assert settings.JWT_EXPIRATION_MINUTES == 60


# ---------------------------------------------------------------------
# Password hashing / verification
# ---------------------------------------------------------------------


def test_hash_password_returns_bcrypt_hash():
    hashed = hash_password("S3cret!Password")
    assert isinstance(hashed, str)
    assert hashed.startswith("$2")
    assert "S3cret!Password" not in hashed


def test_hash_password_uses_a_fresh_salt_each_time():
    assert hash_password("same-password") != hash_password("same-password")


def test_hash_password_rejects_empty_and_oversized_input():
    with pytest.raises(ValueError):
        hash_password("")
    with pytest.raises(ValueError):
        hash_password("x" * 73)  # bcrypt truncates at 72 bytes


def test_verify_password_accepts_correct_password():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed) is True


def test_verify_password_rejects_wrong_password():
    hashed = hash_password("correct-password")
    assert verify_password("wrong-password", hashed) is False
    assert verify_password("", hashed) is False


def test_verify_password_never_raises_on_malformed_hash():
    assert verify_password("anything", "not-a-bcrypt-hash") is False
    assert verify_password("anything", "") is False
    assert verify_password("anything", None) is False  # type: ignore[arg-type]


# ---------------------------------------------------------------------
# Token creation / decoding
# ---------------------------------------------------------------------


def test_create_access_token_encodes_data():
    token = create_access_token({"sub": "42", "role": "admin"})
    payload = decode_access_token(token)
    assert payload["sub"] == "42"
    assert payload["role"] == "admin"
    assert "exp" in payload
    assert "iat" in payload


def test_create_access_token_does_not_mutate_input_data():
    data = {"sub": "7", "role": "staff"}
    create_access_token(data)
    assert data == {"sub": "7", "role": "staff"}


def test_create_access_token_default_expiration_from_settings():
    token = create_access_token({"sub": "1"})
    payload = decode_access_token(token)
    lifetime = payload["exp"] - payload["iat"]
    assert lifetime == settings.JWT_EXPIRATION_MINUTES * 60


def test_create_access_token_honors_custom_expires_delta():
    token = create_access_token(
        {"sub": "1"}, expires_delta=timedelta(minutes=5)
    )
    payload = decode_access_token(token)
    assert payload["exp"] - payload["iat"] == 5 * 60


def test_decode_access_token_rejects_expired_token():
    expired = create_access_token(
        {"sub": "1"}, expires_delta=timedelta(seconds=-10)
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(expired)


def test_decode_access_token_rejects_garbage_token():
    with pytest.raises(jwt.PyJWTError):
        decode_access_token("not-a-jwt-at-all")


def test_decode_access_token_rejects_token_signed_with_other_secret():
    forged = jwt.encode(
        {"sub": "1", "role": "admin"},
        "some-other-secret",
        algorithm=settings.JWT_ALGORITHM,
    )
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(forged)


def test_decode_access_token_rejects_tampered_payload():
    token = create_access_token({"sub": "1", "role": "guest"})
    head, tail = token.split(".", 1)
    forged = head + "." + "eyJyb2xlIjoiYWRtaW4ifQ" + "." + tail.split(".")[-1]
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(forged)


# ---------------------------------------------------------------------
# RBAC dependency (require_role)
# ---------------------------------------------------------------------


def _bearer(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_require_role_returns_payload_for_matching_role():
    dependency = require_role("admin")
    token = create_access_token({"sub": "1", "role": "admin"})
    payload = dependency(_bearer(token))
    assert payload["sub"] == "1"
    assert payload["role"] == "admin"


def test_require_role_rejects_missing_token():
    dependency = require_role("admin")
    with pytest.raises(HTTPException) as exc:
        dependency(None)
    assert exc.value.status_code == 401


def test_require_role_rejects_invalid_token():
    dependency = require_role("admin")
    with pytest.raises(HTTPException) as exc:
        dependency(_bearer("garbage-token"))
    assert exc.value.status_code == 401


def test_require_role_rejects_expired_token():
    dependency = require_role("admin")
    expired = create_access_token(
        {"role": "admin"}, expires_delta=timedelta(seconds=-10)
    )
    with pytest.raises(HTTPException) as exc:
        dependency(_bearer(expired))
    assert exc.value.status_code == 401
    assert exc.value.detail == "Token has expired"


def test_require_role_rejects_wrong_role_with_403():
    dependency = require_role("admin")
    token = create_access_token({"sub": "9", "role": "staff"})
    with pytest.raises(HTTPException) as exc:
        dependency(_bearer(token))
    assert exc.value.status_code == 403


def test_require_role_rejects_token_without_role_claim():
    dependency = require_role("admin")
    token = create_access_token({"sub": "9"})
    with pytest.raises(HTTPException) as exc:
        dependency(_bearer(token))
    assert exc.value.status_code == 403
