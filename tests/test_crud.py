"""CRUD tests (Sprint 2) with fakes: no network, no database writes.

Every test records the executed SQL so it can prove what would run:
parameterized values, whitelist-only updates, logical (never physical)
deletes, identity taken from the JWT and prices taken from catalogo.
"""

from decimal import Decimal

import httpx
import psycopg
from fastapi.testclient import TestClient

from services.catalogo.app import main as catalogo_main
from services.clientes.app import main as clientes_main
from services.reservas.app import main as reservas_main
from shared.auth import ROLE_ADMIN, ROLE_CLIENT
from tests.conftest import trigger_error

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CLIENT_ROW = {
    "id_cliente": 1,
    "nombre_completo": "Ana Lopez",
    "numero_identidad": "0801199000123",
    "telefono": "+504 9999-0001",
    "correo": "cliente.prueba@puntoysal.com",
    "fecha_registro": "2026-11-01T12:00:00-06:00",
    "activo": True,
}

_RESERVA_ROW = {
    "id_reserva": 7,
    "codigo_reserva": "RES-CRUD-0007",
    "id_cliente": 1,
    "id_mesa": None,
    "fecha_hora_inicio": "2027-05-01T19:00:00-06:00",
    "duracion_minutos": 120,
    "cantidad_personas": 2,
    "estado": "pendiente",
    "observaciones": None,
    "fecha_creacion": "2026-11-02T12:00:00-06:00",
    "fecha_actualizacion": "2026-11-02T12:00:00-06:00",
    "id_administrador": None,
}

_MESA_ROW = {
    "id_mesa": 1,
    "numero_mesa": "T-1",
    "capacidad": 4,
    "ubicacion": "Terraza",
    "estado": "disponible",
    "activa": True,
}

_PLATILLO_ROW = {
    "id_platillo": 1,
    "nombre": "Filete de pescado",
    "descripcion": "A la plancha",
    "precio": "180.00",
    "disponible": True,
    "fecha_creacion": "2026-11-01T12:00:00-06:00",
}


def catalogo_client_returning(payload_by_id):
    """Catalogo HTTP client (mock transport) with canned dish payloads."""

    def handler(request: httpx.Request) -> httpx.Response:
        dish_id = int(request.url.path.rsplit("/", 1)[-1])
        if dish_id in payload_by_id:
            return httpx.Response(200, json={"data": payload_by_id[dish_id]})
        return httpx.Response(404, json={"detail": "Dish not found"})

    return httpx.Client(transport=httpx.MockTransport(handler), timeout=5.0)


def set_clause(query: str) -> str:
    """Return the ``SET ...`` portion of an UPDATE statement."""
    return query.split("SET", 1)[1].split("WHERE", 1)[0]


# ---------------------------------------------------------------------------
# Clientes CRUD (7)
# ---------------------------------------------------------------------------


def test_register_client_creates_account_and_profile(patch_service_db):
    """POST /api/v1/clientes: 201, bcrypt hash, rol forced to 'cliente'."""
    new_profile = dict(_CLIENT_ROW, id_cliente=9, correo="nuevo@puntoysal.com")
    patch_service_db(
        clientes_main,
        one_results=[{"id_usuario": 42}, new_profile],
    )
    payload = {
        "nombre_completo": "Ana Lopez",
        "correo": "nuevo@puntoysal.com",
        "password": "ClaveNueva2026",
        "telefono": "+504 9999-0001",
    }
    with TestClient(clientes_main.app) as client:
        response = client.post("/api/v1/clientes", json=payload)
    assert response.status_code == 201
    body = response.json()["data"]
    # The response never exposes credentials or internal linkage.
    assert "password" not in str(body).lower()
    assert "password_hash" not in body
    assert "id_usuario" not in body

    executed = patch_service_db.last_connection.executed
    assert len(executed) == 2
    insert_usuario, insert_cliente = executed
    assert "INSERT INTO usuarios" in insert_usuario[0]
    assert "INSERT INTO clientes" in insert_cliente[0]
    u_params = insert_usuario[1]
    # (correo, hash, rol): hash is bcrypt, never the plain password.
    assert u_params[0] == "nuevo@puntoysal.com"
    assert u_params[1].startswith(("$2a$", "$2b$", "$2y$"))
    assert "ClaveNueva2026" not in u_params
    assert u_params[2] == ROLE_CLIENT, "the role is forced by the service"
    # Profile links back to the created account.
    assert insert_cliente[1][-1] == 42


def test_register_duplicate_email_returns_409(scripted_service_db):
    """Duplicate correo/identidad -> 409 (no half-created account)."""
    scripted_service_db(
        clientes_main,
        effects=[psycopg.errors.UniqueViolation("usuarios_correo_key")],
    )
    with TestClient(clientes_main.app) as client:
        response = client.post(
            "/api/v1/clientes",
            json={
                "nombre_completo": "Ana",
                "correo": "duplicado@puntoysal.com",
                "password": "ClaveNueva2026",
                "telefono": "9999",
            },
        )
    assert response.status_code == 409
    assert response.json()["detail"] == "Email or identity number already registered"


def test_register_rejects_password_over_72_bytes(patch_service_db):
    """bcrypt cannot process >72 bytes: rejected before hashing (422)."""
    # 40 characters that encode to 80 UTF-8 bytes (within max_length=72).
    heavy_password = "ñ" * 40
    assert len(heavy_password) == 40
    assert len(heavy_password.encode("utf-8")) == 80
    patch_service_db(clientes_main, one_results=[])
    with TestClient(clientes_main.app) as client:
        response = client.post(
            "/api/v1/clientes",
            json={
                "nombre_completo": "Ana",
                "correo": "bytes@puntoysal.com",
                "password": heavy_password,
                "telefono": "9999",
            },
        )
    assert response.status_code == 422
    assert patch_service_db.last_connection.executed == []


def test_register_rejects_short_password(patch_service_db):
    patch_service_db(clientes_main, one_results=[])
    with TestClient(clientes_main.app) as client:
        response = client.post(
            "/api/v1/clientes",
            json={
                "nombre_completo": "Ana",
                "correo": "corta@puntoysal.com",
                "password": "1234567",
                "telefono": "9999",
            },
        )
    assert response.status_code == 422


def test_update_client_whitelists_fields(patch_service_db, client_headers):
    """PATCH by the owner updates only the supplied business field."""
    target = {"id_cliente": 1, "id_usuario": 10, "correo": "cliente.prueba@puntoysal.com"}
    updated = dict(_CLIENT_ROW, telefono="+504 8888-2222")
    patch_service_db(clientes_main, one_results=[target, updated])
    with TestClient(clientes_main.app) as client:
        response = client.patch(
            "/api/v1/clientes/1",
            json={"telefono": "+504 8888-2222"},
            headers=client_headers,
        )
    assert response.status_code == 200
    assert response.json()["data"]["telefono"] == "+504 8888-2222"

    executed = patch_service_db.last_connection.executed
    assert len(executed) == 2
    select_q, select_p = executed[0]
    assert "id_usuario" in select_q and select_p == (1, 2)
    update_q, update_p = executed[1]
    assert "UPDATE clientes" in update_q
    clause = set_clause(update_q)
    assert "telefono = %s" in clause
    for forbidden in ("rol", "activo", "password_hash", "id_usuario"):
        assert forbidden not in clause, forbidden
    assert update_p == ("+504 8888-2222", 1)


def test_update_client_syncs_email_to_account(patch_service_db, admin_headers):
    """Changing correo keeps usuarios.correo consistent in the same write."""
    target = {"id_cliente": 1, "id_usuario": 10, "correo": "viejo@puntoysal.com"}
    updated = dict(_CLIENT_ROW, correo="nuevo@puntoysal.com")
    patch_service_db(clientes_main, one_results=[target, updated])
    with TestClient(clientes_main.app) as client:
        response = client.put(
            "/api/v1/clientes/1",
            json={"correo": "nuevo@puntoysal.com"},
            headers=admin_headers,
        )
    assert response.status_code == 200
    executed = patch_service_db.last_connection.executed
    assert len(executed) == 3
    account_query, account_params = executed[1]
    assert "UPDATE usuarios" in account_query
    assert account_params == ("nuevo@puntoysal.com", 10)


def test_update_missing_client_returns_404(patch_service_db, admin_headers):
    patch_service_db(clientes_main, one_results=[None])
    with TestClient(clientes_main.app) as client:
        response = client.patch(
            "/api/v1/clientes/999999",
            json={"telefono": "9999"},
            headers=admin_headers,
        )
    assert response.status_code == 404


def test_delete_client_is_logical(patch_service_db, admin_headers):
    """DELETE (admin) deactivates rows; never a physical DELETE."""
    row = dict(_CLIENT_ROW, activo=False, id_usuario=10)
    patch_service_db(clientes_main, one_results=[row])
    with TestClient(clientes_main.app) as client:
        response = client.delete("/api/v1/clientes/1", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["activo"] is False
    assert "id_usuario" not in data

    executed = patch_service_db.last_connection.executed
    assert len(executed) == 2
    for query, _params in executed:
        assert not query.strip().upper().startswith("DELETE")
    assert "activo = false" in executed[0][0]
    assert "UPDATE usuarios" in executed[1][0]
    assert executed[1][1] == (10,)


def test_delete_missing_client_returns_404(patch_service_db, admin_headers):
    patch_service_db(clientes_main, one_results=[None])
    with TestClient(clientes_main.app) as client:
        response = client.delete("/api/v1/clientes/999999", headers=admin_headers)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Catalogo CRUD (9)
# ---------------------------------------------------------------------------


def test_create_mesa_returns_201(patch_service_db, admin_headers):
    patch_service_db(catalogo_main, one_results=[_MESA_ROW])
    with TestClient(catalogo_main.app) as client:
        response = client.post(
            "/api/v1/catalogo/mesas",
            json={"numero_mesa": "T-1", "capacidad": 4, "ubicacion": "Terraza"},
            headers=admin_headers,
        )
    assert response.status_code == 201
    assert response.json()["data"] == _MESA_ROW
    query, params = patch_service_db.last_connection.executed[0]
    assert "INSERT INTO mesas" in query
    assert params == ("T-1", 4, "Terraza", "disponible", True)


def test_create_mesa_duplicate_returns_409(scripted_service_db, admin_headers):
    scripted_service_db(
        catalogo_main,
        effects=[psycopg.errors.UniqueViolation("mesas_numero_mesa_key")],
    )
    with TestClient(catalogo_main.app) as client:
        response = client.post(
            "/api/v1/catalogo/mesas",
            json={"numero_mesa": "T-1", "capacidad": 4},
            headers=admin_headers,
        )
    assert response.status_code == 409


def test_create_mesa_negative_capacity_422(patch_service_db, admin_headers):
    patch_service_db(catalogo_main, one_results=[])
    with TestClient(catalogo_main.app) as client:
        response = client.post(
            "/api/v1/catalogo/mesas",
            json={"numero_mesa": "T-X", "capacidad": 0},
            headers=admin_headers,
        )
    assert response.status_code == 422
    assert patch_service_db.last_connection.executed == []


def test_update_mesa_partial_whitelist(patch_service_db, admin_headers):
    patch_service_db(catalogo_main, one_results=[dict(_MESA_ROW, capacidad=8)])
    with TestClient(catalogo_main.app) as client:
        response = client.patch(
            "/api/v1/catalogo/mesas/1",
            json={"capacidad": 8},
            headers=admin_headers,
        )
    assert response.status_code == 200
    query, params = patch_service_db.last_connection.executed[0]
    assert "UPDATE mesas" in query
    clause = set_clause(query)
    assert "capacidad = %s" in clause
    assert params == (8, 1)


def test_delete_mesa_is_logical(patch_service_db, admin_headers):
    row = dict(_MESA_ROW, activa=False)
    patch_service_db(catalogo_main, one_results=[row])
    with TestClient(catalogo_main.app) as client:
        response = client.delete("/api/v1/catalogo/mesas/1", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["data"]["activa"] is False
    query, params = patch_service_db.last_connection.executed[0]
    assert not query.strip().upper().startswith("DELETE")
    # Constant literal (no user input): only the id is parameterized.
    assert "activa = false" in query
    assert params == (1,)


def test_delete_missing_mesa_returns_404(patch_service_db, admin_headers):
    patch_service_db(catalogo_main, one_results=[None])
    with TestClient(catalogo_main.app) as client:
        response = client.delete("/api/v1/catalogo/mesas/999999", headers=admin_headers)
    assert response.status_code == 404


def test_create_platillo_returns_201(patch_service_db, admin_headers):
    patch_service_db(catalogo_main, one_results=[_PLATILLO_ROW])
    with TestClient(catalogo_main.app) as client:
        response = client.post(
            "/api/v1/catalogo/platillos",
            json={
                "nombre": "Filete de pescado",
                "descripcion": "A la plancha",
                "precio": "180.00",
            },
            headers=admin_headers,
        )
    assert response.status_code == 201
    query, params = patch_service_db.last_connection.executed[0]
    assert "INSERT INTO platillos" in query
    assert params == ("Filete de pescado", "A la plancha", Decimal("180.00"), True)


def test_create_platillo_negative_price_422(patch_service_db, admin_headers):
    patch_service_db(catalogo_main, one_results=[])
    with TestClient(catalogo_main.app) as client:
        response = client.post(
            "/api/v1/catalogo/platillos",
            json={"nombre": "Inválido", "precio": "-1.00"},
            headers=admin_headers,
        )
    assert response.status_code == 422
    assert patch_service_db.last_connection.executed == []


def test_update_platillo_partial_whitelist(patch_service_db, admin_headers):
    patch_service_db(catalogo_main, one_results=[dict(_PLATILLO_ROW, precio="200.00")])
    with TestClient(catalogo_main.app) as client:
        response = client.put(
            "/api/v1/catalogo/platillos/1",
            json={"precio": "200.00"},
            headers=admin_headers,
        )
    assert response.status_code == 200
    query, params = patch_service_db.last_connection.executed[0]
    clause = set_clause(query)
    assert "precio = %s" in clause
    assert params == (Decimal("200.00"), 1)


def test_delete_platillo_is_logical(patch_service_db, admin_headers):
    row = dict(_PLATILLO_ROW, disponible=False)
    patch_service_db(catalogo_main, one_results=[row])
    with TestClient(catalogo_main.app) as client:
        response = client.delete(
            "/api/v1/catalogo/platillos/1", headers=admin_headers
        )
    assert response.status_code == 200
    assert response.json()["data"]["disponible"] is False
    query, params = patch_service_db.last_connection.executed[0]
    assert not query.strip().upper().startswith("DELETE")
    # Constant literal (no user input): only the id is parameterized.
    assert "disponible = false" in query
    assert params == (1,)


# ---------------------------------------------------------------------------
# Reservas CRUD (13, 14)
# ---------------------------------------------------------------------------


def test_create_reservation_forces_client_identity_and_catalog_price(
    patch_service_db, client_headers, monkeypatch
):
    """Client create: id_cliente from the JWT, price from catalogo HTTP."""
    patch_service_db(reservas_main, one_results=[_RESERVA_ROW])
    monkeypatch.setattr(
        reservas_main,
        "_catalogo_client",
        lambda: catalogo_client_returning(
            {1: {"id_platillo": 1, "nombre": "Filete", "precio": "180.00"}}
        ),
    )
    payload = {
        "fecha_hora_inicio": "2027-05-01T19:00:00-06:00",
        "cantidad_personas": 2,
        "id_mesa": None,
        "platillos": [{"id_platillo": 1, "cantidad": 2}],
    }
    with TestClient(reservas_main.app) as client:
        response = client.post(
            "/api/v1/reservas", json=payload, headers=client_headers
        )
    assert response.status_code == 201
    assert response.json()["data"] == _RESERVA_ROW

    executed = patch_service_db.last_connection.executed
    insert_reserva, insert_platillo = executed
    assert "INSERT INTO reservas" in insert_reserva[0]
    # Identity: id_cliente comes from the token claim (first parameter).
    assert insert_reserva[1][0] == 1
    assert "INSERT INTO reserva_platillos" in insert_platillo[0]
    # Price comes from the catalog, never from the request body.
    assert insert_platillo[1][3] == Decimal("180.00")


def test_create_reservation_rejects_price_in_body(patch_service_db, client_headers):
    """precio_unitario is not an accepted field (extra=forbid)."""
    patch_service_db(reservas_main, one_results=[])
    with TestClient(reservas_main.app) as client:
        response = client.post(
            "/api/v1/reservas",
            json={
                "fecha_hora_inicio": "2027-05-01T19:00:00-06:00",
                "cantidad_personas": 2,
                "platillos": [
                    {"id_platillo": 1, "cantidad": 1, "precio_unitario": "0.01"}
                ],
            },
            headers=client_headers,
        )
    assert response.status_code == 422
    assert patch_service_db.last_connection.executed == []


def test_create_reservation_unknown_dish_returns_400(
    patch_service_db, client_headers, monkeypatch
):
    """A dish that does not exist in catalogo aborts before any write."""
    patch_service_db(reservas_main, one_results=[])
    monkeypatch.setattr(
        reservas_main,
        "_catalogo_client",
        lambda: catalogo_client_returning({}),
    )
    with TestClient(reservas_main.app) as client:
        response = client.post(
            "/api/v1/reservas",
            json={
                "fecha_hora_inicio": "2027-05-01T19:00:00-06:00",
                "cantidad_personas": 2,
                "platillos": [{"id_platillo": 999, "cantidad": 1}],
            },
            headers=client_headers,
        )
    assert response.status_code == 400
    assert response.json()["detail"] == "Dish 999 does not exist"
    assert patch_service_db.last_connection.executed == [], "no write must run"


def test_create_reservation_catalogo_down_returns_503(
    patch_service_db, client_headers, monkeypatch
):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    patch_service_db(reservas_main, one_results=[])
    monkeypatch.setattr(
        reservas_main,
        "_catalogo_client",
        lambda: httpx.Client(transport=httpx.MockTransport(handler), timeout=5.0),
    )
    with TestClient(reservas_main.app) as client:
        response = client.post(
            "/api/v1/reservas",
            json={
                "fecha_hora_inicio": "2027-05-01T19:00:00-06:00",
                "cantidad_personas": 2,
                "platillos": [{"id_platillo": 1, "cantidad": 1}],
            },
            headers=client_headers,
        )
    assert response.status_code == 503
    assert patch_service_db.last_connection.executed == []


def test_create_reservation_trigger_rule_returns_400(
    scripted_service_db, client_headers
):
    """Database trigger rules (e.g. mesa unavailable) -> 400 + message."""
    scripted_service_db(
        reservas_main,
        effects=[
            trigger_error(
                "La mesa seleccionada no está disponible para esa fecha."
            )
        ],
    )
    with TestClient(reservas_main.app) as client:
        response = client.post(
            "/api/v1/reservas",
            json={
                "fecha_hora_inicio": "2027-05-01T19:00:00-06:00",
                "cantidad_personas": 2,
            },
            headers=client_headers,
        )
    assert response.status_code == 400
    assert "no está disponible" in response.json()["detail"]


def test_create_reservation_admin_requires_client(scripted_service_db, admin_headers):
    """Administrators must say which customer the reservation is for."""
    scripted_service_db(reservas_main, effects=[])
    with TestClient(reservas_main.app) as client:
        response = client.post(
            "/api/v1/reservas",
            json={
                "fecha_hora_inicio": "2027-05-01T19:00:00-06:00",
                "cantidad_personas": 2,
            },
            headers=admin_headers,
        )
    assert response.status_code == 400
    assert "id_cliente" in response.json()["detail"]
    assert scripted_service_db.last_connection.executed == []


def test_create_reservation_naive_datetime_422(patch_service_db, client_headers):
    """Timestamps require an explicit timezone offset."""
    patch_service_db(reservas_main, one_results=[])
    with TestClient(reservas_main.app) as client:
        response = client.post(
            "/api/v1/reservas",
            json={
                "fecha_hora_inicio": "2027-05-01T19:00:00",
                "cantidad_personas": 2,
            },
            headers=client_headers,
        )
    assert response.status_code == 422


def test_create_reservation_invalid_inputs_422(patch_service_db, client_headers):
    """Zero guests / too short duration / negative quantities are rejected."""
    cases = [
        {"fecha_hora_inicio": "2027-05-01T19:00:00-06:00", "cantidad_personas": 0},
        {"fecha_hora_inicio": "2027-05-01T19:00:00-06:00", "cantidad_personas": 2,
         "duracion_minutos": 5},
        {"fecha_hora_inicio": "2027-05-01T19:00:00-06:00", "cantidad_personas": 2,
         "platillos": [{"id_platillo": 1, "cantidad": 0}]},
    ]
    for body in cases:
        patch_service_db(reservas_main, one_results=[])
        with TestClient(reservas_main.app) as client:
            response = client.post(
                "/api/v1/reservas", json=body, headers=client_headers
            )
        assert response.status_code == 422, body
        assert patch_service_db.last_connection.executed == []


def test_update_reservation_trigger_message_returns_400(
    scripted_service_db, admin_headers
):
    """An illegal estado transition is rejected by the DB trigger (400)."""
    scripted_service_db(
        reservas_main,
        one_results=[{"id_reserva": 7}],
        effects=[
            None,  # ownership SELECT succeeds
            trigger_error(
                "Transición de estado no permitida: confirmada -> pendiente."
            ),
        ],
    )
    with TestClient(reservas_main.app) as client:
        response = client.patch(
            "/api/v1/reservas/RES-CRUD-0007",
            json={"estado": "pendiente"},
            headers=admin_headers,
        )
    assert response.status_code == 400
    assert "Transición de estado no permitida" in response.json()["detail"]


def test_update_reservation_unknown_field_422(patch_service_db, admin_headers):
    patch_service_db(reservas_main, one_results=[])
    with TestClient(reservas_main.app) as client:
        response = client.put(
            "/api/v1/reservas/RES-CRUD-0007",
            json={"codigo_reserva": "HACK-1"},
            headers=admin_headers,
        )
    assert response.status_code == 422
    assert patch_service_db.last_connection.executed == []


def test_delete_reservation_is_logical(patch_service_db, admin_headers):
    """DELETE cancels logically: only estado changes, no row disappears."""
    target = {"id_reserva": 7}
    cancelada = dict(_RESERVA_ROW, estado="cancelada", id_administrador=1)
    patch_service_db(reservas_main, one_results=[target, cancelada])
    with TestClient(reservas_main.app) as client:
        response = client.delete(
            "/api/v1/reservas/RES-CRUD-0007", headers=admin_headers
        )
    assert response.status_code == 200
    assert response.json()["data"]["estado"] == "cancelada"

    executed = patch_service_db.last_connection.executed
    assert len(executed) == 2
    select_q, select_p = executed[0]
    assert "FROM reservas" in select_q and select_p == ("RES-CRUD-0007",)
    update_q, update_p = executed[1]
    assert not update_q.strip().upper().startswith("DELETE")
    assert "estado = 'cancelada'" in update_q
    assert update_p == (1, 7), "acting admin (JWT) and reservation id"


def test_delete_reservation_trigger_rule_returns_400(
    scripted_service_db, admin_headers
):
    """e.g. a completed reservation cannot be cancelled (DB rule)."""
    scripted_service_db(
        reservas_main,
        one_results=[{"id_reserva": 7}],
        effects=[
            None,  # ownership SELECT succeeds
            trigger_error(
                "Transición de estado no permitida: completada -> cancelada."
            ),
        ],
    )
    with TestClient(reservas_main.app) as client:
        response = client.delete(
            "/api/v1/reservas/RES-CRUD-0007", headers=admin_headers
        )
    assert response.status_code == 400
    assert "Transición de estado no permitida" in response.json()["detail"]


def test_delete_missing_reservation_returns_404(patch_service_db, admin_headers):
    patch_service_db(reservas_main, one_results=[None])
    with TestClient(reservas_main.app) as client:
        response = client.delete(
            "/api/v1/reservas/NO-EXISTE", headers=admin_headers
        )
    assert response.status_code == 404
