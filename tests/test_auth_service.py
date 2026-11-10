"""Unit tests for the auth microservice (faked database, no network).

Covers the full login contract: success (signed JWT with the canonical
claims including the profile id), uniform 401 ``Invalid credentials``
for unknown user / wrong password / inactive account (with an identical
detail so accounts cannot be enumerated), 503 when the database is
down, 500 for unexpected errors, and 422 for malformed bodies.
"""

from fastapi.testclient import TestClient

import bcrypt

from services.auth.app import main as auth_main
from shared.auth import decode_token, hash_password

# Generated once at import: a real bcrypt hash for a fake test password
# (the tests never touch the database, so this never leaves the process).
VALID_PASSWORD = "correct-password"
VALID_HASH = hash_password(VALID_PASSWORD)

CORREO = "admin.prueba@puntoysal.test"


def _admin_row(**overrides):
    row = {
        "id_usuario": 1,
        "correo": CORREO,
        "password_hash": VALID_HASH,
        "rol": "administrador",
        "activo": True,
        # Profile-link columns of the login query (LEFT JOINs).
        "id_cliente": None,
        "id_administrador": 1,
    }
    row.update(overrides)
    return row


def test_login_success_returns_signed_jwt(patch_service_db):
    patch_service_db(auth_main, one_results=[_admin_row()])
    with TestClient(auth_main.app) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"correo": CORREO, "password": VALID_PASSWORD},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["rol"] == "administrador"
    assert body["expires_in"] > 0
    assert body["correo"] == CORREO
    assert body["id_usuario"] == 1
    assert body["id_cliente"] is None
    assert body["id_administrador"] == 1

    # The token is valid under the shared auth layer and carries the
    # canonical claims (identity, role, profile id, iat/exp).
    payload = decode_token(body["access_token"])
    assert payload["sub"] == "1"
    assert payload["rol"] == "administrador"
    assert payload["correo"] == CORREO
    assert payload["id_administrador"] == 1
    assert "id_cliente" not in payload
    assert payload["exp"] > payload["iat"]

    # No credential material leaks in the response.
    assert VALID_PASSWORD not in response.text
    assert VALID_HASH not in response.text

    # The correo was sent as a bound parameter (never string-interpolated).
    _query, params = patch_service_db.last_connection.executed[0]
    assert params == (CORREO,)


def test_login_wrong_password_returns_401(patch_service_db):
    patch_service_db(auth_main, one_results=[_admin_row()])
    with TestClient(auth_main.app) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"correo": CORREO, "password": "wrong-password"},
        )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


def test_login_unknown_correo_returns_same_401(patch_service_db):
    """Unknown account must be indistinguishable from a wrong password."""
    patch_service_db(auth_main, one_results=[None])
    with TestClient(auth_main.app) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"correo": "nadie@puntoysal.test", "password": VALID_PASSWORD},
        )
    assert response.status_code == 401
    # Identical detail to the wrong-password case: no user enumeration.
    assert response.json()["detail"] == "Invalid credentials"


def test_login_inactive_account_returns_401(patch_service_db):
    patch_service_db(auth_main, one_results=[_admin_row(activo=False)])
    with TestClient(auth_main.app) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"correo": CORREO, "password": VALID_PASSWORD},
        )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


def test_login_returns_503_when_database_unreachable(failing_connection):
    failing_connection(auth_main)
    with TestClient(auth_main.app) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"correo": CORREO, "password": VALID_PASSWORD},
        )
    assert response.status_code == 503
    assert response.json()["detail"] == "Database connection failed"


def test_login_returns_500_on_unexpected_error(unexpected_failure):
    unexpected_failure(auth_main)
    with TestClient(auth_main.app) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"correo": CORREO, "password": VALID_PASSWORD},
        )
    assert response.status_code == 500
    assert response.json()["detail"] == "Internal server error"
    # No internals leak to the caller.
    assert "Traceback" not in response.text


def test_login_missing_fields_returns_422(patch_service_db):
    patch_service_db(auth_main, one_results=[_admin_row()])
    with TestClient(auth_main.app) as client:
        response = client.post("/api/v1/auth/login", json={})
    assert response.status_code == 422
    # Validation fails before any database access happens.
    assert patch_service_db.last_connection.executed == []


def test_health_ok(patch_service_db):
    patch_service_db(auth_main, healthy=True)
    with TestClient(auth_main.app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "service": "auth",
        "status": "ok",
        "database": "connected",
    }


def test_health_returns_503_without_database(patch_service_db):
    patch_service_db(auth_main, healthy=False)
    with TestClient(auth_main.app) as client:
        response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["detail"] == "Database connection failed"


# ---------------------------------------------------------------------
# Timing-side-channel mitigation (login hardening)
#
# Every login attempt must perform exactly one bcrypt verification —
# unknown e-mails against a module-level dummy hash, existing accounts
# (active or not) against their real hash — so the response time does
# not reveal whether an account exists. This is a mitigation of a
# timing side channel, NOT a claim of mathematically constant-time
# behaviour, and the response contract is unchanged.
# ---------------------------------------------------------------------


def _spy_verify(monkeypatch):
    """Record every ``password_hash`` the service verifies against."""
    calls = []
    real_verify = auth_main.verify_password

    def spy(password, password_hash):
        calls.append(password_hash)
        return real_verify(password, password_hash)

    monkeypatch.setattr(auth_main, "verify_password", spy)
    return calls


def test_unknown_correo_still_performs_one_bcrypt_check(
    patch_service_db, monkeypatch
):
    """Unknown e-mail: one bcrypt verification against the dummy hash
    (timing equalization) and the uniform 401."""
    calls = _spy_verify(monkeypatch)
    patch_service_db(auth_main, one_results=[None])
    with TestClient(auth_main.app) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={
                "correo": "nadie@puntoysal.test",
                "password": VALID_PASSWORD,
            },
        )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"
    assert len(calls) == 1
    assert calls[0] == auth_main._DUMMY_PASSWORD_HASH


def test_dummy_hash_is_valid_and_never_regenerated_per_request(
    patch_service_db, monkeypatch
):
    """The dummy hash is a well-formed bcrypt hash and a module-level
    constant generated once at import — two requests verify against
    the identical object (no per-request gensalt)."""
    calls = _spy_verify(monkeypatch)
    patch_service_db(auth_main, one_results=[None])
    with TestClient(auth_main.app) as client:
        for _ in range(2):
            client.post(
                "/api/v1/auth/login",
                json={"correo": "nadie@puntoysal.test", "password": "x"},
            )
    assert len(calls) == 2
    assert calls[0] is calls[1] is auth_main._DUMMY_PASSWORD_HASH
    dummy = auth_main._DUMMY_PASSWORD_HASH
    assert dummy.startswith("$2")
    # Well-formed bcrypt hash: checkpw only raises on malformed input.
    bcrypt.checkpw(b"probe", dummy.encode("utf-8"))


def test_inactive_account_verifies_against_real_hash_then_401(
    patch_service_db, monkeypatch
):
    """Inactive accounts undergo password verification (their real
    hash) before the uniform 401 — even with the correct password."""
    calls = _spy_verify(monkeypatch)
    patch_service_db(auth_main, one_results=[_admin_row(activo=False)])
    with TestClient(auth_main.app) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"correo": CORREO, "password": VALID_PASSWORD},
        )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"
    assert len(calls) == 1
    assert calls[0] == VALID_HASH  # the account's real hash


def test_all_failure_modes_return_identical_responses(patch_service_db):
    """Unknown e-mail, wrong password and inactive account are
    byte-for-byte indistinguishable (anti-enumeration contract):
    same status, same detail, same Bearer challenge."""
    attempts = [
        (None, VALID_PASSWORD),  # unknown e-mail
        (_admin_row(), "wrong-password"),  # wrong password
        (_admin_row(activo=False), VALID_PASSWORD),  # inactive, correct pwd
    ]
    seen = []
    for row, password in attempts:
        patch_service_db(auth_main, one_results=[row])
        with TestClient(auth_main.app) as client:
            response = client.post(
                "/api/v1/auth/login",
                json={"correo": CORREO, "password": password},
            )
        seen.append(
            (
                response.status_code,
                response.json().get("detail"),
                response.headers.get("WWW-Authenticate"),
            )
        )
    assert len(set(seen)) == 1, f"responses differ: {seen}"
    assert seen[0] == (401, "Invalid credentials", "Bearer")
