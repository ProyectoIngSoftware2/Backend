"""Live authentication/authorization tests (read-only) against NeonDB.

Disabled by default. Enable explicitly with credentials coming ONLY from
the environment (they are never written to any file tracked by Git):

    TEST_ADMIN_CORREO=... TEST_ADMIN_PASSWORD=... \
    TEST_CLIENT_CORREO=... TEST_CLIENT_PASSWORD=... \
    RUN_DB_TESTS=1 pytest -m integration

Read-only guarantee: every operation performed here is a SELECT
(login validates credentials with bcrypt against usuarios; the list and
detail endpoints run plain SELECTs). No row is ever created, updated
or deleted.
"""

import os

import pytest
from fastapi.testclient import TestClient

from services.auth.app import main as auth_main
from services.catalogo.app import main as catalogo_main
from services.clientes.app import main as clientes_main
from services.reservas.app import main as reservas_main

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DB_TESTS") != "1",
        reason="live database tests disabled (set RUN_DB_TESTS=1 to enable)",
    ),
]


@pytest.fixture
def auth_client():
    with TestClient(auth_main.app) as client:
        yield client


@pytest.fixture
def clientes_client():
    with TestClient(clientes_main.app) as client:
        yield client


@pytest.fixture
def reservas_client():
    with TestClient(reservas_main.app) as client:
        yield client


@pytest.fixture
def catalogo_client():
    with TestClient(catalogo_main.app) as client:
        yield client


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Logins (scenarios 1, 2, 3 against the real database)
# ---------------------------------------------------------------------------


def test_live_administrator_login(auth_client, live_credentials):
    """Scenario 1: the administrator account authenticates with role."""
    correo, password = live_credentials("admin")
    response = auth_client.post(
        "/api/v1/auth/login", json={"correo": correo, "password": password}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["rol"] == "administrador"
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["id_administrador"] is not None
    # The token really is a decodable, signed JWT.
    from shared.auth import decode_token

    claims = decode_token(body["access_token"])
    assert claims["rol"] == "administrador"
    assert claims["sub"] == str(body["id_usuario"])


def test_live_client_login(auth_client, live_credentials):
    """Scenario 2: the client account authenticates with role."""
    correo, password = live_credentials("cliente")
    response = auth_client.post(
        "/api/v1/auth/login", json={"correo": correo, "password": password}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["rol"] == "cliente"
    assert body["id_cliente"] is not None
    from shared.auth import decode_token

    claims = decode_token(body["access_token"])
    assert claims["rol"] == "cliente"
    assert claims["id_cliente"] == body["id_cliente"]


def test_live_wrong_password_rejected(auth_client, live_credentials):
    """Scenario 3: correct e-mail + wrong password -> 401 (real DB)."""
    correo, _password = live_credentials("admin")
    response = auth_client.post(
        "/api/v1/auth/login",
        json={"correo": correo, "password": "esta-no-es-la-clave"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"
    assert "access_token" not in response.text


# ---------------------------------------------------------------------------
# Permission matrix against the real database (10, 11, 19, 20)
# ---------------------------------------------------------------------------


def test_live_admin_reads_client_list(clientes_client, live_login):
    """Scenario 11: administrator lists all clients (SELECT only)."""
    token = live_login("admin")["access_token"]
    response = clientes_client.get("/api/v1/clientes", headers=_auth(token))
    assert response.status_code == 200
    assert isinstance(response.json()["data"], list)


def test_live_client_forbidden_on_client_list(clientes_client, live_login):
    """Scenario 10: client token on the admin list -> 403."""
    token = live_login("cliente")["access_token"]
    response = clientes_client.get("/api/v1/clientes", headers=_auth(token))
    assert response.status_code == 403


def test_live_client_list_without_token_401(clientes_client):
    """Scenario 19: no token on a protected endpoint -> 401."""
    response = clientes_client.get("/api/v1/clientes")
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


def test_live_admin_reads_reservation_list(reservas_client, live_login):
    token = live_login("admin")["access_token"]
    response = reservas_client.get("/api/v1/reservas", headers=_auth(token))
    assert response.status_code == 200
    assert isinstance(response.json()["data"], list)


def test_live_client_forbidden_on_reservation_list(reservas_client, live_login):
    """Scenario 10: the reservation list belongs to administrators."""
    token = live_login("cliente")["access_token"]
    response = reservas_client.get("/api/v1/reservas", headers=_auth(token))
    assert response.status_code == 403


def test_live_invalid_token_401(reservas_client):
    response = reservas_client.get(
        "/api/v1/reservas", headers=_auth("token-basura")
    )
    assert response.status_code == 401


def test_live_catalog_reads_public(catalogo_client):
    """Sprint 1 behaviour preserved: catalog reads need no token."""
    mesas = catalogo_client.get("/api/v1/catalogo/mesas")
    platillos = catalogo_client.get("/api/v1/catalogo/platillos")
    assert mesas.status_code == 200
    assert isinstance(mesas.json()["data"], list)
    assert platillos.status_code == 200
    assert isinstance(platillos.json()["data"], list)


def test_live_catalog_write_without_token_401(catalogo_client):
    """A write attempt without credentials is rejected before any data
    access: the handler never runs, so nothing is written (read-only)."""
    response = catalogo_client.post(
        "/api/v1/catalogo/mesas",
        json={"numero_mesa": "NO-DEBE-CREARSE", "capacidad": 1},
    )
    assert response.status_code == 401
