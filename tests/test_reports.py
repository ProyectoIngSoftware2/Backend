"""Sprint 4 reporting tests: GET /api/v1/reportes/reservas (gap G4).

All tests run in-process with faked database access: no network, no
live database writes. The endpoint issues two fetchall reads in a
fixed order (detail rows, per-state counts) scripted through
``all_results``. Filters are validated before any SQL runs, so the 400
tests also assert the database was never touched. Patterns follow
tests/test_availability.py and tests/test_sprint3.py.
"""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from services.reservas.app import main as reservas_main

_TZ = timezone(timedelta(hours=-6))

_RESERVAS_ROWS = [
    {
        "id_reserva": 1,
        "codigo_reserva": "RES-AAAA-1111",
        "id_cliente": 7,
        "id_mesa": 2,
        "fecha_hora_inicio": datetime(2026, 11, 20, 19, 0, tzinfo=_TZ),
        "duracion_minutos": 120,
        "cantidad_personas": 4,
        "estado": "confirmada",
        "observaciones": None,
        "fecha_creacion": datetime(2026, 11, 10, 8, 0, tzinfo=_TZ),
        "fecha_actualizacion": datetime(2026, 11, 10, 8, 0, tzinfo=_TZ),
        "id_administrador": None,
    },
    {
        "id_reserva": 2,
        "codigo_reserva": "RES-BBBB-2222",
        "id_cliente": 7,
        "id_mesa": None,
        "fecha_hora_inicio": datetime(2026, 11, 21, 13, 0, tzinfo=_TZ),
        "duracion_minutos": 60,
        "cantidad_personas": 2,
        "estado": "pendiente",
        "observaciones": "Aniversario",
        "fecha_creacion": datetime(2026, 11, 12, 9, 30, tzinfo=_TZ),
        "fecha_actualizacion": datetime(2026, 11, 12, 9, 30, tzinfo=_TZ),
        "id_administrador": None,
    },
]

_COUNTS_ROWS = [
    {"estado": "confirmada", "total": 2},
    {"estado": "pendiente", "total": 1},
]

_EMPTY_POR_ESTADO = {
    "pendiente": 0,
    "aprobada": 0,
    "confirmada": 0,
    "rechazada": 0,
    "cancelada": 0,
    "completada": 0,
}


# ---------------------------------------------------------------------------
# Happy paths (administrators only)
# ---------------------------------------------------------------------------


def test_reports_admin_with_all_filters(patch_service_db, admin_headers):
    """All five filters are applied and bound as separate %s parameters."""
    patch_service_db(
        reservas_main, all_results=[_RESERVAS_ROWS, _COUNTS_ROWS]
    )
    with TestClient(reservas_main.app) as client:
        response = client.get(
            "/api/v1/reportes/reservas"
            "?fecha_inicio=2026-11-01&fecha_fin=2026-11-30"
            "&estado=confirmada&id_cliente=7&id_mesa=2",
            headers=admin_headers,
        )
    assert response.status_code == 200

    data = response.json()["data"]
    assert data["filtros"] == {
        "fecha_inicio": "2026-11-01",
        "fecha_fin": "2026-11-30",
        "estado": "confirmada",
        "id_cliente": 7,
        "id_mesa": 2,
    }
    assert data["resumen"] == {
        "total_reservas": 3,
        "por_estado": {**_EMPTY_POR_ESTADO, "confirmada": 2, "pendiente": 1},
    }
    assert [row["codigo_reserva"] for row in data["reservas"]] == [
        "RES-AAAA-1111",
        "RES-BBBB-2222",
    ]

    # Two statements (rows + counts), both with the same five-bound
    # parameter tuple: values never appear in the SQL text (F-07).
    executed = patch_service_db.last_connection.executed
    assert len(executed) == 2, "expected the rows query and the counts query"
    expected_params = ("2026-11-01", "2026-11-30", "confirmada", 7, 2)
    for query, params in executed:
        assert query.count("%s") == 5, "one placeholder per filter value"
        assert params == expected_params
        assert "2026-11-01" not in query, "the date must not be inlined"
        assert "confirmada" not in query, "the estado must not be inlined"
    assert "GROUP BY estado" in executed[1][0]
    assert "ORDER BY fecha_hora_inicio" in executed[0][0]


def test_reports_without_filters(patch_service_db, admin_headers):
    """No filters -> unfiltered report with a zeroed summary."""
    patch_service_db(reservas_main, all_results=[[], []])
    with TestClient(reservas_main.app) as client:
        response = client.get("/api/v1/reportes/reservas", headers=admin_headers)
    assert response.status_code == 200

    data = response.json()["data"]
    assert data["filtros"] == {
        "fecha_inicio": None,
        "fecha_fin": None,
        "estado": None,
        "id_cliente": None,
        "id_mesa": None,
    }
    assert data["resumen"] == {"total_reservas": 0, "por_estado": _EMPTY_POR_ESTADO}
    assert data["reservas"] == []

    executed = patch_service_db.last_connection.executed
    assert len(executed) == 2
    for query, params in executed:
        assert "WHERE" not in query, "no filter must produce no WHERE clause"
        assert params == ()


def test_reports_single_filter_binds_one_parameter(patch_service_db, admin_headers):
    """A single filter still travels as a parameter, not as SQL text."""
    patch_service_db(reservas_main, all_results=[[_RESERVAS_ROWS[1]], []])
    with TestClient(reservas_main.app) as client:
        response = client.get(
            "/api/v1/reportes/reservas?id_cliente=7", headers=admin_headers
        )
    assert response.status_code == 200

    data = response.json()["data"]
    assert data["filtros"]["id_cliente"] == 7
    assert data["filtros"]["fecha_inicio"] is None
    assert data["filtros"]["estado"] is None

    executed = patch_service_db.last_connection.executed
    assert executed[0][0].count("%s") == 1
    assert executed[0][1] == (7,)
    assert "id_cliente = %s" in executed[0][0]


# ---------------------------------------------------------------------------
# RBAC: administrators only (403 for cliente, 401 without a token)
# ---------------------------------------------------------------------------


def test_reports_cliente_is_forbidden(patch_service_db, client_headers):
    """A cliente token is rejected with 403 before any report runs."""
    patch_service_db(reservas_main, all_results=[[], []])
    with TestClient(reservas_main.app) as client:
        response = client.get(
            "/api/v1/reportes/reservas", headers=client_headers
        )
    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"


def test_reports_missing_token_is_401(patch_service_db):
    """Unauthenticated access is 401 (distinct from the 403 above)."""
    patch_service_db(reservas_main, all_results=[[], []])
    with TestClient(reservas_main.app) as client:
        response = client.get("/api/v1/reportes/reservas")
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


# ---------------------------------------------------------------------------
# Parameter validation (400, never 422, and never reaching the database)
# ---------------------------------------------------------------------------


def test_reports_invalid_fecha_values_return_400(patch_service_db, admin_headers):
    """Malformed fecha_inicio / fecha_fin are rejected with 400."""
    patch_service_db(reservas_main, all_results=[[], []])
    with TestClient(reservas_main.app) as client:
        inicio = client.get(
            "/api/v1/reportes/reservas?fecha_inicio=ayer", headers=admin_headers
        )
        fin = client.get(
            "/api/v1/reportes/reservas?fecha_fin=31/12/2026", headers=admin_headers
        )
    assert inicio.status_code == 400
    assert "fecha_inicio" in inicio.json()["detail"]
    assert fin.status_code == 400
    assert "fecha_fin" in fin.json()["detail"]
    assert patch_service_db.last_connection.executed == []


def test_reports_inverted_date_range_returns_400(patch_service_db, admin_headers):
    """fecha_inicio after fecha_fin is rejected before any SQL runs."""
    patch_service_db(reservas_main, all_results=[[], []])
    with TestClient(reservas_main.app) as client:
        response = client.get(
            "/api/v1/reportes/reservas"
            "?fecha_inicio=2026-12-01&fecha_fin=2026-11-01",
            headers=admin_headers,
        )
    assert response.status_code == 400
    assert "fecha_inicio" in response.json()["detail"]
    assert patch_service_db.last_connection.executed == []


def test_reports_invalid_estado_returns_400(patch_service_db, admin_headers):
    """estado outside the six-state whitelist is rejected with 400."""
    patch_service_db(reservas_main, all_results=[[], []])
    with TestClient(reservas_main.app) as client:
        response = client.get(
            "/api/v1/reportes/reservas?estado=volando", headers=admin_headers
        )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "estado" in detail
    assert "pendiente" in detail and "completada" in detail
    assert patch_service_db.last_connection.executed == []


def test_reports_invalid_ids_return_400(patch_service_db, admin_headers):
    """Non-numeric or non-positive id_cliente / id_mesa are rejected."""
    patch_service_db(reservas_main, all_results=[[], []])
    with TestClient(reservas_main.app) as client:
        text = client.get(
            "/api/v1/reportes/reservas?id_cliente=abc", headers=admin_headers
        )
        zero = client.get(
            "/api/v1/reportes/reservas?id_cliente=0", headers=admin_headers
        )
        negative = client.get(
            "/api/v1/reportes/reservas?id_mesa=-3", headers=admin_headers
        )
    for response in (text, zero, negative):
        assert response.status_code == 400
        assert "positive integer" in response.json()["detail"]
    assert patch_service_db.last_connection.executed == []


# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------


def test_reports_database_failure_returns_503(failing_connection, admin_headers):
    """A down database answers the controlled 503 like every sibling route."""
    failing_connection(reservas_main)
    with TestClient(reservas_main.app) as client:
        response = client.get("/api/v1/reportes/reservas", headers=admin_headers)
    assert response.status_code == 503
    assert response.json()["detail"] == "Database connection failed"


def test_reports_unexpected_error_returns_500(unexpected_failure, admin_headers):
    """A non-database bug is logged and answered as a generic 500."""
    unexpected_failure(reservas_main)
    with TestClient(reservas_main.app) as client:
        response = client.get("/api/v1/reportes/reservas", headers=admin_headers)
    assert response.status_code == 500
    assert response.json()["detail"] == "Internal server error"
