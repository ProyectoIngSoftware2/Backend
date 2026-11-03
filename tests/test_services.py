"""Unit tests for the three microservices (no network, no real database)."""

import logging

import httpx
from fastapi.testclient import TestClient

from services.catalogo.app import main as catalogo_main
from services.clientes.app import main as clientes_main
from services.reservas.app import main as reservas_main

SERVICE_MODULES = [
    (clientes_main, "clientes"),
    (reservas_main, "reservas"),
    (catalogo_main, "catalogo"),
]


def catalogo_client_returning(names_by_id):
    """Build a catalogo HTTP client (mock transport) with canned dish names."""

    def handler(request: httpx.Request) -> httpx.Response:
        dish_id = int(request.url.path.rsplit("/", 1)[-1])
        if dish_id in names_by_id:
            return httpx.Response(
                200, json={"data": {"id_platillo": dish_id, "nombre": names_by_id[dish_id]}}
            )
        return httpx.Response(404, json={"detail": "Dish not found"})

    return httpx.Client(transport=httpx.MockTransport(handler), timeout=5.0)


def test_health_ok(patch_service_db):
    """Each service answers 200 on /health when the database responds."""
    for module, name in SERVICE_MODULES:
        patch_service_db(module, healthy=True)
        with TestClient(module.app) as client:
            response = client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body == {"service": name, "status": "ok", "database": "connected"}


def test_health_returns_503_without_database(patch_service_db):
    """Each service answers 503 on /health when the database is down."""
    for module, _name in SERVICE_MODULES:
        patch_service_db(module, healthy=False)
        with TestClient(module.app) as client:
            response = client.get("/health")
        assert response.status_code == 503
        assert response.json()["detail"] == "Database connection failed"


def test_openapi_available(patch_service_db):
    """Each service exposes its own OpenAPI (Swagger) documentation."""
    for module, _name in SERVICE_MODULES:
        patch_service_db(module, healthy=True)
        with TestClient(module.app) as client:
            response = client.get("/openapi.json")
        assert response.status_code == 200
        assert "/health" in response.json()["paths"]


def test_clientes_list_empty(patch_service_db):
    """GET /api/v1/clientes returns an empty data list on an empty table."""
    patch_service_db(clientes_main, all_results=[[]])
    with TestClient(clientes_main.app) as client:
        response = client.get("/api/v1/clientes")
    assert response.status_code == 200
    assert response.json() == {"data": []}


def test_clientes_detail_not_found(patch_service_db):
    """GET /api/v1/clientes/{id} returns 404 for an unknown customer."""
    patch_service_db(clientes_main, one_results=[None])
    with TestClient(clientes_main.app) as client:
        response = client.get("/api/v1/clientes/999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Customer not found"


def test_clientes_detail_found(patch_service_db):
    """GET /api/v1/clientes/{id} returns the customer row."""
    fake_row = {
        "id_cliente": 1,
        "nombre_completo": "Ana Lopez",
        "numero_identidad": "0801199000123",
        "telefono": "+504 9999-0001",
        "correo": "ana.lopez@example.com",
        "fecha_registro": "2026-11-01T12:00:00-06:00",
        "activo": True,
    }
    patch_service_db(clientes_main, one_results=[fake_row])
    with TestClient(clientes_main.app) as client:
        response = client.get("/api/v1/clientes/1")
    assert response.status_code == 200
    assert response.json() == {"data": fake_row}


def test_clientes_list_database_error_returns_503(failing_connection):
    """A psycopg connection failure on a data endpoint returns 503."""
    failing_connection(clientes_main)
    with TestClient(clientes_main.app) as client:
        response = client.get("/api/v1/clientes")
    assert response.status_code == 503
    assert response.json()["detail"] == "Database connection failed"


def test_clientes_unexpected_error_returns_500(unexpected_failure):
    """A non-database bug is a generic 500, not a fake 'database down'."""
    unexpected_failure(clientes_main)
    with TestClient(clientes_main.app) as client:
        response = client.get("/api/v1/clientes")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    # No internals leak to the client.
    assert "Traceback" not in response.text
    assert "SELECT" not in response.text
    assert "RuntimeError" not in response.text


def test_unexpected_error_is_logged_with_traceback(unexpected_failure, caplog):
    """F-02: unexpected errors are logged via logging.exception."""
    unexpected_failure(clientes_main)
    with caplog.at_level(logging.ERROR, logger=clientes_main.__name__):
        with TestClient(clientes_main.app) as client:
            response = client.get("/api/v1/clientes")
    assert response.status_code == 500
    logged = [r for r in caplog.records if r.exc_info is not None]
    assert logged, "expected an exception with traceback to be logged"
    assert any(
        "Unexpected error while listing customers" in r.getMessage()
        for r in logged
    )


def test_reservas_list_empty(patch_service_db):
    patch_service_db(reservas_main, all_results=[[]])
    with TestClient(reservas_main.app) as client:
        response = client.get("/api/v1/reservas")
    assert response.status_code == 200
    assert response.json() == {"data": []}


def test_reservas_detail_not_found(patch_service_db):
    """Unknown reservation code returns 404 (and not a 503)."""
    patch_service_db(reservas_main, one_results=[None])
    with TestClient(reservas_main.app) as client:
        response = client.get("/api/v1/reservas/NO-EXISTE")
    assert response.status_code == 404
    assert response.json()["detail"] == "Reservation not found"


def test_reservas_detail_includes_dishes_and_history(patch_service_db, monkeypatch):
    """Reservation detail merges own-table rows with names from catalogo (F-01)."""
    reservation = {
        "id_reserva": 1,
        "codigo_reserva": "RES-TEST-0001",
        "id_cliente": 1,
        "id_mesa": 1,
        "fecha_hora_inicio": "2027-03-15T19:00:00-06:00",
        "duracion_minutos": 120,
        "cantidad_personas": 2,
        "estado": "pendiente",
        "observaciones": "test",
        "fecha_creacion": "2026-11-01T12:00:00-06:00",
        "fecha_actualizacion": "2026-11-01T12:00:00-06:00",
        "id_administrador": None,
    }
    # reserva_platillos rows (reservas' own table) carry no dish name.
    dish_rows = [
        {
            "id_platillo": 1,
            "cantidad": 2,
            "precio_unitario": "180.00",
            "observaciones": None,
        }
    ]
    history = [
        {
            "id_historial": 1,
            "estado_anterior": None,
            "estado_nuevo": "pendiente",
            "id_administrador": None,
            "comentario": None,
            "fecha_cambio": "2026-11-01T12:00:00-06:00",
        }
    ]
    patch_service_db(
        reservas_main,
        one_results=[reservation],
        all_results=[dish_rows, history],
    )
    monkeypatch.setattr(
        reservas_main,
        "_catalogo_client",
        lambda: catalogo_client_returning({1: "Filete de pescado a la plancha"}),
    )
    with TestClient(reservas_main.app) as client:
        response = client.get("/api/v1/reservas/RES-TEST-0001")
    assert response.status_code == 200
    body = response.json()
    assert body["data"] == reservation
    # Response contract preserved: same keys as the original JOIN query.
    assert body["platillos"] == [
        {
            "id_platillo": 1,
            "nombre": "Filete de pescado a la plancha",
            "cantidad": 2,
            "precio_unitario": "180.00",
            "observaciones": None,
        }
    ]
    assert body["historial"] == history


def test_reservas_detail_never_queries_platillos_table(patch_service_db, monkeypatch):
    """F-01: the reservations service executes SQL only on its own tables."""
    reservation = {
        "id_reserva": 7,
        "codigo_reserva": "RES-OWN-TABLES",
        "id_cliente": 1,
        "id_mesa": None,
        "fecha_hora_inicio": "2027-04-01T19:00:00-06:00",
        "duracion_minutos": 60,
        "cantidad_personas": 2,
        "estado": "pendiente",
        "observaciones": None,
        "fecha_creacion": "2026-11-02T12:00:00-06:00",
        "fecha_actualizacion": "2026-11-02T12:00:00-06:00",
        "id_administrador": None,
    }
    patch_service_db(
        reservas_main,
        one_results=[reservation],
        all_results=[
            [{"id_platillo": 9, "cantidad": 1, "precio_unitario": "45.00", "observaciones": None}],
            [],
        ],
    )
    monkeypatch.setattr(
        reservas_main,
        "_catalogo_client",
        lambda: catalogo_client_returning({9: "Baleada tradicional"}),
    )
    with TestClient(reservas_main.app) as client:
        response = client.get("/api/v1/reservas/RES-OWN-TABLES")
    assert response.status_code == 200

    executed = patch_service_db.last_connection.executed
    assert executed, "expected SQL to have been executed"
    for query, _params in executed:
        assert "JOIN platillos" not in query
        assert "FROM platillos" not in query
    # The name came over HTTP from catalogo instead.
    assert response.json()["platillos"][0]["nombre"] == "Baleada tradicional"


def test_reservas_detail_catalogo_unavailable_returns_503(patch_service_db, monkeypatch):
    """F-01: an unreachable catalogo produces a controlled 503, not a 500."""
    reservation = {
        "id_reserva": 1,
        "codigo_reserva": "RES-TEST-0001",
        "id_cliente": 1,
        "id_mesa": 1,
        "fecha_hora_inicio": "2027-03-15T19:00:00-06:00",
        "duracion_minutos": 120,
        "cantidad_personas": 2,
        "estado": "pendiente",
        "observaciones": "test",
        "fecha_creacion": "2026-11-01T12:00:00-06:00",
        "fecha_actualizacion": "2026-11-01T12:00:00-06:00",
        "id_administrador": None,
    }
    patch_service_db(
        reservas_main,
        one_results=[reservation],
        all_results=[[{"id_platillo": 1, "cantidad": 1, "precio_unitario": "45.00", "observaciones": None}], []],
    )

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused (simulated)", request=request)

    monkeypatch.setattr(
        reservas_main,
        "_catalogo_client",
        lambda: httpx.Client(transport=httpx.MockTransport(handler), timeout=5.0),
    )
    with TestClient(reservas_main.app) as client:
        response = client.get("/api/v1/reservas/RES-TEST-0001")
    assert response.status_code == 503
    assert response.json() == {"detail": "Catalogo service is unavailable"}
    # The internal catalogo URL must never leak.
    assert "localhost" not in response.text
    assert "8003" not in response.text


def test_reservas_detail_catalogo_timeout_returns_504(patch_service_db, monkeypatch):
    """F-01: a slow catalogo produces a controlled 504."""
    reservation = {
        "id_reserva": 1,
        "codigo_reserva": "RES-TEST-0001",
        "id_cliente": 1,
        "id_mesa": 1,
        "fecha_hora_inicio": "2027-03-15T19:00:00-06:00",
        "duracion_minutos": 120,
        "cantidad_personas": 2,
        "estado": "pendiente",
        "observaciones": "test",
        "fecha_creacion": "2026-11-01T12:00:00-06:00",
        "fecha_actualizacion": "2026-11-01T12:00:00-06:00",
        "id_administrador": None,
    }
    patch_service_db(
        reservas_main,
        one_results=[reservation],
        all_results=[[{"id_platillo": 1, "cantidad": 1, "precio_unitario": "45.00", "observaciones": None}], []],
    )

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out (simulated)", request=request)

    monkeypatch.setattr(
        reservas_main,
        "_catalogo_client",
        lambda: httpx.Client(transport=httpx.MockTransport(handler), timeout=5.0),
    )
    with TestClient(reservas_main.app) as client:
        response = client.get("/api/v1/reservas/RES-TEST-0001")
    assert response.status_code == 504
    assert response.json() == {"detail": "Catalogo service did not respond in time"}


def test_reservas_detail_without_dishes_never_calls_catalogo(patch_service_db, monkeypatch):
    """No dishes -> no cross-service call (catalogo can be down)."""
    reservation = {
        "id_reserva": 2,
        "codigo_reserva": "RES-NO-DISHES",
        "id_cliente": 1,
        "id_mesa": None,
        "fecha_hora_inicio": "2027-04-02T19:00:00-06:00",
        "duracion_minutos": 60,
        "cantidad_personas": 2,
        "estado": "pendiente",
        "observaciones": None,
        "fecha_creacion": "2026-11-02T12:00:00-06:00",
        "fecha_actualizacion": "2026-11-02T12:00:00-06:00",
        "id_administrador": None,
    }
    patch_service_db(reservas_main, one_results=[reservation], all_results=[[], []])

    def forbidden_call():
        raise AssertionError("catalogo must not be called when there are no dishes")

    monkeypatch.setattr(reservas_main, "_catalogo_client", forbidden_call)
    with TestClient(reservas_main.app) as client:
        response = client.get("/api/v1/reservas/RES-NO-DISHES")
    assert response.status_code == 200
    assert response.json()["platillos"] == []


def test_catalogo_mesas_list_empty(patch_service_db):
    patch_service_db(catalogo_main, all_results=[[]])
    with TestClient(catalogo_main.app) as client:
        response = client.get("/api/v1/catalogo/mesas")
    assert response.status_code == 200
    assert response.json() == {"data": []}


def test_catalogo_platillos_list_empty(patch_service_db):
    patch_service_db(catalogo_main, all_results=[[]])
    with TestClient(catalogo_main.app) as client:
        response = client.get("/api/v1/catalogo/platillos")
    assert response.status_code == 200
    assert response.json() == {"data": []}


def test_catalogo_mesa_not_found(patch_service_db):
    patch_service_db(catalogo_main, one_results=[None])
    with TestClient(catalogo_main.app) as client:
        response = client.get("/api/v1/catalogo/mesas/999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Table not found"


def test_catalogo_platillo_not_found(patch_service_db):
    patch_service_db(catalogo_main, one_results=[None])
    with TestClient(catalogo_main.app) as client:
        response = client.get("/api/v1/catalogo/platillos/999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Dish not found"
