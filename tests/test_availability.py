"""Sprint 4 availability tests: GET /api/v1/disponibilidad (gap G6).

All tests run in-process with faked database access: no network, no
live database writes. The endpoint issues four fetchall reads in a
fixed order (horarios, mesas, reservas, bloqueos_horario), scripted
through ``all_results``. Every request here is sent without an
Authorization header, which also proves the endpoint is public.
Patterns follow tests/test_sprint3.py.
"""

from datetime import datetime, time, timedelta, timezone

from fastapi.testclient import TestClient

from services.reservas.app import main as reservas_main

_FECHA = "2026-11-16"  # a Monday -> dia_semana 1

_HORARIO_19_23 = {
    "hora_apertura": time(19, 0),
    "hora_cierre": time(23, 0),
    "intervalo_minutos": 60,
}

_MESAS = [
    {"id_mesa": 1, "numero_mesa": "M1", "capacidad": 4},
    {"id_mesa": 2, "numero_mesa": "M2", "capacidad": 6},
    {"id_mesa": 3, "numero_mesa": "M3", "capacidad": 8},
]


def _availability_reads(horarios=(), mesas=(), reservas=(), bloqueos=()):
    """Build the four fetchall results consumed by the endpoint (in order)."""
    return [list(horarios), list(mesas), list(reservas), list(bloqueos)]


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_availability_happy_path_public(patch_service_db):
    """Public GET (no token) returns the day's slots and their free mesas."""
    patch_service_db(
        reservas_main,
        all_results=_availability_reads(
            horarios=[_HORARIO_19_23], mesas=_MESAS
        ),
    )
    with TestClient(reservas_main.app) as client:
        response = client.get(f"/api/v1/disponibilidad?fecha={_FECHA}")
    assert response.status_code == 200

    data = response.json()["data"]
    assert data["fecha"] == _FECHA
    assert data["dia_semana"] == 1  # Monday
    assert data["capacidad_requerida"] == 1  # default
    assert data["duracion_minutos"] == 120  # default
    assert data["mesas"] == _MESAS
    assert data["horarios"] == [
        {"hora_apertura": "19:00", "hora_cierre": "23:00", "intervalo_minutos": 60}
    ]
    # 19:00, 20:00 and 21:00 fit a 120-minute reservation before 23:00;
    # 22:00 would end at midnight and is not offered.
    assert data["slots"] == [
        {"hora": "19:00", "disponible": True, "mesas_disponibles": 3},
        {"hora": "20:00", "disponible": True, "mesas_disponibles": 3},
        {"hora": "21:00", "disponible": True, "mesas_disponibles": 3},
    ]
    assert data["slots_disponibles"] == 3

    # Four reads, and every user-controlled value travels as %s (F-07).
    executed = patch_service_db.last_connection.executed
    assert len(executed) == 4, "expected horarios, mesas, reservas, bloqueos"
    assert executed[0][1] == (1,), "dia_semana must be bound as a parameter"
    assert executed[1][1] == (1,), "default capacidad >= 1"
    assert executed[2][1] == (_FECHA, _FECHA)
    assert executed[3][1] == (_FECHA, _FECHA)
    for query, _params in executed:
        assert "%s" in query, "expected a placeholder instead of an inline value"
        assert _FECHA not in query, "the date must not appear in the SQL text"


def test_availability_filters_capacity_and_duration(patch_service_db):
    """cantidad_personas filters mesas; duracion_minutos shapes the slots."""
    patch_service_db(
        reservas_main,
        all_results=_availability_reads(
            horarios=[_HORARIO_19_23],
            mesas=[_MESAS[1]],  # only M2 (capacidad 6) can host 5 guests
        ),
    )
    with TestClient(reservas_main.app) as client:
        response = client.get(
            f"/api/v1/disponibilidad?fecha={_FECHA}"
            "&cantidad_personas=5&duracion_minutos=90"
        )
    assert response.status_code == 200

    data = response.json()["data"]
    assert data["capacidad_requerida"] == 5
    assert data["duracion_minutos"] == 90
    assert data["mesas"] == [_MESAS[1]]
    assert data["slots_disponibles"] == 3
    assert patch_service_db.last_connection.executed[1][1] == (5,)


def test_availability_closed_weekday_returns_empty(patch_service_db):
    """No active horarios for the weekday -> 200 with no slots (closed)."""
    patch_service_db(reservas_main, all_results=_availability_reads())
    with TestClient(reservas_main.app) as client:
        response = client.get(f"/api/v1/disponibilidad?fecha={_FECHA}")
    assert response.status_code == 200

    data = response.json()["data"]
    assert data["horarios"] == []
    assert data["slots"] == []
    assert data["slots_disponibles"] == 0


# ---------------------------------------------------------------------------
# Parameter validation (400, never 422, and never reaching the database)
# ---------------------------------------------------------------------------


def test_availability_missing_fecha_returns_400(patch_service_db):
    """Without fecha the endpoint answers 400 before touching the database."""
    patch_service_db(reservas_main, all_results=_availability_reads())
    with TestClient(reservas_main.app) as client:
        response = client.get("/api/v1/disponibilidad")
    assert response.status_code == 400
    assert "fecha" in response.json()["detail"]
    assert patch_service_db.last_connection.executed == []


def test_availability_invalid_fecha_returns_400(patch_service_db):
    """Malformed or empty fecha values are rejected with 400, not 422."""
    patch_service_db(reservas_main, all_results=_availability_reads())
    with TestClient(reservas_main.app) as client:
        slash = client.get("/api/v1/disponibilidad?fecha=16/11/2026")
        garbage = client.get("/api/v1/disponibilidad?fecha=ayer")
        empty = client.get("/api/v1/disponibilidad?fecha=")
    for response in (slash, garbage, empty):
        assert response.status_code == 400
    assert patch_service_db.last_connection.executed == []


def test_availability_invalid_cantidad_personas_returns_400(patch_service_db):
    """Non-numeric or < 1 cantidad_personas is rejected with 400."""
    patch_service_db(reservas_main, all_results=_availability_reads())
    with TestClient(reservas_main.app) as client:
        text = client.get(
            f"/api/v1/disponibilidad?fecha={_FECHA}&cantidad_personas=abc"
        )
        zero = client.get(
            f"/api/v1/disponibilidad?fecha={_FECHA}&cantidad_personas=0"
        )
        negative = client.get(
            f"/api/v1/disponibilidad?fecha={_FECHA}&cantidad_personas=-2"
        )
    assert text.status_code == 400
    assert "integer" in text.json()["detail"]
    for response in (zero, negative):
        assert response.status_code == 400
        assert "at least 1" in response.json()["detail"]
    assert patch_service_db.last_connection.executed == []


def test_availability_invalid_duracion_minutos_returns_400(patch_service_db):
    """duracion_minutos outside 15..720 or non-numeric is rejected with 400."""
    patch_service_db(reservas_main, all_results=_availability_reads())
    with TestClient(reservas_main.app) as client:
        text = client.get(
            f"/api/v1/disponibilidad?fecha={_FECHA}&duracion_minutos=abc"
        )
        too_short = client.get(
            f"/api/v1/disponibilidad?fecha={_FECHA}&duracion_minutos=10"
        )
        too_long = client.get(
            f"/api/v1/disponibilidad?fecha={_FECHA}&duracion_minutos=721"
        )
    assert text.status_code == 400
    for response in (too_short, too_long):
        assert response.status_code == 400
        assert "between 15 and 720" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Business rules: reservations and schedule blocks
# ---------------------------------------------------------------------------


def test_availability_reservation_blocks_slot(patch_service_db):
    """An active (tz-aware) reservation occupies its mesa in overlapping slots."""
    patch_service_db(
        reservas_main,
        all_results=_availability_reads(
            horarios=[_HORARIO_19_23],
            mesas=[_MESAS[0]],
            reservas=[
                {
                    "id_mesa": 1,
                    # timestamptz exactly as psycopg returns it: aware datetime
                    "fecha_hora_inicio": datetime(
                        2026, 11, 16, 20, 0, tzinfo=timezone(timedelta(hours=-6))
                    ),
                    "duracion_minutos": 60,
                }
            ],
        ),
    )
    with TestClient(reservas_main.app) as client:
        response = client.get(f"/api/v1/disponibilidad?fecha={_FECHA}")
    assert response.status_code == 200

    slots = response.json()["data"]["slots"]
    # The reservation holds M1 from 20:00 to 21:00: the slots intersecting
    # it have no free mesa; the 21:00 slot starts exactly when it ends.
    assert slots == [
        {"hora": "19:00", "disponible": False, "mesas_disponibles": 0},
        {"hora": "20:00", "disponible": False, "mesas_disponibles": 0},
        {"hora": "21:00", "disponible": True, "mesas_disponibles": 1},
    ]
    assert response.json()["data"]["slots_disponibles"] == 1

    # Only the states that still hold a mesa are read.
    query, _params = patch_service_db.last_connection.executed[2]
    assert "estado IN ('pendiente', 'aprobada', 'confirmada')" in query


def test_availability_general_bloqueo_blocks_every_mesa(patch_service_db):
    """A bloqueo without id_mesa closes the intersecting slots entirely."""
    patch_service_db(
        reservas_main,
        all_results=_availability_reads(
            horarios=[_HORARIO_19_23],
            mesas=_MESAS[:2],
            bloqueos=[
                {
                    "id_mesa": None,
                    "inicio": datetime(
                        2026, 11, 16, 19, 0, tzinfo=timezone(timedelta(hours=-6))
                    ),
                    "fin": datetime(
                        2026, 11, 16, 21, 0, tzinfo=timezone(timedelta(hours=-6))
                    ),
                    "motivo": "Mantenimiento general",
                }
            ],
        ),
    )
    with TestClient(reservas_main.app) as client:
        response = client.get(f"/api/v1/disponibilidad?fecha={_FECHA}")
    assert response.status_code == 200

    slots = response.json()["data"]["slots"]
    assert slots == [
        {"hora": "19:00", "disponible": False, "mesas_disponibles": 0},
        {"hora": "20:00", "disponible": False, "mesas_disponibles": 0},
        {"hora": "21:00", "disponible": True, "mesas_disponibles": 2},
    ]


def test_availability_mesa_bloqueo_blocks_only_that_mesa(patch_service_db):
    """A bloqueo with id_mesa only removes that mesa from the slot."""
    patch_service_db(
        reservas_main,
        all_results=_availability_reads(
            horarios=[_HORARIO_19_23],
            mesas=_MESAS,
            bloqueos=[
                {
                    "id_mesa": 2,
                    "inicio": datetime(
                        2026, 11, 16, 19, 0, tzinfo=timezone(timedelta(hours=-6))
                    ),
                    "fin": datetime(
                        2026, 11, 16, 21, 0, tzinfo=timezone(timedelta(hours=-6))
                    ),
                    "motivo": "Reservado para evento",
                }
            ],
        ),
    )
    with TestClient(reservas_main.app) as client:
        response = client.get(f"/api/v1/disponibilidad?fecha={_FECHA}")
    assert response.status_code == 200

    slots = response.json()["data"]["slots"]
    assert [slot["mesas_disponibles"] for slot in slots] == [2, 2, 3]
    assert all(slot["disponible"] for slot in slots)


# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------


def test_availability_database_failure_returns_503(failing_connection):
    """A down database answers the controlled 503 like every sibling route."""
    failing_connection(reservas_main)
    with TestClient(reservas_main.app) as client:
        response = client.get(f"/api/v1/disponibilidad?fecha={_FECHA}")
    assert response.status_code == 503
    assert response.json()["detail"] == "Database connection failed"


def test_availability_unexpected_error_returns_500(unexpected_failure):
    """A non-database bug is logged and answered as a generic 500."""
    unexpected_failure(reservas_main)
    with TestClient(reservas_main.app) as client:
        response = client.get(f"/api/v1/disponibilidad?fecha={_FECHA}")
    assert response.status_code == 500
    assert response.json()["detail"] == "Internal server error"
