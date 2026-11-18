"""Authentication tests (Sprint 2): login, JWT creation and validation.

No network and no real database: the login endpoint runs against the
fake connection with a genuine bcrypt hash, and every token is built
with the real signing code (test-only secret from the environment).
"""

from datetime import datetime, timedelta, timezone

import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient

from services.auth.app import main as auth_main
from services.reservas.app import main as reservas_main
from shared.auth import (
    ROLE_ADMIN,
    ROLE_CLIENT,
    VALID_ROLES,
    create_access_token,
    decode_token,
    get_auth_settings,
    hash_password,
    reset_auth_settings,
    verify_password,
)

# A password hashed once at import time (cost is paid only once).
PLAIN_PASSWORD = "Correcta2026!"
PASSWORD_HASH = hash_password(PLAIN_PASSWORD)


def _login_row(**overrides):
    """usuarios row (joined with its profile) returned by the fake DB."""
    row = {
        "id_usuario": 10,
        "correo": "admin.prueba@puntoysal.test",
        "password_hash": PASSWORD_HASH,
        "rol": ROLE_ADMIN,
        "activo": True,
        "id_cliente": None,
        "id_administrador": 1,
    }
    row.update(overrides)
    return row


def _post_login(patch_service_db, body):
    patch_service_db(auth_main, one_results=[_login_row()])
    with TestClient(auth_main.app) as client:
        return client.post("/api/v1/auth/login", json=body)


# ---------------------------------------------------------------------------
# Password hashing (bcrypt)
# ---------------------------------------------------------------------------


def test_hash_password_uses_bcrypt_and_never_stores_plaintext():
    digest = hash_password("secreta-una-vez")
    assert digest.startswith(("$2a$", "$2b$", "$2y$"))
    assert "secreta-una-vez" not in digest
    assert verify_password("secreta-una-vez", digest) is True
    assert verify_password("otra-clave", digest) is False


def test_verify_password_rejects_malformed_hash():
    assert verify_password("x", "PLACEHOLDER_SPRINT2_WILL_HASH_THIS") is False
    assert verify_password("x", "") is False
    assert verify_password("", PASSWORD_HASH) is False


def test_verify_password_rejects_passwords_over_72_bytes():
    # bcrypt 5.x raises ValueError on >72 bytes: verify must return False.
    assert verify_password("a" * 80, PASSWORD_HASH) is False


# ---------------------------------------------------------------------------
# Successful logins (1, 2)
# ---------------------------------------------------------------------------


def test_login_administrator_success(patch_service_db):
    """Scenario 1: administrator logs in and receives a valid JWT."""
    response = _post_login(
        patch_service_db,
        {"correo": "admin.prueba@puntoysal.test", "password": PLAIN_PASSWORD},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["rol"] == ROLE_ADMIN
    assert body["expires_in"] == get_auth_settings().JWT_EXPIRE_MINUTES * 60
    assert body["correo"] == "admin.prueba@puntoysal.test"
    assert body["id_usuario"] == 10
    assert body["id_administrador"] == 1

    # The token is genuinely signed and carries the required claims.
    claims = decode_token(body["access_token"])
    assert claims["sub"] == "10"
    assert claims["rol"] == ROLE_ADMIN
    assert claims["correo"] == "admin.prueba@puntoysal.test"
    assert claims["id_administrador"] == 1
    assert claims["exp"] > claims["iat"]


def test_login_client_success(patch_service_db):
    """Scenario 2: client logs in and receives a valid JWT with profile."""
    patch_service_db(
        auth_main,
        one_results=[
            _login_row(
                id_usuario=20,
                correo="cliente.prueba@puntoysal.com",
                rol=ROLE_CLIENT,
                id_cliente=5,
                id_administrador=None,
            )
        ],
    )
    with TestClient(auth_main.app) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={
                "correo": "cliente.prueba@puntoysal.com",
                "password": PLAIN_PASSWORD,
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["rol"] == ROLE_CLIENT
    assert body["id_cliente"] == 5

    claims = decode_token(body["access_token"])
    assert claims["rol"] == ROLE_CLIENT
    assert claims["sub"] == "20"
    assert claims["id_cliente"] == 5
    assert "id_administrador" not in claims


# ---------------------------------------------------------------------------
# Credential failures (3)
# ---------------------------------------------------------------------------


def test_login_incorrect_password_returns_401(patch_service_db):
    """Scenario 3: wrong password -> 401, same message as unknown user."""
    response = _post_login(
        patch_service_db,
        {"correo": "admin.prueba@puntoysal.test", "password": "incorrecta"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"
    assert response.headers.get("www-authenticate") == "Bearer"
    assert "access_token" not in response.text


def test_login_unknown_user_returns_same_401(patch_service_db):
    """Unknown account: identical answer (no account enumeration)."""
    response = _post_login(
        patch_service_db,
        {"correo": "nadie@puntoysal.test", "password": "cualquiera"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


def test_login_disabled_account_returns_uniform_401(patch_service_db):
    """Correct password on a disabled account -> the SAME 401.

    Uniform anti-enumeration contract: unknown user, wrong password and
    disabled account are byte-identical responses, so no probe can tell
    an account exists (or its state).
    """
    patch_service_db(
        auth_main,
        one_results=[_login_row(activo=False)],
    )
    with TestClient(auth_main.app) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={
                "correo": "admin.prueba@puntoysal.test",
                "password": PLAIN_PASSWORD,
            },
        )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"
    assert response.headers.get("www-authenticate") == "Bearer"
    assert "access_token" not in response.text


def test_login_invalid_body_returns_422(patch_service_db):
    """Missing fields, bad e-mail shape or unknown keys are rejected."""
    for body in (
        {"correo": "admin.prueba@puntoysal.test"},
        {"password": "x"},
        {"correo": "sin-arroba", "password": "cualquiera"},
        {"correo": "a@b.com", "password": "x", "rol": ROLE_ADMIN},
    ):
        response = _post_login(patch_service_db, body)
        assert response.status_code == 422, body


def test_login_response_never_contains_password_or_hash(patch_service_db):
    """Neither the plain password nor the bcrypt hash may be exposed."""
    response = _post_login(
        patch_service_db,
        {"correo": "admin.prueba@puntoysal.test", "password": PLAIN_PASSWORD},
    )
    text = response.text
    assert PLAIN_PASSWORD not in text
    assert PASSWORD_HASH not in text
    assert '"password"' not in text


def test_login_database_failure_returns_503(failing_connection):
    """A database outage during login is a controlled 503, not a 500."""
    failing_connection(auth_main)
    with TestClient(auth_main.app) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"correo": "a@b.com", "password": "cualquiera"},
        )
    assert response.status_code == 503


# ---------------------------------------------------------------------------
# Token validation on protected endpoints (4, 5, 6, 7)
# ---------------------------------------------------------------------------


@pytest.fixture
def res_detail_client(patch_service_db):
    """Reservas TestClient whose DB fake always answers 'not found'."""

    def _client():
        patch_service_db(reservas_main, one_results=[None])
        return TestClient(reservas_main.app)

    return _client


def test_missing_token_returns_401(res_detail_client):
    """Scenario 4: no Authorization header -> 401 + Bearer challenge."""
    with res_detail_client() as client:
        response = client.get("/api/v1/reservas/RES-1")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"
    assert response.headers.get("www-authenticate") == "Bearer"


def test_invalid_token_returns_401(res_detail_client):
    """Scenario 5: garbage/malformed token -> 401."""
    with res_detail_client() as client:
        response = client.get(
            "/api/v1/reservas/RES-1",
            headers={"Authorization": "Bearer no.es.un.jwt"},
        )
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


def test_non_bearer_scheme_returns_401(res_detail_client):
    """Only the Bearer scheme is accepted."""
    with res_detail_client() as client:
        response = client.get(
            "/api/v1/reservas/RES-1",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
    assert response.status_code == 401


def test_expired_token_returns_401(res_detail_client):
    """Scenario 6: a correctly signed but expired token -> 401."""
    settings = get_auth_settings()
    now = datetime.now(timezone.utc)
    expired = pyjwt.encode(
        {
            "sub": "10",
            "rol": ROLE_ADMIN,
            "correo": "admin.prueba@puntoysal.test",
            "iat": int((now - timedelta(hours=2)).timestamp()),
            "exp": int((now - timedelta(minutes=5)).timestamp()),
        },
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    with res_detail_client() as client:
        response = client.get(
            "/api/v1/reservas/RES-1",
            headers={"Authorization": f"Bearer {expired}"},
        )
    assert response.status_code == 401
    assert response.json()["detail"] == "Token has expired"


def test_incorrect_signature_returns_401(res_detail_client):
    """Scenario 7: token signed with a different secret -> 401."""
    forged = pyjwt.encode(
        {
            "sub": "10",
            "rol": ROLE_ADMIN,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        "otro-secreto-completamente-diferente-1234567890",
        algorithm="HS256",
    )
    with res_detail_client() as client:
        response = client.get(
            "/api/v1/reservas/RES-1",
            headers={"Authorization": f"Bearer {forged}"},
        )
    assert response.status_code == 401


def test_wrong_algorithm_returns_401(res_detail_client):
    """Same secret but another algorithm: only the configured one counts."""
    settings = get_auth_settings()
    token = pyjwt.encode(
        {
            "sub": "10",
            "rol": ROLE_ADMIN,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        settings.JWT_SECRET,
        algorithm="HS512",
    )
    with res_detail_client() as client:
        response = client.get(
            "/api/v1/reservas/RES-1",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 401


def test_token_with_unknown_role_is_rejected(res_detail_client):
    """A signed token carrying a role outside the DB CHECK is refused."""
    settings = get_auth_settings()
    for rol in ("recepcion", "superadmin", ""):
        token = pyjwt.encode(
            {
                "sub": "10",
                "rol": rol,
                "iat": int(datetime.now(timezone.utc).timestamp()),
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            },
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM,
        )
        with res_detail_client() as client:
            response = client.get(
                "/api/v1/reservas/RES-1",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 401, rol


def test_token_with_non_numeric_sub_is_rejected(res_detail_client):
    """A signed token with an unusable identity is refused."""
    settings = get_auth_settings()
    token = pyjwt.encode(
        {
            "sub": "not-a-number",
            "rol": ROLE_ADMIN,
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    with res_detail_client() as client:
        response = client.get(
            "/api/v1/reservas/RES-1",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 401


def test_token_without_exp_is_rejected(res_detail_client):
    """A correctly signed token with no expiration can never be used.

    PyJWT only validates ``exp`` when it is present, so the claim must
    be *required*: otherwise a token without expiration would live
    forever.
    """
    settings = get_auth_settings()
    token = pyjwt.encode(
        {
            "sub": "10",
            "rol": ROLE_ADMIN,
            "iat": int(datetime.now(timezone.utc).timestamp()),
        },
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    with res_detail_client() as client:
        response = client.get(
            "/api/v1/reservas/RES-1",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 401
    assert "access_token" not in response.text


def test_token_without_iat_is_rejected(res_detail_client):
    """A correctly signed token without issued-at is refused too."""
    settings = get_auth_settings()
    token = pyjwt.encode(
        {
            "sub": "10",
            "rol": ROLE_ADMIN,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    with res_detail_client() as client:
        response = client.get(
            "/api/v1/reservas/RES-1",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 401


def test_protected_endpoint_never_reached_without_token(patch_service_db):
    """Without a token the database is not queried at all."""
    patch_service_db(reservas_main, one_results=[None])
    with TestClient(reservas_main.app) as client:
        response = client.get("/api/v1/reservas/RES-1")
    assert response.status_code == 401
    assert patch_service_db.last_connection.executed == [], (
        "no SQL must run before authentication"
    )


# ---------------------------------------------------------------------------
# Token/secret configuration rules
# ---------------------------------------------------------------------------


@pytest.fixture
def fresh_auth_settings():
    """Reset the cached auth settings before and after each test."""
    reset_auth_settings()
    yield
    reset_auth_settings()


def test_create_access_token_rejects_unknown_role(fresh_auth_settings):
    with pytest.raises(ValueError):
        create_access_token(id_usuario=1, rol="recepcion", correo="a@b.com")


def test_decode_token_rejects_malformed(fresh_auth_settings):
    from shared.auth import TokenError

    with pytest.raises(TokenError):
        decode_token("basura")


def test_short_jwt_secret_fails_closed(fresh_auth_settings, monkeypatch):
    """A weak/short JWT_SECRET is refused: no default secret, ever."""
    monkeypatch.setenv("JWT_SECRET", "corto")
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        get_auth_settings()


def test_disallowed_algorithm_fails_closed(fresh_auth_settings, monkeypatch):
    """`none`/unknown algorithms are refused at configuration time."""
    monkeypatch.setenv(
        "JWT_SECRET", "pys-unit-tests-only-secret-do-not-use-0123456789"
    )
    monkeypatch.setenv("JWT_ALGORITHM", "none")
    with pytest.raises(RuntimeError, match="JWT_ALGORITHM"):
        get_auth_settings()


def test_default_algorithm_is_hs256(fresh_auth_settings):
    assert get_auth_settings().JWT_ALGORITHM == "HS256"
    assert get_auth_settings().JWT_EXPIRE_MINUTES >= 1


def test_valid_roles_match_database_check():
    """The API exposes exactly the two roles of usuarios_rol_check."""
    assert set(VALID_ROLES) == {ROLE_ADMIN, ROLE_CLIENT}
