"""Authorization tests (Sprint 2): RBAC matrix, ownership isolation (IDOR)
and mass-assignment protection.

All requests run in-process against the fakes: no network, no database
writes. The ownership assertions also verify that the owner condition is
part of the SQL itself (never only in frontend or URL logic).
"""

from fastapi.testclient import TestClient

from services.catalogo.app import main as catalogo_main
from services.clientes.app import main as clientes_main
from services.reservas.app import main as reservas_main
from shared.auth import ROLE_ADMIN, ROLE_CLIENT

# ---------------------------------------------------------------------------
# Role matrix on admin-only collection endpoints (10, 19, 20)
# ---------------------------------------------------------------------------

ADMIN_ONLY_READS = [
    (clientes_main, "/api/v1/clientes"),
    (reservas_main, "/api/v1/reservas"),
]

ADMIN_ONLY_WRITES = [
    (clientes_main, "delete", "/api/v1/clientes/1"),
    (catalogo_main, "post", "/api/v1/catalogo/mesas"),
    (catalogo_main, "post", "/api/v1/catalogo/platillos"),
    (catalogo_main, "patch", "/api/v1/catalogo/mesas/1"),
    (catalogo_main, "put", "/api/v1/catalogo/platillos/1"),
    (catalogo_main, "delete", "/api/v1/catalogo/mesas/1"),
    (catalogo_main, "delete", "/api/v1/catalogo/platillos/1"),
]

VALID_BODIES = {
    "post": {"numero_mesa": "T-99", "capacidad": 4},
    "patch": {"capacidad": 6},
    "put": {"precio": "150.00"},
}


def test_admin_reads_all_collections(patch_service_db, admin_headers):
    """Scenario 11: the administrator can read every collection."""
    for module, path in ADMIN_ONLY_READS:
        patch_service_db(module, all_results=[[]])
        with TestClient(module.app) as client:
            response = client.get(path, headers=admin_headers)
        assert response.status_code == 200, path
        assert response.json() == {"data": []}


def test_client_forbidden_on_admin_reads(patch_service_db, client_headers):
    """Scenario 10: a client token on an admin endpoint -> 403."""
    for module, path in ADMIN_ONLY_READS:
        patch_service_db(module, all_results=[[]])
        with TestClient(module.app) as client:
            response = client.get(path, headers=client_headers)
        assert response.status_code == 403, path
        assert response.json()["detail"] == "Not enough permissions"


def test_missing_token_on_admin_reads_is_401(patch_service_db):
    """Unauthenticated (19) is 401, distinct from authenticated 403."""
    for module, path in ADMIN_ONLY_READS:
        patch_service_db(module, all_results=[[]])
        with TestClient(module.app) as client:
            response = client.get(path)
        assert response.status_code == 401, path
        assert response.headers.get("www-authenticate") == "Bearer"


def test_client_forbidden_on_admin_writes(patch_service_db, client_headers):
    """Scenario 10: catalog/client mutations are closed to clients."""
    for module, method, path in ADMIN_ONLY_WRITES:
        patch_service_db(module, one_results=[None], all_results=[[]])
        with TestClient(module.app) as client:
            kwargs = {"headers": client_headers}
            if method in ("post", "patch", "put"):
                kwargs["json"] = VALID_BODIES[method]
            response = getattr(client, method)(path, **kwargs)
        assert response.status_code == 403, f"{method.upper()} {path}"
        assert response.json()["detail"] == "Not enough permissions"


def test_missing_token_on_admin_writes_is_401(patch_service_db):
    """A write without credentials fails at 401 before touching data."""
    for module, method, path in ADMIN_ONLY_WRITES:
        patch_service_db(module, one_results=[None], all_results=[[]])
        with TestClient(module.app) as client:
            kwargs = {}
            if method in ("post", "patch", "put"):
                kwargs["json"] = VALID_BODIES[method]
            response = getattr(client, method)(path, **kwargs)
        assert response.status_code == 401, f"{method.upper()} {path}"


def test_catalog_reads_stay_public(patch_service_db):
    """Sprint 1 behaviour preserved: catalog GETs need no token."""
    for path in (
        "/api/v1/catalogo/mesas",
        "/api/v1/catalogo/platillos",
        "/api/v1/catalogo/mesas/1",
        "/api/v1/catalogo/platillos/1",
    ):
        patch_service_db(
            catalogo_main, one_results=[{"id_mesa": 1}], all_results=[[]]
        )
        with TestClient(catalogo_main.app) as client:
            response = client.get(path)
        assert response.status_code == 200, path


# ---------------------------------------------------------------------------
# Client data isolation / IDOR (8, 9)
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
    "codigo_reserva": "RES-OWN-0007",
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


def test_client_reads_own_profile(patch_service_db, client_headers):
    """A client can read its own profile (owner path)."""
    patch_service_db(clientes_main, one_results=[_CLIENT_ROW])
    with TestClient(clientes_main.app) as client:
        response = client.get("/api/v1/clientes/1", headers=client_headers)
    assert response.status_code == 200
    assert response.json()["data"]["id_cliente"] == 1

    # Ownership is inside the SQL WHERE clause with bound parameters.
    query, params = patch_service_db.last_connection.executed[0]
    assert "id_usuario" in query
    assert params == (1, 2), "id_cliente and id_usuario must be bound"


def test_client_cannot_read_another_profile(patch_service_db, client_headers):
    """Scenario 8: another client's profile -> 404 (not 403: no IDOR)."""
    patch_service_db(clientes_main, one_results=[None])
    with TestClient(clientes_main.app) as client:
        response = client.get("/api/v1/clientes/999", headers=client_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Customer not found"
    query, params = patch_service_db.last_connection.executed[0]
    assert "id_usuario" in query, "the owner condition must be in the SQL"
    assert params == (999, 2)


def test_admin_reads_any_profile(patch_service_db, admin_headers):
    """Scenario 11: the administrator reads any profile by id."""
    patch_service_db(clientes_main, one_results=[_CLIENT_ROW])
    with TestClient(clientes_main.app) as client:
        response = client.get("/api/v1/clientes/1", headers=admin_headers)
    assert response.status_code == 200
    query, params = patch_service_db.last_connection.executed[0]
    assert "id_usuario" not in query, "admin query is not owner-scoped"
    assert params == (1,)


def test_client_reads_own_reservation(patch_service_db, client_headers):
    """A client reads its own reservation with dishes and history."""
    patch_service_db(
        reservas_main,
        one_results=[_RESERVA_ROW],
        all_results=[[], []],
    )
    with TestClient(reservas_main.app) as client:
        response = client.get(
            "/api/v1/reservas/RES-OWN-0007", headers=client_headers
        )
    assert response.status_code == 200
    query, params = patch_service_db.last_connection.executed[0]
    assert "id_cliente" in query
    assert params == ("RES-OWN-0007", 1), "owner id comes from the JWT"


def test_client_cannot_read_another_reservation(patch_service_db, client_headers):
    """Scenario 9: another client's reservation -> 404 (anti-IDOR)."""
    patch_service_db(reservas_main, one_results=[None])
    with TestClient(reservas_main.app) as client:
        response = client.get(
            "/api/v1/reservas/RES-DE-OTRO", headers=client_headers
        )
    assert response.status_code == 404
    assert response.json()["detail"] == "Reservation not found"
    query, params = patch_service_db.last_connection.executed[0]
    assert "id_cliente" in query, "the owner condition must be in the SQL"
    assert params == ("RES-DE-OTRO", 1)


def test_client_without_profile_owns_nothing(patch_service_db, token_for):
    """A client token without id_cliente claim cannot match any record."""
    headers = {"Authorization": f"Bearer {token_for(30, ROLE_CLIENT)}"}
    patch_service_db(reservas_main, one_results=[None])
    with TestClient(reservas_main.app) as client:
        response = client.get("/api/v1/reservas/RES-X", headers=headers)
    assert response.status_code == 404
    # No query at all: ownership is impossible without a profile id.
    assert patch_service_db.last_connection.executed == []


def test_admin_can_cancel_any_reservation(patch_service_db, admin_headers):
    """Scenario 11/12: administrator acts on any reservation (logical)."""
    updated = dict(_RESERVA_ROW, estado="cancelada")
    patch_service_db(reservas_main, one_results=[_RESERVA_ROW, updated])
    with TestClient(reservas_main.app) as client:
        response = client.delete(
            "/api/v1/reservas/RES-OWN-0007", headers=admin_headers
        )
    assert response.status_code == 200
    assert response.json()["data"]["estado"] == "cancelada"
    # SELECT (unscoped) + logical UPDATE, never a physical DELETE.
    queries = [q for q, _ in patch_service_db.last_connection.executed]
    assert "id_cliente" not in queries[0]
    assert "estado = 'cancelada'" in queries[1] or "estado" in queries[1]
    assert not any(q.strip().upper().startswith("DELETE") for q in queries)


def test_client_cannot_cancel_another_reservation(patch_service_db, client_headers):
    """Ownership applies to the cancellation path too (404)."""
    patch_service_db(reservas_main, one_results=[None])
    with TestClient(reservas_main.app) as client:
        response = client.delete(
            "/api/v1/reservas/RES-DE-OTRO", headers=client_headers
        )
    assert response.status_code == 404
    query, params = patch_service_db.last_connection.executed[0]
    assert "id_cliente" in query
    assert params == ("RES-DE-OTRO", 1)


# ---------------------------------------------------------------------------
# Client reservation rules (13, 14)
# ---------------------------------------------------------------------------


def test_client_cannot_create_for_another_customer(patch_service_db, client_headers):
    """A client supplying another id_cliente is rejected with 403."""
    patch_service_db(reservas_main, all_results=[[]])
    with TestClient(reservas_main.app) as client:
        response = client.post(
            "/api/v1/reservas",
            json={
                "fecha_hora_inicio": "2027-06-01T19:00:00-06:00",
                "cantidad_personas": 2,
                "id_cliente": 999,
            },
            headers=client_headers,
        )
    assert response.status_code == 403
    assert patch_service_db.last_connection.executed == [], "no write must run"


def test_client_may_only_request_cancellation(patch_service_db, client_headers):
    """Scenario 14: clients can set estado='cancelada' and nothing else."""
    patch_service_db(reservas_main, one_results=[_RESERVA_ROW, _RESERVA_ROW])
    with TestClient(reservas_main.app) as client:
        response = client.patch(
            "/api/v1/reservas/RES-OWN-0007",
            json={"estado": "aprobada"},
            headers=client_headers,
        )
    assert response.status_code == 403
    assert response.json()["detail"] == "Only cancellation is allowed for clients"
    assert patch_service_db.last_connection.executed == [], "no write must run"


def test_client_cancellation_is_allowed(patch_service_db, client_headers):
    """The allowed client transition reaches the database (trigger decides)."""
    cancelada = dict(_RESERVA_ROW, estado="cancelada")
    patch_service_db(reservas_main, one_results=[_RESERVA_ROW, cancelada])
    with TestClient(reservas_main.app) as client:
        response = client.patch(
            "/api/v1/reservas/RES-OWN-0007",
            json={"estado": "cancelada"},
            headers=client_headers,
        )
    assert response.status_code == 200
    assert response.json()["data"]["estado"] == "cancelada"


def test_client_patch_of_another_reservation_is_404(patch_service_db, client_headers):
    """Ownership also holds on the update path."""
    patch_service_db(reservas_main, one_results=[None])
    with TestClient(reservas_main.app) as client:
        response = client.patch(
            "/api/v1/reservas/RES-DE-OTRO",
            json={"estado": "cancelada"},
            headers=client_headers,
        )
    assert response.status_code == 404
    query, params = patch_service_db.last_connection.executed[0]
    assert "id_cliente" in query


def test_admin_status_change_reaches_database(patch_service_db, admin_headers):
    """Scenario 12/14: an administrator may request any transition."""
    aprobada = dict(_RESERVA_ROW, estado="aprobada", id_administrador=1)
    patch_service_db(reservas_main, one_results=[_RESERVA_ROW, aprobada])
    with TestClient(reservas_main.app) as client:
        response = client.patch(
            "/api/v1/reservas/RES-OWN-0007",
            json={"estado": "aprobada"},
            headers=admin_headers,
        )
    assert response.status_code == 200
    assert response.json()["data"]["estado"] == "aprobada"
    # The acting administrator is stamped on the row (from the JWT).
    update_query, update_params = patch_service_db.last_connection.executed[-1]
    assert "id_administrador" in update_query
    assert 1 in update_params


# ---------------------------------------------------------------------------
# Mass assignment (6, 11)
# ---------------------------------------------------------------------------


def test_registration_cannot_assign_role_or_protected_fields(patch_service_db):
    """rol/activo/id_usuario/password_hash are not accepted at all."""
    for payload in (
        {"nombre_completo": "Ana", "correo": "a@b.com", "password": "12345678",
         "telefono": "9999", "rol": ROLE_ADMIN},
        {"nombre_completo": "Ana", "correo": "a@b.com", "password": "12345678",
         "telefono": "9999", "activo": False},
        {"nombre_completo": "Ana", "correo": "a@b.com", "password": "12345678",
         "telefono": "9999", "id_usuario": 1},
    ):
        patch_service_db(clientes_main, all_results=[[]])
        with TestClient(clientes_main.app) as client:
            response = client.post("/api/v1/clientes", json=payload)
        assert response.status_code == 422, payload
        assert patch_service_db.last_connection.executed == []


def test_update_cannot_touch_protected_fields(patch_service_db, client_headers):
    """PATCH with rol/activo/password_hash is a 422 (extra=forbid)."""
    for payload in (
        {"rol": ROLE_ADMIN},
        {"activo": True},
        {"password_hash": "$2b$12$whatever"},
        {"id_usuario": 1},
    ):
        patch_service_db(clientes_main, one_results=[_CLIENT_ROW])
        with TestClient(clientes_main.app) as client:
            response = client.patch(
                "/api/v1/clientes/1", json=payload, headers=client_headers
            )
        assert response.status_code == 422, payload


def test_reservation_create_rejects_protected_fields(
    patch_service_db, client_headers
):
    """estado/codigo/id_cliente-of-others cannot be injected on create."""
    patch_service_db(reservas_main, all_results=[[]])
    with TestClient(reservas_main.app) as client:
        response = client.post(
            "/api/v1/reservas",
            json={
                "fecha_hora_inicio": "2027-06-01T19:00:00-06:00",
                "cantidad_personas": 2,
                "estado": "aprobada",
            },
            headers=client_headers,
        )
    assert response.status_code == 422


def test_catalog_write_rejects_primary_key_injection(patch_service_db, admin_headers):
    """The client can never choose the primary key of a new record."""
    patch_service_db(catalogo_main, all_results=[[]])
    with TestClient(catalogo_main.app) as client:
        response = client.post(
            "/api/v1/catalogo/mesas",
            json={"id_mesa": 1, "numero_mesa": "T-100", "capacidad": 4},
            headers=admin_headers,
        )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Error semantics (18)
# ---------------------------------------------------------------------------


def test_status_codes_are_distinct_per_failure(
    patch_service_db, admin_headers, client_headers
):
    """401 (no/invalid token), 403 (role), 404 (missing resource)."""
    patch_service_db(clientes_main, one_results=[None], all_results=[[]])
    with TestClient(clientes_main.app) as client:
        unauthenticated = client.get("/api/v1/clientes")
        invalid = client.get(
            "/api/v1/clientes",
            headers={"Authorization": "Bearer basura"},
        )
        forbidden = client.get("/api/v1/clientes", headers=client_headers)
        missing = client.get(
            "/api/v1/clientes/999999", headers=admin_headers
        )
    assert unauthenticated.status_code == 401
    assert invalid.status_code == 401
    assert forbidden.status_code == 403
    assert missing.status_code == 404
