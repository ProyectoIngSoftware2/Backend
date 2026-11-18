"""Pydantic request schemas for the reservas microservice (Sprint 2).

Only business fields are accepted (``extra="forbid"``): clients can
never supply ``id_cliente`` for somebody else, an administrator or a
status that the database would not allow. Status transitions and mesa
validations are enforced by the existing database triggers, not
duplicated here.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Exact values of the CHECK constraint reservas_estado_check.
EstadoReserva = Literal[
    "pendiente",
    "aprobada",
    "confirmada",
    "rechazada",
    "cancelada",
    "completada",
]


def _require_timezone(value: datetime | None) -> datetime | None:
    """Reject naive datetimes: the column is timestamptz, so an
    explicit UTC offset (e.g. ``-06:00``) is mandatory to avoid
    silently interpreting the server's timezone."""
    if value is not None and value.tzinfo is None:
        raise ValueError(
            "must include a timezone offset, e.g. 2026-12-01T19:00:00-06:00"
        )
    return value


class ReservaPlatilloCreate(BaseModel):
    """One dish line of a new reservation.

    ``precio_unitario`` is intentionally absent: the price always
    comes from the catalogo microservice, never from the client.
    """

    model_config = ConfigDict(extra="forbid")

    id_platillo: int
    cantidad: int = Field(gt=0)
    observaciones: str | None = Field(default=None, max_length=500)


class ReservaCreate(BaseModel):
    """Body of POST /api/v1/reservas.

    ``id_cliente`` is only used by administrators (the service derives
    the client from the JWT for role ``cliente`` and rejects a body
    that tries to assign another customer).
    """

    model_config = ConfigDict(extra="forbid")

    fecha_hora_inicio: datetime
    cantidad_personas: int = Field(gt=0)
    duracion_minutos: int = Field(default=120, ge=15, le=720)
    id_mesa: int | None = None
    observaciones: str | None = Field(default=None, max_length=1000)
    id_cliente: int | None = None
    platillos: list[ReservaPlatilloCreate] = Field(
        default_factory=list, max_length=50
    )

    @field_validator("fecha_hora_inicio")
    @classmethod
    def _tz_required(cls, value: datetime) -> datetime:
        return _require_timezone(value)


class ReservaUpdate(BaseModel):
    """Partial update body (PATCH/PUT /api/v1/reservas/{codigo}).

    Only the keys present in the request are updated. ``estado`` is
    limited by the service to ``cancelada`` for clients; administrators
    may request any transition allowed by the database trigger.
    """

    model_config = ConfigDict(extra="forbid")

    fecha_hora_inicio: datetime | None = None
    duracion_minutos: int | None = Field(default=None, ge=15, le=720)
    cantidad_personas: int | None = Field(default=None, gt=0)
    id_mesa: int | None = None
    observaciones: str | None = Field(default=None, max_length=1000)
    estado: EstadoReserva | None = None

    @field_validator("fecha_hora_inicio")
    @classmethod
    def _tz_required(cls, value: datetime | None) -> datetime | None:
        if value is None:
            # Explicit ``null`` on a non-nullable column.
            raise ValueError("must not be null")
        return _require_timezone(value)

    @field_validator("duracion_minutos", "cantidad_personas", "estado")
    @classmethod
    def _reject_null(cls, value):
        # Only runs when the key is explicitly present in the request
        # (defaults are not validated), so ``null`` on a non-nullable
        # column answers 422 while an absent key means "no change".
        if value is None:
            raise ValueError("must not be null")
        return value
