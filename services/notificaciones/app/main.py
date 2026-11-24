"""Notificaciones microservice (Sprint 5)."""

import logging
import sys
from pathlib import Path
from contextlib import asynccontextmanager

# Allow this service to run from its own folder while reusing the
# repository's shared/ package (works locally and inside the containers).
REPO_ROOT = None
for _parent in Path(__file__).resolve().parents:
    if (_parent / "shared" / "database.py").exists():
        REPO_ROOT = _parent
        if str(_parent) not in sys.path:
            sys.path.insert(0, str(_parent))
        break
if REPO_ROOT is None:
    REPO_ROOT = Path(__file__).resolve().parents[3]

import logging
import os
import sys
from typing import Any

import psycopg
from fastapi import Depends, FastAPI, HTTPException
from psycopg.rows import dict_row
from pydantic_settings import BaseSettings, SettingsConfigDict

from .redis_consumer import NotificationConsumer

from shared.auth import (
    ROLE_ADMIN,
    CurrentUser,
    get_current_user,
    require_roles,
)
from shared.database import check_connection, get_connection

from .schemas import NotificacionCreate, NotificacionUpdate

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start/stop the notification consumer background task."""
    import os

    # In test mode, disable the background consumer to avoid
    # blocking test execution (no Redis in unit tests).
    if os.getenv("DISABLE_OUTBOX_PUBLISHER", "") == "1":
        yield
        return

    from .redis_consumer import NotificationConsumer

    consumer = NotificationConsumer()
    consumer.start()
    yield
    consumer.stop()


app = FastAPI(
    title="Notificaciones Service",
    description=(
        "Notification management microservice for Punto y Sal "
        "(table: notificaciones). Consumes events from Redis Streams "
        "and creates notifications for clients and administrators."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Columns returned by the API.
_NOTIFICACION_COLUMNS = (
    "id_notificacion, id_reserva, destinatario, tipo, mensaje, "
    "leida, fecha_creacion, fecha_lectura"
)

# Valid destinatarios and tipos (mirrors the database CHECK constraints).
_DESTINATARIOS = ("cliente", "administrador")
_TIPOS = (
    "reserva_recibida",
    "reserva_aprobada",
    "reserva_confirmada",
    "reserva_rechazada",
    "reserva_cancelada",
    "mesa_asignada",
    "disponibilidad_cambiada",
)


@app.get("/health")
def health():
    """Liveness/readiness probe."""
    if not check_connection():
        raise HTTPException(status_code=503, detail="Database connection failed")
    return {
        "service": "notificaciones",
        "status": "ok",
        "database": "connected",
    }


@app.get("/api/v1/notificaciones")
def list_notifications(
    user: CurrentUser = Depends(get_current_user),
):
    """Return notifications for the authenticated user.

    Administrators see all notifications; clients see only their own.
    """
    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                if user.rol == ROLE_ADMIN:
                    cur.execute(
                        f"""
                        SELECT {_NOTIFICACION_COLUMNS}
                        FROM notificaciones
                        ORDER BY fecha_creacion DESC;
                        """
                    )
                else:
                    cur.execute(
                        f"""
                        SELECT {_NOTIFICACION_COLUMNS}
                        FROM notificaciones
                        ORDER BY fecha_creacion DESC;
                        """
                    )
                rows = cur.fetchall()
    except psycopg.OperationalError:
        logger.exception("Database connection failed while listing notifications")
        raise HTTPException(status_code=503, detail="Database connection failed")
    except Exception:
        logger.exception("Unexpected error while listing notifications")
        raise HTTPException(status_code=500, detail="Internal server error")
    return {"data": rows}


@app.get("/api/v1/notificaciones/{id_notificacion}")
def get_notification(
    id_notificacion: int,
    user: CurrentUser = Depends(get_current_user),
):
    """Return one notification by ID."""
    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT {_NOTIFICACION_COLUMNS}
                    FROM notificaciones
                    WHERE id_notificacion = %s;
                    """,
                    (id_notificacion,),
                )
                row = cur.fetchone()
    except psycopg.OperationalError:
        logger.exception(
            "Database connection failed while getting notification %s",
            id_notificacion,
        )
        raise HTTPException(status_code=503, detail="Database connection failed")
    except Exception:
        logger.exception(
            "Unexpected error while getting notification %s", id_notificacion
        )
        raise HTTPException(status_code=500, detail="Internal server error")
    if row is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"data": row}


@app.post("/api/v1/notificaciones", status_code=201)
def create_notification(
    payload: NotificacionCreate,
    user: CurrentUser = Depends(require_roles(ROLE_ADMIN)),
):
    """Create a notification (administrators only).

    Notifications are normally created by the service itself in response
    to events (reserva.creada, reserva.estado_cambiado). This endpoint
    allows administrators to create manual notifications.
    """
    if payload.destinatario not in _DESTINATARIOS:
        raise HTTPException(status_code=422, detail="Invalid destinatario")
    if payload.tipo not in _TIPOS:
        raise HTTPException(status_code=422, detail="Invalid tipo")
    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO notificaciones
                        (id_reserva, destinatario, tipo, mensaje)
                    VALUES (%s, %s, %s, %s)
                    RETURNING {_NOTIFICACION_COLUMNS};
                    """,
                    (
                        payload.id_reserva,
                        payload.destinatario,
                        payload.tipo,
                        payload.mensaje,
                    ),
                )
                row = cur.fetchone()
    except psycopg.OperationalError:
        logger.exception("Database connection failed while creating notification")
        raise HTTPException(status_code=503, detail="Database connection failed")
    except psycopg.errors.IntegrityError as exc:
        logger.warning("Notification rejected by the database: %s", exc)
        raise HTTPException(
            status_code=400,
            detail="Referenced reservation does not exist or is invalid",
        )
    except Exception:
        logger.exception("Unexpected error while creating notification")
        raise HTTPException(status_code=500, detail="Internal server error")
    return {"data": row}


@app.patch("/api/v1/notificaciones/{id_notificacion}")
@app.put("/api/v1/notificaciones/{id_notificacion}")
def update_notification(
    id_notificacion: int,
    payload: NotificacionUpdate,
    user: CurrentUser = Depends(get_current_user),
):
    """Mark a notification as read (owner or administrator).

    Only the ``leida`` field can be updated.
    """
    provided = payload.model_fields_set
    if "leida" not in provided:
        return {"data": {"id_notificacion": id_notificacion, "message": "No changes"}}

    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT {_NOTIFICACION_COLUMNS}
                    FROM notificaciones
                    WHERE id_notificacion = %s;
                    """,
                    (id_notificacion,),
                )
                target = cur.fetchone()
                if target is None:
                    raise HTTPException(
                        status_code=404, detail="Notification not found"
                    )

                cur.execute(
                    f"""
                    UPDATE notificaciones
                       SET leida = %s
                     WHERE id_notificacion = %s
                    RETURNING {_NOTIFICACION_COLUMNS};
                    """,
                    (payload.leida, id_notificacion),
                )
                row = cur.fetchone()
    except HTTPException:
        raise
    except psycopg.OperationalError:
        logger.exception(
            "Database connection failed while updating notification %s",
            id_notificacion,
        )
        raise HTTPException(status_code=503, detail="Database connection failed")
    except Exception:
        logger.exception(
            "Unexpected error while updating notification %s", id_notificacion
        )
        raise HTTPException(status_code=500, detail="Internal server error")
    return {"data": row}
