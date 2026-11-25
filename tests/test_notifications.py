"""Sprint 5 automated tests: notificaciones microservice.

All tests run in-process with faked database access: no network, no
live database writes.
"""

import httpx
import pytest
from fastapi.testclient import TestClient

from services.notificaciones.app import main as notificaciones_main
from services.reservas.app import main as reservas_main
from shared.auth import ROLE_ADMIN, ROLE_CLIENT, create_access_token
from tests.conftest import trigger_error, scripted_service_db, patch_service_db


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

_NOTIFICACION_ROW = {
    "id_notificacion": 1,
    "id_reserva": 7,
    "destinatario": "cliente",
    "tipo": "reserva_recibida",
    "mensaje": "Se recibió una nueva solicitud de reserva: PS-20261225-000001",
    "leida": False,
    "fecha_creacion": "2026-12-25T10:00:00-06:00",
    "fecha_lectura": None,
}


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


def test_notificaciones_health_ok(patch_service_db):
    """The notificaciones service health probe returns ok."""
    patch_service_db(notificaciones_main, healthy=True)
    with TestClient(notificaciones_main.app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "service": "notificaciones",
        "status": "ok",
        "database": "connected",
    }


def test_notificaciones_health_degraded(patch_service_db):
    """The notificaciones service health probe returns 503 when DB is down."""
    patch_service_db(notificaciones_main, healthy=False)
    with TestClient(notificaciones_main.app) as client:
        response = client.get("/health")
    assert response.status_code == 503


# ---------------------------------------------------------------------------
# List notifications
# ---------------------------------------------------------------------------


def test_list_notifications_admin(patch_service_db, admin_headers):
    """Administrator can list all notifications."""
    patch_service_db(notificaciones_main, all_results=[[_NOTIFICACION_ROW]])
    with TestClient(notificaciones_main.app) as client:
        response = client.get(
            "/api/v1/notificaciones", headers=admin_headers
        )
    assert response.status_code == 200
    assert response.json()["data"] == [_NOTIFICACION_ROW]


def test_list_notifications_client(patch_service_db, client_headers):
    """Client can list notifications."""
    patch_service_db(notificaciones_main, all_results=[[_NOTIFICACION_ROW]])
    with TestClient(notificaciones_main.app) as client:
        response = client.get(
            "/api/v1/notificaciones", headers=client_headers
        )
    assert response.status_code == 200


def test_list_notifications_requires_auth(patch_service_db):
    """Listing notifications requires authentication."""
    patch_service_db(notificaciones_main, healthy=True)
    with TestClient(notificaciones_main.app) as client:
        response = client.get("/api/v1/notificaciones")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Get single notification
# ---------------------------------------------------------------------------


def test_get_notification_found(patch_service_db, client_headers):
    """Get a notification by ID returns the notification."""
    patch_service_db(notificaciones_main, one_results=[_NOTIFICACION_ROW])
    with TestClient(notificaciones_main.app) as client:
        response = client.get(
            "/api/v1/notificaciones/1", headers=client_headers
        )
    assert response.status_code == 200
    assert response.json()["data"] == _NOTIFICACION_ROW


def test_get_notification_not_found(patch_service_db, client_headers):
    """Get a non-existent notification returns 404."""
    patch_service_db(notificaciones_main, one_results=[None])
    with TestClient(notificaciones_main.app) as client:
        response = client.get(
            "/api/v1/notificaciones/999", headers=client_headers
        )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Create notification (admin only)
# ---------------------------------------------------------------------------


def test_create_notification_admin(patch_service_db, admin_headers):
    """Administrator can create a notification."""
    patch_service_db(notificaciones_main, one_results=[_NOTIFICACION_ROW])
    with TestClient(notificaciones_main.app) as client:
        response = client.post(
            "/api/v1/notificaciones",
            json={
                "id_reserva": 7,
                "destinatario": "cliente",
                "tipo": "reserva_recibida",
                "mensaje": "Test notification",
            },
            headers=admin_headers,
        )
    assert response.status_code == 201
    assert response.json()["data"] == _NOTIFICACION_ROW


def test_create_notification_client_forbidden(patch_service_db, client_headers):
    """Client cannot create notifications."""
    patch_service_db(notificaciones_main, healthy=True)
    with TestClient(notificaciones_main.app) as client:
        response = client.post(
            "/api/v1/notificaciones",
            json={
                "id_reserva": 7,
                "destinatario": "cliente",
                "tipo": "reserva_recibida",
                "mensaje": "Test notification",
            },
            headers=client_headers,
        )
    assert response.status_code == 403


def test_create_notification_invalid_destinatario(patch_service_db, admin_headers):
    """Invalid destinatario returns 422."""
    patch_service_db(notificaciones_main, healthy=True)
    with TestClient(notificaciones_main.app) as client:
        response = client.post(
            "/api/v1/notificaciones",
            json={
                "id_reserva": 7,
                "destinatario": "invalid",
                "tipo": "reserva_recibida",
                "mensaje": "Test notification",
            },
            headers=admin_headers,
        )
    assert response.status_code == 422


def test_create_notification_invalid_tipo(patch_service_db, admin_headers):
    """Invalid tipo returns 422."""
    patch_service_db(notificaciones_main, healthy=True)
    with TestClient(notificaciones_main.app) as client:
        response = client.post(
            "/api/v1/notificaciones",
            json={
                "id_reserva": 7,
                "destinatario": "cliente",
                "tipo": "invalid_type",
                "mensaje": "Test notification",
            },
            headers=admin_headers,
        )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Update notification (mark as read)
# ---------------------------------------------------------------------------


def test_update_notification_mark_as_read(patch_service_db, client_headers):
    """Client can mark a notification as read."""
    updated = dict(_NOTIFICACION_ROW, leida=True, fecha_lectura="2026-12-25T12:00:00-06:00")
    patch_service_db(notificaciones_main, one_results=[_NOTIFICACION_ROW, updated])
    with TestClient(notificaciones_main.app) as client:
        response = client.patch(
            "/api/v1/notificaciones/1",
            json={"leida": True},
            headers=client_headers,
        )
    assert response.status_code == 200


def test_update_notification_no_changes(patch_service_db, client_headers):
    """PATCH with no leida field returns no changes."""
    patch_service_db(notificaciones_main, one_results=[_NOTIFICACION_ROW])
    with TestClient(notificaciones_main.app) as client:
        response = client.patch(
            "/api/v1/notificaciones/1",
            json={},
            headers=client_headers,
        )
    assert response.status_code == 200
    assert "No changes" in response.json()["data"]["message"]


def test_update_notification_not_found(patch_service_db, client_headers):
    """Update non-existent notification returns 404."""
    patch_service_db(notificaciones_main, one_results=[None])
    with TestClient(notificaciones_main.app) as client:
        response = client.patch(
            "/api/v1/notificaciones/999",
            json={"leida": True},
            headers=client_headers,
        )
    assert response.status_code == 404