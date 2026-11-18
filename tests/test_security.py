"""Unit tests for the canonical shared auth layer (``shared.auth``).

No network and no database: the module is standalone and reads its
settings from the environment / repository ``.env``, so these tests run
with or without a local ``.env`` (conftest injects a test-only
``JWT_SECRET``).

This suite is the adaptation of David Avila's Phase-1 ``shared.security``
tests to the canonical module agreed in the integration:

* ``settings`` (module constant)      -> ``get_auth_settings()`` / ``reset_auth_settings()``;
* ``decode_access_token``             -> ``decode_token`` (raises ``TokenError``);
* ``require_role`` (token -> payload) -> ``require_roles`` (FastAPI dependency);
* ``JWT_EXPIRATION_MINUTES``          -> ``JWT_EXPIRE_MINUTES``;
* claim ``role``                      -> claim ``rol`` (database column).

Every meaningful security assertion of the original suite is preserved
(bcrypt behaviour, forged/tampered/expired token rejection, 401 vs 403
semantics). Two tests are intentionally not carried over, because the
canonical API no longer exposes the behaviour they covered:

* ``test_create_access_token_does_not_mutate_input_data`` — the factory
  takes keyword scalars (``id_usuario``, ``rol``, ``correo``, profile
  ids), not a caller-owned claims dict, so there is no shared structure
  left to mutate;
* ``test_create_access_token_honors_custom_expires_delta`` — token
  lifetime is always ``JWT_EXPIRE_MINUTES`` from settings (no per-token
  override exists anywhere in production code).

The fail-closed configuration rules (secret required and >= 32 chars,
algorithm restricted to HS*) are additionally covered here.
"""

import base64
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient

from shared.auth import (
    ROLE_ADMIN,
    ROLE_CLIENT,
    CurrentUser,
    TokenError,
    create_access_token,
    decode_token,
    get_auth_settings,
    get_current_user,
    hash_password,
    require_roles,
    reset_auth_settings,
    verify_password,
)


@pytest.fixture
def fresh_auth_settings(monkeypatch):
    """Recompute ``shared.auth`` settings from the environment.

    Drops the module cache before and after the test and removes the
    optional variables so their documented defaults are exercised
    deterministically. ``JWT_SECRET`` is left to conftest (test-only
    secret injected via ``setdefault``).
    """
    reset_auth_settings()
    monkeypatch.delenv("JWT_ALGORITHM", raising=False)
    monkeypatch.delenv("JWT_EXPIRE_MINUTES", raising=False)
    yield
    reset_auth_settings()


# ---------------------------------------------------------------------
# Settings: documented defaults + fail-closed configuration
# ---------------------------------------------------------------------


def test_settings_use_documented_defaults(fresh_auth_settings):
    """Defaults apply when the optional env vars are absent."""
    settings = get_auth_settings()
    assert settings.JWT_SECRET  # non-empty (test-only secret from conftest)
    assert settings.JWT_ALGORITHM == "HS256"
    assert settings.JWT_EXPIRE_MINUTES == 60


def test_missing_jwt_secret_fails_closed(fresh_auth_settings, monkeypatch):
    """No secret configured -> configuration error, never a default one."""
    monkeypatch.delenv("JWT_SECRET", raising=False)
    reset_auth_settings()
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        get_auth_settings()


def test_short_jwt_secret_fails_closed(fresh_auth_settings, monkeypatch):
    """A secret below the minimum length is refused (< 32 chars)."""
    monkeypatch.setenv("JWT_SECRET", "too-short-secret")
    reset_auth_settings()
    with pytest.raises(RuntimeError, match="at least 32"):
        get_auth_settings()


def test_empty_jwt_secret_fails_closed(fresh_auth_settings, monkeypatch):
    """An empty secret (e.g. .env.example left untouched) is refused:
    there is no fallback signing secret, ever."""
    monkeypatch.setenv("JWT_SECRET", "")
    reset_auth_settings()
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        get_auth_settings()


def test_whitespace_only_jwt_secret_fails_closed(
    fresh_auth_settings, monkeypatch
):
    """A whitespace-only value carries no entropy: refused as empty."""
    monkeypatch.setenv("JWT_SECRET", " " * 40)
    reset_auth_settings()
    with pytest.raises(RuntimeError, match="empty"):
        get_auth_settings()


def test_documented_placeholder_secret_is_rejected(
    fresh_auth_settings, monkeypatch
):
    """The historical .env.example placeholder is longer than 32 chars
    but publicly documented: it must never be accepted, otherwise
    copying the example would yield a known signing secret."""
    monkeypatch.setenv(
        "JWT_SECRET",
        "REPLACE_WITH_A_LONG_RANDOM_SECRET_AT_LEAST_32_CHARACTERS",
    )
    reset_auth_settings()
    with pytest.raises(RuntimeError, match="placeholder"):
        get_auth_settings()


@pytest.mark.parametrize(
    "placeholder",
    [
        # Any REPLACE_WITH_... template, any case, any length >= 32.
        "REPLACE_WITH_A_NEW_TEMPLATE_0123456789abcdef0123456789ab",
        "replace_with_lowercase_template_0123456789abcdef012345678",
    ],
)
def test_replace_with_template_secrets_are_rejected(
    fresh_auth_settings, monkeypatch, placeholder
):
    monkeypatch.setenv("JWT_SECRET", placeholder)
    reset_auth_settings()
    with pytest.raises(RuntimeError, match="placeholder"):
        get_auth_settings()


def test_env_example_secret_value_is_never_accepted(
    fresh_auth_settings, monkeypatch
):
    """Whatever ships on the ``JWT_SECRET=`` line of .env.example must
    fail validation, so copying the example file can never produce a
    working signing secret (the line is empty by design; a legacy
    placeholder value would also be refused)."""
    example = Path(__file__).resolve().parent.parent / ".env.example"
    values = [
        line.split("=", 1)[1].strip()
        for line in example.read_text(encoding="utf-8").splitlines()
        if line.startswith("JWT_SECRET=")
    ]
    assert len(values) == 1, "expected exactly one JWT_SECRET line"
    monkeypatch.setenv("JWT_SECRET", values[0])
    reset_auth_settings()
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        get_auth_settings()


def test_disallowed_jwt_algorithm_fails_closed(fresh_auth_settings, monkeypatch):
    """Only HS256/HS384/HS512 are accepted (notably not ``none``)."""
    monkeypatch.setenv("JWT_ALGORITHM", "none")
    reset_auth_settings()
    with pytest.raises(RuntimeError, match="JWT_ALGORITHM"):
        get_auth_settings()


@pytest.mark.parametrize("algorithm", ["HS256", "HS384", "HS512"])
def test_documented_algorithms_are_accepted(
    fresh_auth_settings, monkeypatch, algorithm
):
    """Valid configuration contract: exactly the three HMAC
    algorithms are allowed (HS256 is the default)."""
    monkeypatch.setenv("JWT_ALGORITHM", algorithm)
    reset_auth_settings()
    assert get_auth_settings().JWT_ALGORITHM == algorithm


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
        # bcrypt 5.0 refuses >72 bytes outright; the assertion pins the
        # contract so a future version cannot silently truncate instead.
        hash_password("x" * 73)


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


def test_create_access_token_encodes_canonical_claims():
    token = create_access_token(
        id_usuario=42, rol=ROLE_ADMIN, correo="admin@puntoysal.test"
    )
    payload = decode_token(token)
    assert payload["sub"] == "42"
    assert payload["rol"] == ROLE_ADMIN
    assert payload["correo"] == "admin@puntoysal.test"
    assert isinstance(payload["iat"], int)
    assert isinstance(payload["exp"], int)
    assert payload["exp"] > payload["iat"]


def test_create_access_token_carries_only_the_matching_profile_claim():
    admin = decode_token(
        create_access_token(
            id_usuario=1,
            rol=ROLE_ADMIN,
            correo="a@puntoysal.test",
            id_administrador=5,
        )
    )
    assert admin["id_administrador"] == 5
    assert "id_cliente" not in admin

    client = decode_token(
        create_access_token(
            id_usuario=2,
            rol=ROLE_CLIENT,
            correo="c@puntoysal.test",
            id_cliente=9,
        )
    )
    assert client["id_cliente"] == 9
    assert "id_administrador" not in client


def test_create_access_token_default_lifetime_from_settings():
    settings = get_auth_settings()
    token = create_access_token(
        id_usuario=1, rol=ROLE_CLIENT, correo="c@puntoysal.test"
    )
    payload = decode_token(token)
    assert payload["exp"] - payload["iat"] == settings.JWT_EXPIRE_MINUTES * 60


def test_create_access_token_rejects_unknown_role():
    """A role outside the database CHECK can never be minted."""
    with pytest.raises(ValueError, match="Unknown role"):
        create_access_token(
            id_usuario=1, rol="recepcion", correo="x@puntoysal.test"
        )


def test_decode_token_rejects_expired_token():
    settings = get_auth_settings()
    now = datetime.now(timezone.utc)
    expired = jwt.encode(
        {
            "sub": "1",
            "rol": ROLE_ADMIN,
            "iat": int((now - timedelta(minutes=10)).timestamp()),
            "exp": int((now - timedelta(minutes=5)).timestamp()),
        },
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    with pytest.raises(TokenError, match="Token has expired"):
        decode_token(expired)


def test_decode_token_rejects_garbage_token():
    with pytest.raises(TokenError, match="Invalid authentication credentials"):
        decode_token("not-a-jwt-at-all")


def test_decode_token_rejects_token_signed_with_other_secret():
    settings = get_auth_settings()
    now = datetime.now(timezone.utc)
    forged = jwt.encode(
        {
            "sub": "1",
            "rol": ROLE_ADMIN,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
        },
        "some-other-secret",
        algorithm=settings.JWT_ALGORITHM,
    )
    with pytest.raises(TokenError, match="Invalid authentication credentials"):
        decode_token(forged)


def test_decode_token_rejects_tampered_payload():
    """Rewriting the claims without resigning the token is refused."""
    token = create_access_token(
        id_usuario=1, rol=ROLE_CLIENT, correo="c@puntoysal.test"
    )
    head, _payload, tail = token.split(".")
    claims = {
        "sub": "1",
        "rol": ROLE_ADMIN,  # privilege-escalation attempt
        "iat": 1,
        "exp": 9_999_999_999,
    }
    forged_payload = (
        base64.urlsafe_b64encode(json.dumps(claims).encode("utf-8"))
        .rstrip(b"=")
        .decode("ascii")
    )
    forged = f"{head}.{forged_payload}.{tail}"
    with pytest.raises(TokenError, match="Invalid authentication credentials"):
        decode_token(forged)


@pytest.mark.parametrize("omitted", ["exp", "iat"])
def test_decode_token_requires_exp_and_iat(omitted):
    """A signed token missing ``exp`` or ``iat`` can never be accepted.

    PyJWT only validates ``exp`` when the claim is present, so both
    claims are *required*: otherwise a leaked token without expiration
    would live forever.
    """
    settings = get_auth_settings()
    now = datetime.now(timezone.utc)
    claims = {
        "sub": "1",
        "rol": ROLE_ADMIN,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
    }
    del claims[omitted]
    token = jwt.encode(claims, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    with pytest.raises(TokenError):
        decode_token(token)


def test_decode_token_rejects_token_without_rol_claim():
    """A signed token that carries no role claim is not a credential."""
    settings = get_auth_settings()
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": "1",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
        },
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    with pytest.raises(TokenError, match="Invalid authentication credentials"):
        decode_token(token)


def test_decode_token_rejects_unknown_role_claim():
    """A signed token with a role outside the DB CHECK is refused."""
    settings = get_auth_settings()
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": "1",
            "rol": "recepcion",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
        },
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    with pytest.raises(TokenError, match="Invalid authentication credentials"):
        decode_token(token)


# ---------------------------------------------------------------------
# Authentication dependency (get_current_user)
# ---------------------------------------------------------------------


def _bearer(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_get_current_user_returns_identity_from_valid_token():
    token = create_access_token(
        id_usuario=7,
        rol=ROLE_ADMIN,
        correo="a@puntoysal.test",
        id_administrador=3,
    )
    user = get_current_user(_bearer(token))
    assert user.id_usuario == 7
    assert user.rol == ROLE_ADMIN
    assert user.correo == "a@puntoysal.test"
    assert user.id_administrador == 3
    assert user.id_cliente is None


def test_get_current_user_rejects_missing_token():
    with pytest.raises(HTTPException) as exc:
        get_current_user(None)
    assert exc.value.status_code == 401
    assert exc.value.headers.get("WWW-Authenticate") == "Bearer"


def test_get_current_user_rejects_non_bearer_scheme():
    credentials = HTTPAuthorizationCredentials(
        scheme="Basic", credentials="dXNlcjpwYXNz"
    )
    with pytest.raises(HTTPException) as exc:
        get_current_user(credentials)
    assert exc.value.status_code == 401


def test_get_current_user_rejects_invalid_token():
    with pytest.raises(HTTPException) as exc:
        get_current_user(_bearer("garbage-token"))
    assert exc.value.status_code == 401


def test_get_current_user_rejects_expired_token():
    settings = get_auth_settings()
    now = datetime.now(timezone.utc)
    expired = jwt.encode(
        {
            "sub": "1",
            "rol": ROLE_ADMIN,
            "iat": int((now - timedelta(minutes=10)).timestamp()),
            "exp": int((now - timedelta(minutes=5)).timestamp()),
        },
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    with pytest.raises(HTTPException) as exc:
        get_current_user(_bearer(expired))
    assert exc.value.status_code == 401
    assert exc.value.detail == "Token has expired"
    assert exc.value.headers.get("WWW-Authenticate") == "Bearer"


def test_get_current_user_rejects_token_without_rol_claim():
    """Canonical contract: a signed token without a usable role claim is
    an invalid credential -> 401.

    (Phase 1 answered 403 here; the integration deliberately chose the
    stricter 401 so every unusable token is refused uniformly, matching
    the endpoint tests in ``test_auth.py``.)
    """
    settings = get_auth_settings()
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": "9",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
        },
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    with pytest.raises(HTTPException) as exc:
        get_current_user(_bearer(token))
    assert exc.value.status_code == 401


# ---------------------------------------------------------------------
# RBAC dependency (require_roles) through real FastAPI wiring
# ---------------------------------------------------------------------


def _protected_app() -> FastAPI:
    """Minimal app exposing one endpoint restricted to administrators."""
    app = FastAPI()

    @app.get("/protected")
    def protected(user: CurrentUser = Depends(require_roles(ROLE_ADMIN))):
        return {"id_usuario": user.id_usuario, "rol": user.rol}

    return app


PROTECTED_APP = _protected_app()


def test_require_roles_returns_user_for_matching_role():
    token = create_access_token(
        id_usuario=1,
        rol=ROLE_ADMIN,
        correo="a@puntoysal.test",
        id_administrador=1,
    )
    response = TestClient(PROTECTED_APP).get(
        "/protected", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json() == {"id_usuario": 1, "rol": ROLE_ADMIN}


def test_require_roles_rejects_missing_token():
    """No credential -> 401 with the Bearer challenge (never 403)."""
    response = TestClient(PROTECTED_APP).get("/protected")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"
    assert response.headers.get("WWW-Authenticate") == "Bearer"


def test_require_roles_rejects_invalid_token():
    response = TestClient(PROTECTED_APP).get(
        "/protected", headers={"Authorization": "Bearer garbage-token"}
    )
    assert response.status_code == 401
    assert response.headers.get("WWW-Authenticate") == "Bearer"


def test_require_roles_rejects_expired_token():
    settings = get_auth_settings()
    now = datetime.now(timezone.utc)
    expired = jwt.encode(
        {
            "sub": "1",
            "rol": ROLE_ADMIN,
            "iat": int((now - timedelta(minutes=10)).timestamp()),
            "exp": int((now - timedelta(minutes=5)).timestamp()),
        },
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    response = TestClient(PROTECTED_APP).get(
        "/protected", headers={"Authorization": f"Bearer {expired}"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Token has expired"


def test_require_roles_rejects_wrong_role_with_403():
    """A valid *client* token authenticates but is forbidden (403)."""
    token = create_access_token(
        id_usuario=9, rol=ROLE_CLIENT, correo="c@puntoysal.test", id_cliente=9
    )
    response = TestClient(PROTECTED_APP).get(
        "/protected", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"


def test_require_roles_factory_rejects_unknown_role():
    """Config error at wiring time: only DB roles may be requested."""
    with pytest.raises(ValueError, match="Unknown role"):
        require_roles("recepcion")
