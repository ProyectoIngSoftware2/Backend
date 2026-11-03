"""F-07: SQL values must be passed as separate parameters, never interpolated.

These tests record the exact (query, params) pairs the services send to the
driver and assert that user-controlled values appear only in the parameter
tuple, never inside the SQL text.
"""

from fastapi.testclient import TestClient

from services.catalogo.app import main as catalogo_main
from services.clientes.app import main as clientes_main
from services.reservas.app import main as reservas_main


def test_clientes_detail_passes_id_as_parameter(patch_service_db):
    """GET /api/v1/clientes/{id} binds the id with %s, not string building."""
    fake_row = {"id_cliente": 12345, "nombre_completo": "Ana Lopez"}
    patch_service_db(clientes_main, one_results=[fake_row])
    with TestClient(clientes_main.app) as client:
        response = client.get("/api/v1/clientes/12345")
    assert response.status_code == 200

    query, params = patch_service_db.last_connection.executed[0]
    assert "%s" in query, "expected a placeholder instead of an inlined value"
    assert "12345" not in query, "the id must not appear in the SQL text"
    assert params == (12345,), "the id must be passed as a separate parameter"


def test_reservas_detail_passes_codigo_as_parameter(patch_service_db):
    """GET /api/v1/reservas/{codigo} binds the code in every query."""
    reservation = {
        "id_reserva": 5,
        "codigo_reserva": "ABC-777-ZZZ",
        "id_cliente": 1,
        "id_mesa": None,
        "fecha_hora_inicio": "2027-05-01T19:00:00-06:00",
        "duracion_minutos": 60,
        "cantidad_personas": 2,
        "estado": "pendiente",
        "observaciones": None,
        "fecha_creacion": "2026-11-02T12:00:00-06:00",
        "fecha_actualizacion": "2026-11-02T12:00:00-06:00",
        "id_administrador": None,
    }
    # No dishes -> no catalogo call; history empty.
    patch_service_db(reservas_main, one_results=[reservation], all_results=[[], []])
    with TestClient(reservas_main.app) as client:
        response = client.get("/api/v1/reservas/ABC-777-ZZZ")
    assert response.status_code == 200

    executed = patch_service_db.last_connection.executed
    assert len(executed) == 3, "expected the three read-only queries"
    for query, params in executed:
        assert "%s" in query, "expected a placeholder instead of an inlined value"
        assert "ABC-777-ZZZ" not in query, "the code must not appear in SQL text"
        assert isinstance(params, tuple)
    assert executed[0][1] == ("ABC-777-ZZZ",)


def test_catalogo_detail_passes_id_as_parameter(patch_service_db):
    """GET /api/v1/catalogo/platillos/{id} binds the id with %s."""
    fake_row = {"id_platillo": 777, "nombre": "Platillo de prueba"}
    patch_service_db(catalogo_main, one_results=[fake_row])
    with TestClient(catalogo_main.app) as client:
        response = client.get("/api/v1/catalogo/platillos/777")
    assert response.status_code == 200

    query, params = patch_service_db.last_connection.executed[0]
    assert "%s" in query, "expected a placeholder instead of an inlined value"
    assert "777" not in query, "the id must not appear in the SQL text"
    assert params == (777,), "the id must be passed as a separate parameter"


def test_list_endpoints_send_static_sql_without_parameters(patch_service_db):
    """List endpoints execute static SQL and bind no user input at all."""
    for module in (clientes_main, catalogo_main):
        patch_service_db(module, all_results=[[]])
        with TestClient(module.app) as client:
            path = (
                "/api/v1/clientes"
                if module is clientes_main
                else "/api/v1/catalogo/platillos"
            )
            response = client.get(path)
        assert response.status_code == 200
        query, params = patch_service_db.last_connection.executed[0]
        assert "%s" not in query
        assert params is None
