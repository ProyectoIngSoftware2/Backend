"""Live integration tests against NeonDB (SELECT-only, never a write).

Disabled by default so the suite stays deterministic. Enable explicitly:

    RUN_DB_TESTS=1 .venv/Scripts/python -m pytest -m integration

Every test is read-only: /health endpoints run a "SELECT 1" and the list
endpoints run plain SELECTs against empty tables. No data is written.
"""

import os

import pytest
from fastapi.testclient import TestClient

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DB_TESTS") != "1",
        reason="live database tests disabled (set RUN_DB_TESTS=1 to enable)",
    ),
]


def test_root_app_live_database():
    from app import main as root_main

    with TestClient(root_main.app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["base_de_datos"] == "conectada"


def test_clientes_service_live_database():
    from services.clientes.app import main as clientes_main

    with TestClient(clientes_main.app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["database"] == "connected"


def test_reservas_service_live_database():
    from services.reservas.app import main as reservas_main

    with TestClient(reservas_main.app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["database"] == "connected"


def test_catalogo_service_live_database():
    from services.catalogo.app import main as catalogo_main

    with TestClient(catalogo_main.app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["database"] == "connected"


def test_clientes_service_live_list_readonly(live_login):
    """Live read-only list: a pure SELECT through the real service.

    Requires a valid administrator token: the endpoint is protected
    since Sprint 2 (credentials come from the environment only).
    """
    from services.clientes.app import main as clientes_main

    with TestClient(clientes_main.app) as client:
        token = live_login("admin")["access_token"]
        response = client.get(
            "/api/v1/clientes",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    assert isinstance(response.json()["data"], list)


def test_reservas_service_live_list_readonly(live_login):
    """Live read-only list against the reservation tables (SELECT only)."""
    from services.reservas.app import main as reservas_main

    with TestClient(reservas_main.app) as client:
        token = live_login("admin")["access_token"]
        response = client.get(
            "/api/v1/reservas",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    assert isinstance(response.json()["data"], list)
