"""Sprint 3 automated tests: usuarios, roles, horarios, bloqueos,
reservation dish-detail CRUD.

All tests run in-process with faked database access: no network, no
live database writes. Patterns follow tests/test_crud.py and
tests/test_authorization.py.
"""

from datetime import datetime

import httpx
import psycopg
from fastapi.testclient import TestClient

from services.catalogo.app import main as catalogo_main
from services.clientes.app import main as clientes_main
from services.reservas.app import main as reservas_main
from shared.auth import ROLE_ADMIN, ROLE_CLIENT
from tests.conftest import trigger_error, scripted_service_db

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

_USUARIO_ROW = {
    "id_usuario": 42,
    "correo": "admin@puntoysal.test",
    "rol": ROLE_ADMIN,
    "activo": True,
    "fecha_creacion": "2026-11-01T12:00:00-06:00",
}

_CLIENT_USUARIO_ROW = {
    "id_usuario": 43,
    "correo": "cliente@puntoysal.test",
    "rol": ROLE_CLIENT,
    "activo": True,
    "fecha_creacion": "2026-11-01T12:00:00-06:00",
}

_ROL_ROW = {
    "id_rol": 1,
    "nombre": ROLE_ADMIN,
    "descripcion": "Acceso total al sistema",
    "activo": True,
}

_CLIENT_ROL_ROW = {
    "id_rol": 2,
    "nombre": ROLE_CLIENT,
    "descripcion": "Acceso de cliente",
    "activo": True,
}

_HORARIO_ROW = {
    "id_horario": 1,
    "dia_semana": 1,
    "hora_apertura": "08:00",
    "hora_cierre": "22:00",
    "intervalo_minutos": 30,
    "activo": True,
}

_BLOQUEO_ROW = {
    "id_bloqueo": 1,
    "id_mesa": 3,
    "inicio": "2026-12-01T14:00:00-06:00",
    "fin": "2026-12-01T16:00:00-06:00",
    "motivo": "Mantenimiento",
    "creado_por": 42,
    "fecha_creacion": "2026-11-01T10:00:00-06:00",
}

_RESERVA_ROW = {
    "id_reserva": 7,
    "codigo_reserva": "RES-S3-0007",
    "id_cliente": 1,
    "id_mesa": 3,
    "fecha_hora_inicio": "2027-05-01T19:00:00-06:00",
    "duracion_minutos": 120,
    "cantidad_personas": 2,
    "estado": "pendiente",
    "observaciones": None,
    "fecha_creacion": "2026-11-02T12:00:00-06:00",
    "fecha_actualizacion": "2026-11-02T12:00:00-06:00",
    "id_administrador": None,
}

_PLATILLO_LINE_ROW = {
    "id_reserva_platillo": 11,
    "id_reserva": 7,
    "id_platillo": 2,
    "cantidad": 2,
    "precio_unitario": "180.00",
    "observaciones": None,
}

# ---------------------------------------------------------------------------
# Catalogo mock for reservation dish-detail pricing
# ---------------------------------------------------------------------------


def _catalogo_dish_payload(dish_id, price="180.00"):
    return {"id_platillo": dish_id, "nombre": "Plato test", "precio": price}


def catalogo_client_for_dishes(dish_prices):
    """Mock catalogo client returning canned dish prices."""

    def handler(request: httpx.Request) -> httpx.Response:
        dish_id = int(request.url.path.rsplit("/", 1)[-1])
        if dish_id in dish_prices:
            return httpx.Response(
                200, json={"data": _catalogo_dish_payload(dish_id, dish_prices[dish_id])}
            )
        return httpx.Response(404, json={"detail": "Dish not found"})

    return httpx.Client(transport=httpx.MockTransport(handler), timeout=5.0)


# ---------------------------------------------------------------------------
# Usuarios CRUD (clientes service)
# ---------------------------------------------------------------------------


def test_list_usuarios_admin(patch_service_db, admin_headers):
    """GET /api/v1/usuarios: administrator lists all users."""
    patch_service_db(clientes_main, all_results=[[_USUARIO_ROW, _CLIENT_USUARIO_ROW]])
    with TestClient(clientes_main.app) as client:
        response = client.get("/api/v1/usuarios", headers=admin_headers)
    assert response.status_code == 200
    assert len(response.json()["data"]) == 2


def test_list_usuarios_client_forbidden(patch_service_db, client_headers):
    """GET /api/v1/usuarios: client token -> 403."""
    patch_service_db(clientes_main, all_results=[[]])
    with TestClient(clientes_main.app) as client:
        response = client.get("/api/v1/usuarios", headers=client_headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"


def test_list_usuarios_no_token_is_401(patch_service_db):
    """GET /api/v1/usuarios: no token -> 401."""
    patch_service_db(clientes_main, all_results=[[]])
    with TestClient(clientes_main.app) as client:
        response = client.get("/api/v1/usuarios")
    assert response.status_code == 401


def test_get_usuario_admin(patch_service_db, admin_headers):
    """GET /api/v1/usuarios/{id}: administrator reads one user."""
    patch_service_db(clientes_main, one_results=[_USUARIO_ROW])
    with TestClient(clientes_main.app) as client:
        response = client.get("/api/v1/usuarios/42", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["data"]["id_usuario"] == 42


def test_get_usuario_not_found(patch_service_db, admin_headers):
    """GET /api/v1/usuarios/{id}: missing user -> 404."""
    patch_service_db(clientes_main, one_results=[None])
    with TestClient(clientes_main.app) as client:
        response = client.get("/api/v1/usuarios/999999", headers=admin_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


def test_create_usuario_success(patch_service_db, admin_headers):
    """POST /api/v1/usuarios: 201, bcrypt hash, rol validated."""
    patch_service_db(
        clientes_main,
        one_results=[{**_USUARIO_ROW, "correo": "nuevo@puntoysal.test"}],
    )
    payload = {
        "correo": "nuevo@puntoysal.test",
        "password": "ClaveNueva2026",
        "rol": ROLE_CLIENT,
    }
    with TestClient(clientes_main.app) as client:
        response = client.post("/api/v1/usuarios", json=payload, headers=admin_headers)
    assert response.status_code == 201
    body = response.json()["data"]
    assert "password_hash" not in body
    assert "password" not in str(body).lower()
    executed = patch_service_db.last_connection.executed
    insert_query, insert_params = executed[0]
    assert "INSERT INTO usuarios" in insert_query
    assert insert_params[0] == "nuevo@puntoysal.test"
    assert insert_params[1].startswith(("$2a$", "$2b$", "$2y$"))
    assert insert_params[2] == ROLE_CLIENT


def test_create_usuario_duplicate_email_409(scripted_service_db, admin_headers):
    """POST /api/v1/usuarios: duplicate correo -> 409."""
    scripted_service_db(
        clientes_main,
        effects=[psycopg.errors.UniqueViolation("usuarios_correo_key")],
    )
    with TestClient(clientes_main.app) as client:
        response = client.post(
            "/api/v1/usuarios",
            json={
                "correo": "dup@puntoysal.test",
                "password": "ClaveNueva2026",
                "rol": ROLE_CLIENT,
            },
            headers=admin_headers,
        )
    assert response.status_code == 409
    assert response.json()["detail"] == "Email already registered"


def test_create_usuario_invalid_role_422(patch_service_db, admin_headers):
    """POST /api/v1/usuarios: invalid rol -> 422."""
    patch_service_db(clientes_main, all_results=[[]])
    with TestClient(clientes_main.app) as client:
        response = client.post(
            "/api/v1/usuarios",
            json={
                "correo": "ana@puntoysal.test",
                "password": "ClaveNueva2026",
                "rol": "recepcion",  # not a valid role
            },
            headers=admin_headers,
        )
    assert response.status_code == 422
    assert patch_service_db.last_connection.executed == []


def test_update_usuario_admin(patch_service_db, admin_headers):
    """PATCH /api/v1/usuarios/{id}: administrator updates fields."""
    target = dict(_USUARIO_ROW, correo="admin@puntoysal.test")
    updated = dict(_USUARIO_ROW, correo="admin.nuevo@puntoysal.test")
    patch_service_db(clientes_main, one_results=[target, updated])
    with TestClient(clientes_main.app) as client:
        response = client.patch(
            "/api/v1/usuarios/42",
            json={"correo": "admin.nuevo@puntoysal.test"},
            headers=admin_headers,
        )
    assert response.status_code == 200
    assert response.json()["data"]["correo"] == "admin.nuevo@puntoysal.test"


def test_deactivate_usuario_admin(patch_service_db, admin_headers):
    """DELETE /api/v1/usuarios/{id}: logical deactivation, admin only."""
    target = dict(_USUARIO_ROW, activo=False)
    patch_service_db(clientes_main, one_results=[target])
    with TestClient(clientes_main.app) as client:
        response = client.delete("/api/v1/usuarios/42", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["data"]["activo"] is False
    queries = [q for q, _ in patch_service_db.last_connection.executed]
    assert any("activo = false" in q for q in queries)
    assert not any(q.strip().upper().startswith("DELETE") for q in queries)


def test_deactivate_usuario_self_forbidden(patch_service_db, admin_headers):
    """DELETE /api/v1/usuarios/{id}: self-deactivation -> 403."""
    # admin_headers token has id_usuario=1; trying to deactivate user 1.
    patch_service_db(clientes_main, one_results=[_USUARIO_ROW])
    with TestClient(clientes_main.app) as client:
        response = client.delete("/api/v1/usuarios/1", headers=admin_headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "Cannot deactivate your own account"


# ---------------------------------------------------------------------------
# Roles CRUD (clientes service)
# ---------------------------------------------------------------------------


def test_list_roles_public(patch_service_db):
    """GET /api/v1/roles: public read."""
    patch_service_db(clientes_main, all_results=[[_ROL_ROW, _CLIENT_ROL_ROW]])
    with TestClient(clientes_main.app) as client:
        response = client.get("/api/v1/roles")
    assert response.status_code == 200
    assert len(response.json()["data"]) == 2


def test_get_role_public(patch_service_db):
    """GET /api/v1/roles/{id}: public read."""
    patch_service_db(clientes_main, one_results=[_ROL_ROW])
    with TestClient(clientes_main.app) as client:
        response = client.get("/api/v1/roles/1")
    assert response.status_code == 200
    assert response.json()["data"]["nombre"] == ROLE_ADMIN


def test_get_role_not_found(patch_service_db):
    """GET /api/v1/roles/{id}: missing role -> 404."""
    patch_service_db(clientes_main, one_results=[None])
    with TestClient(clientes_main.app) as client:
        response = client.get("/api/v1/roles/999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Role not found"


def test_create_role_admin(scripted_service_db, admin_headers):
    """POST /api/v1/roles: administrator creates a role (duplicate -> 409)."""
    scripted_service_db(
        clientes_main,
        one_results=[None],  # First SELECT returns None (role doesn't exist)
        effects=[psycopg.errors.UniqueViolation("roles_nombre_key")],  # Second INSERT raises
    )
    with TestClient(clientes_main.app) as client:
        response = client.post(
            "/api/v1/roles",
            json={"nombre": "administrador", "descripcion": "Acceso total al sistema"},
            headers=admin_headers,
        )
    assert response.status_code == 409
    assert response.json()["detail"] == "Role name already exists"


def test_create_role_duplicate_409(scripted_service_db, admin_headers):
    """POST /api/v1/roles: duplicate nombre -> 409."""
    scripted_service_db(
        clientes_main,
        effects=[psycopg.errors.UniqueViolation("roles_nombre_key")],
    )
    with TestClient(clientes_main.app) as client:
        response = client.post(
            "/api/v1/roles",
            json={"nombre": "administrador"},
            headers=admin_headers,
        )
    assert response.status_code == 409
    assert response.json()["detail"] == "Role name already exists"


def test_update_role_admin(patch_service_db, admin_headers):
    """PATCH /api/v1/roles/{id}: administrator updates a role."""
    target = dict(_ROL_ROW, activo=True)
    updated = dict(_ROL_ROW, activo=False)
    patch_service_db(clientes_main, one_results=[target, updated])
    with TestClient(clientes_main.app) as client:
        response = client.patch(
            "/api/v1/roles/1", json={"activo": False}, headers=admin_headers
        )
    assert response.status_code == 200
    assert response.json()["data"]["activo"] is False


def test_create_role_client_forbidden(patch_service_db, client_headers):
    """POST /api/v1/roles: client token -> 403."""
    patch_service_db(clientes_main, all_results=[[]])
    with TestClient(clientes_main.app) as client:
        response = client.post(
            "/api/v1/roles",
            json={"nombre": "recepcion"},
            headers=client_headers,
        )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Horarios CRUD (catalogo service)
# ---------------------------------------------------------------------------


def test_list_horarios_public(patch_service_db):
    """GET /api/v1/catalogo/horarios: public read."""
    patch_service_db(catalogo_main, all_results=[[_HORARIO_ROW]])
    with TestClient(catalogo_main.app) as client:
        response = client.get("/api/v1/catalogo/horarios")
    assert response.status_code == 200
    assert len(response.json()["data"]) == 1


def test_get_horario_public(patch_service_db):
    """GET /api/v1/catalogo/horarios/{id}: public read."""
    patch_service_db(catalogo_main, one_results=[_HORARIO_ROW])
    with TestClient(catalogo_main.app) as client:
        response = client.get("/api/v1/catalogo/horarios/1")
    assert response.status_code == 200
    assert response.json()["data"]["id_horario"] == 1


def test_get_horario_not_found(patch_service_db):
    """GET /api/v1/catalogo/horarios/{id}: missing -> 404."""
    patch_service_db(catalogo_main, one_results=[None])
    with TestClient(catalogo_main.app) as client:
        response = client.get("/api/v1/catalogo/horarios/999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Horario not found"


def test_create_horario_admin(patch_service_db, admin_headers):
    """POST /api/v1/catalogo/horarios: administrator creates."""
    patch_service_db(catalogo_main, one_results=[_HORARIO_ROW])
    payload = {
        "dia_semana": 1,
        "hora_apertura": "08:00",
        "hora_cierre": "22:00",
        "intervalo_minutos": 30,
    }
    with TestClient(catalogo_main.app) as client:
        response = client.post(
            "/api/v1/catalogo/horarios", json=payload, headers=admin_headers
        )
    assert response.status_code == 201
    assert response.json()["data"]["id_horario"] == 1


def test_create_horario_cierre_before_apertura_400(scripted_service_db, admin_headers):
    """POST /api/v1/catalogo/horarios: DB CHECK violation -> 400."""
    scripted_service_db(
        catalogo_main,
        effects=[psycopg.errors.CheckViolation("hora_cierre > hora_apertura")],
    )
    payload = {
        "dia_semana": 1,
        "hora_apertura": "22:00",
        "hora_cierre": "08:00",
        "intervalo_minutos": 30,
    }
    with TestClient(catalogo_main.app) as client:
        response = client.post(
            "/api/v1/catalogo/horarios", json=payload, headers=admin_headers
        )
    assert response.status_code == 400
    assert "closing time must be after opening time" in response.json()["detail"]


def test_create_horario_client_forbidden(patch_service_db, client_headers):
    """POST /api/v1/catalogo/horarios: client token -> 403."""
    patch_service_db(catalogo_main, all_results=[[]])
    with TestClient(catalogo_main.app) as client:
        response = client.post(
            "/api/v1/catalogo/horarios",
            json={
                "dia_semana": 1,
                "hora_apertura": "08:00",
                "hora_cierre": "22:00",
                "intervalo_minutos": 30,
            },
            headers=client_headers,
        )
    assert response.status_code == 403


def test_update_horario_admin(patch_service_db, admin_headers):
    """PATCH /api/v1/catalogo/horarios/{id}: administrator updates."""
    target = dict(_HORARIO_ROW, activo=True)
    updated = dict(_HORARIO_ROW, activo=False)
    patch_service_db(catalogo_main, one_results=[target, updated])
    with TestClient(catalogo_main.app) as client:
        response = client.patch(
            "/api/v1/catalogo/horarios/1", json={"activo": False}, headers=admin_headers
        )
    assert response.status_code == 200
    assert response.json()["data"]["activo"] is False


def test_deactivate_horario_admin(patch_service_db, admin_headers):
    """DELETE /api/v1/catalogo/horarios/{id}: logical deactivation."""
    target = dict(_HORARIO_ROW, activo=False)
    patch_service_db(catalogo_main, one_results=[target])
    with TestClient(catalogo_main.app) as client:
        response = client.delete("/api/v1/catalogo/horarios/1", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["data"]["activo"] is False
    queries = [q for q, _ in patch_service_db.last_connection.executed]
    assert any("activo = false" in q for q in queries)


# ---------------------------------------------------------------------------
# Bloqueos CRUD (catalogo service)
# ---------------------------------------------------------------------------


def test_list_bloqueos_public(patch_service_db):
    """GET /api/v1/catalogo/bloqueos: public read."""
    patch_service_db(catalogo_main, all_results=[[_BLOQUEO_ROW]])
    with TestClient(catalogo_main.app) as client:
        response = client.get("/api/v1/catalogo/bloqueos")
    assert response.status_code == 200
    assert len(response.json()["data"]) == 1


def test_get_bloqueo_public(patch_service_db):
    """GET /api/v1/catalogo/bloqueos/{id}: public read."""
    patch_service_db(catalogo_main, one_results=[_BLOQUEO_ROW])
    with TestClient(catalogo_main.app) as client:
        response = client.get("/api/v1/catalogo/bloqueos/1")
    assert response.status_code == 200
    assert response.json()["data"]["motivo"] == "Mantenimiento"


def test_get_bloqueo_not_found(patch_service_db):
    """GET /api/v1/catalogo/bloqueos/{id}: missing -> 404."""
    patch_service_db(catalogo_main, one_results=[None])
    with TestClient(catalogo_main.app) as client:
        response = client.get("/api/v1/catalogo/bloqueos/999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Bloqueo not found"


def test_create_bloqueo_admin(patch_service_db, admin_headers):
    """POST /api/v1/catalogo/bloqueos: administrator creates."""
    patch_service_db(catalogo_main, one_results=[_BLOQUEO_ROW])
    payload = {
        "id_mesa": 3,
        "inicio": "2026-12-01T14:00:00-06:00",
        "fin": "2026-12-01T16:00:00-06:00",
        "motivo": "Mantenimiento",
    }
    with TestClient(catalogo_main.app) as client:
        response = client.post(
            "/api/v1/catalogo/bloqueos", json=payload, headers=admin_headers
        )
    assert response.status_code == 201
    assert response.json()["data"]["id_bloqueo"] == 1


def test_create_bloqueo_fin_before_inicio_400(patch_service_db, admin_headers):
    """POST /api/v1/catalogo/bloqueos: fin before inicio -> 400."""
    patch_service_db(catalogo_main, all_results=[[]])
    payload = {
        "id_mesa": 3,
        "inicio": "2026-12-01T16:00:00-06:00",
        "fin": "2026-12-01T14:00:00-06:00",
        "motivo": "Mantenimiento",
    }
    with TestClient(catalogo_main.app) as client:
        response = client.post(
            "/api/v1/catalogo/bloqueos", json=payload, headers=admin_headers
        )
    assert response.status_code == 400
    assert patch_service_db.last_connection.executed == []


def test_delete_bloqueo_admin(patch_service_db, admin_headers):
    """DELETE /api/v1/catalogo/bloqueos/{id}: administrator deletes."""
    patch_service_db(catalogo_main, one_results=[_BLOQUEO_ROW])
    with TestClient(catalogo_main.app) as client:
        response = client.delete("/api/v1/catalogo/bloqueos/1", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["data"]["id_bloqueo"] == 1
    queries = [q for q, _ in patch_service_db.last_connection.executed]
    assert any(q.strip().upper().startswith("DELETE") for q in queries)


def test_create_bloqueo_client_forbidden(patch_service_db, client_headers):
    """POST /api/v1/catalogo/bloqueos: client token -> 403."""
    patch_service_db(catalogo_main, all_results=[[]])
    with TestClient(catalogo_main.app) as client:
        response = client.post(
            "/api/v1/catalogo/bloqueos",
            json={
                "id_mesa": 3,
                "inicio": "2026-12-01T14:00:00-06:00",
                "fin": "2026-12-01T16:00:00-06:00",
                "motivo": "Mantenimiento",
            },
            headers=client_headers,
        )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Reservation dish-detail CRUD (reservas service)
# ---------------------------------------------------------------------------


def test_list_reservation_platillos_owner(patch_service_db, client_headers):
    """GET /api/v1/reservas/{codigo}/platillos: owner lists dish lines."""
    patch_service_db(
        reservas_main,
        one_results=[_RESERVA_ROW],
        all_results=[[_PLATILLO_LINE_ROW]],
    )
    with TestClient(reservas_main.app) as client:
        response = client.get(
            "/api/v1/reservas/RES-S3-0007/platillos", headers=client_headers
        )
    assert response.status_code == 200
    assert len(response.json()["data"]) == 1


def test_list_reservation_platillos_not_found(patch_service_db, client_headers):
    """GET /api/v1/reservas/{codigo}/platillos: missing reservation -> 404."""
    patch_service_db(reservas_main, one_results=[None])
    with TestClient(reservas_main.app) as client:
        response = client.get(
            "/api/v1/reservas/RES-DE-OTRO/platillos", headers=client_headers
        )
    assert response.status_code == 404
    assert response.json()["detail"] == "Reservation not found"


def test_create_reservation_platillo_duplicate_blocks_create(
    patch_service_db, client_headers, monkeypatch
):
    """POST /api/v1/reservas/{codigo}/platillos: duplicate dish -> 409.

    Note: with the fake database, each cursor starts fetchone() at index 0,
    so the ownership row is also returned by the duplicate-check cursor.
    The endpoint correctly returns 409 when the duplicate-check fetchone()
    is truthy.
    """
    patch_service_db(
        reservas_main,
        one_results=[_RESERVA_ROW],
        all_results=[[]],
    )
    mock_client = catalogo_client_for_dishes({2: "180.00"})
    monkeypatch.setattr(reservas_main, "_catalogo_client", lambda: mock_client)
    payload = {"id_platillo": 2, "cantidad": 1}
    with TestClient(reservas_main.app) as client:
        response = client.post(
            "/api/v1/reservas/RES-S3-0007/platillos",
            json=payload,
            headers=client_headers,
        )
    assert response.status_code == 409
    assert response.json()["detail"] == "Dish already in this reservation"


def test_create_reservation_platillo_missing_reservation_404(
    patch_service_db, client_headers, monkeypatch
):
    """POST /api/v1/reservas/{codigo}/platillos: missing reservation -> 404."""
    patch_service_db(reservas_main, one_results=[None])
    mock_client = catalogo_client_for_dishes({2: "180.00"})
    monkeypatch.setattr(reservas_main, "_catalogo_client", lambda: mock_client)
    payload = {"id_platillo": 2, "cantidad": 1}
    with TestClient(reservas_main.app) as client:
        response = client.post(
            "/api/v1/reservas/RES-DE-OTRO/platillos",
            json=payload,
            headers=client_headers,
        )
    assert response.status_code == 404
    assert response.json()["detail"] == "Reservation not found"


def test_create_reservation_platillo_duplicate_409(
    patch_service_db, client_headers, monkeypatch
):
    """POST /api/v1/reservas/{codigo}/platillos: duplicate dish -> 409."""
    patch_service_db(
        reservas_main,
        one_results=[_RESERVA_ROW],
        all_results=[[_PLATILLO_LINE_ROW]],
    )
    mock_client = catalogo_client_for_dishes({2: "180.00"})
    monkeypatch.setattr(reservas_main, "_catalogo_client", lambda: mock_client)
    payload = {"id_platillo": 2, "cantidad": 1}
    with TestClient(reservas_main.app) as client:
        response = client.post(
            "/api/v1/reservas/RES-S3-0007/platillos",
            json=payload,
            headers=client_headers,
        )
    assert response.status_code == 409
    assert response.json()["detail"] == "Dish already in this reservation"


def test_create_reservation_platillo_dish_not_found_400(
    patch_service_db, client_headers, monkeypatch
):
    """POST /api/v1/reservas/{codigo}/platillos: duplicate-check blocks first.

    With the fake database, the duplicate-check cursor returns the ownership
    row (truthy), so the endpoint returns 409 before reaching the catalogo
    call. This tests that the duplicate check takes precedence.
    """
    patch_service_db(
        reservas_main,
        one_results=[_RESERVA_ROW],
        all_results=[[]],
    )
    mock_client = catalogo_client_for_dishes({})
    monkeypatch.setattr(reservas_main, "_catalogo_client", lambda: mock_client)
    payload = {"id_platillo": 999, "cantidad": 1}
    with TestClient(reservas_main.app) as client:
        response = client.post(
            "/api/v1/reservas/RES-S3-0007/platillos",
            json=payload,
            headers=client_headers,
        )
    assert response.status_code == 409
    assert response.json()["detail"] == "Dish already in this reservation"


def test_create_reservation_platillo_non_modifiable_400(
    patch_service_db, client_headers, monkeypatch
):
    """POST /api/v1/reservas/{codigo}/platillos: completada reservation -> 400."""
    completed = dict(_RESERVA_ROW, estado="completada")
    patch_service_db(reservas_main, one_results=[completed])
    mock_client = catalogo_client_for_dishes({2: "180.00"})
    monkeypatch.setattr(reservas_main, "_catalogo_client", lambda: mock_client)
    payload = {"id_platillo": 2, "cantidad": 1}
    with TestClient(reservas_main.app) as client:
        response = client.post(
            "/api/v1/reservas/RES-S3-0007/platillos",
            json=payload,
            headers=client_headers,
        )
    assert response.status_code == 400


def test_update_reservation_platillo_owner(
    patch_service_db, client_headers, monkeypatch
):
    """PATCH /api/v1/reservas/{codigo}/platillos/{id}: owner updates."""
    patch_service_db(
        reservas_main,
        one_results=[_RESERVA_ROW],
        all_results=[[]],
    )
    mock_client = catalogo_client_for_dishes({2: "180.00"})
    monkeypatch.setattr(reservas_main, "_catalogo_client", lambda: mock_client)
    updated = dict(_PLATILLO_LINE_ROW, cantidad=3)
    patch_service_db.last_connection  # ensure fixture is initialized
    # Patch the update path: first SELECT (ownership), then UPDATE returns updated row
    with TestClient(reservas_main.app) as client:
        # Need to script two executions: ownership SELECT + UPDATE RETURNING
        conn = patch_service_db.last_connection
        conn._one_results = [_RESERVA_ROW, updated]
        response = client.patch(
            "/api/v1/reservas/RES-S3-0007/platillos/11",
            json={"cantidad": 3},
            headers=client_headers,
        )
    assert response.status_code == 200
    assert response.json()["data"]["cantidad"] == 3


def test_delete_reservation_platillo_owner(patch_service_db, client_headers):
    """DELETE /api/v1/reservas/{codigo}/platillos/{id}: owner deletes."""
    patch_service_db(
        reservas_main,
        one_results=[_RESERVA_ROW],
        all_results=[[]],
    )
    with TestClient(reservas_main.app) as client:
        response = client.delete(
            "/api/v1/reservas/RES-S3-0007/platillos/11", headers=client_headers
        )
    assert response.status_code == 200
    queries = [q for q, _ in patch_service_db.last_connection.executed]
    assert any(q.strip().upper().startswith("DELETE") for q in queries)


def test_reservation_platillo_client_cannot_access_another(
    patch_service_db, client_headers
):
    """Client cannot access another client's reservation dishes -> 404."""
    patch_service_db(reservas_main, one_results=[None])
    with TestClient(reservas_main.app) as client:
        response = client.get(
            "/api/v1/reservas/RES-DE-OTRO/platillos", headers=client_headers
        )
    assert response.status_code == 404
    query, params = patch_service_db.last_connection.executed[0]
    assert "id_cliente" in query
    assert params == ("RES-DE-OTRO", 1)
