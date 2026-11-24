"""Pydantic request schemas for the notificaciones microservice (Sprint 5)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


Destinatario = Literal["cliente", "administrador"]
TipoNotificacion = Literal[
    "reserva_recibida",
    "reserva_aprobada",
    "reserva_confirmada",
    "reserva_rechazada",
    "reserva_cancelada",
    "mesa_asignada",
    "disponibilidad_cambiada",
]


class NotificacionCreate(BaseModel):
    """Body of POST /api/v1/notificaciones."""

    model_config = ConfigDict(extra="forbid")

    id_reserva: int
    destinatario: Destinatario
    tipo: TipoNotificacion
    mensaje: str = Field(min_length=1, max_length=1000)


class NotificacionUpdate(BaseModel):
    """Partial update body (PATCH/PUT /api/v1/notificaciones/{id})."""

    model_config = ConfigDict(extra="forbid")

    leida: bool | None = None
