"""Pydantic request schemas for the horarios y bloqueos API (Sprint 3).

Only business fields are accepted. ``extra="forbid"`` rejects unknown
keys with HTTP 422.
"""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator


class HorarioCreate(BaseModel):
    """Body of POST /api/v1/catalogo/horarios."""

    model_config = ConfigDict(extra="forbid")

    dia_semana: int = Field(ge=1, le=7)
    hora_apertura: str  # "HH:MM" format, validated server-side
    hora_cierre: str    # "HH:MM" format
    intervalo_minutos: int = Field(gt=0, le=1440)
    activo: bool = True

    @field_validator("hora_apertura", "hora_cierre")
    @classmethod
    def _validate_time_format(cls, value):
        try:
            datetime.strptime(value, "%H:%M")
        except ValueError:
            raise ValueError("must be in HH:MM format")
        return value

    @field_validator("hora_cierre")
    @classmethod
    def _validate_cierre_after_apertura(cls, value, info):
        if "hora_apertura" in info.data:
            try:
                apertura = datetime.strptime(info.data["hora_apertura"], "%H:%M")
                cierre = datetime.strptime(value, "%H:%M")
                if cierre <= apertura:
                    raise ValueError("hora_cierre must be after hora_apertura")
            except ValueError:
                pass  # Let format validator handle bad format
        return value


class HorarioActualizar(BaseModel):
    """Partial update body (PATCH/PUT /api/v1/catalogo/horarios/{id})."""

    model_config = ConfigDict(extra="forbid")

    dia_semana: int | None = Field(default=None, ge=1, le=7)
    hora_apertura: str | None = None
    hora_cierre: str | None = None
    intervalo_minutos: int | None = Field(default=None, gt=0, le=1440)
    activo: bool | None = None

    @field_validator("hora_apertura", "hora_cierre")
    @classmethod
    def _validate_time_format(cls, value):
        if value is not None:
            try:
                datetime.strptime(value, "%H:%M")
            except ValueError:
                raise ValueError("must be in HH:MM format")
        return value


class BloqueoCreate(BaseModel):
    """Body of POST /api/v1/catalogo/bloqueos.

    ``id_mesa`` is optional: when omitted, the block applies to all
    tables (general block).
    """

    model_config = ConfigDict(extra="forbid")

    id_mesa: int | None = None
    inicio: datetime
    fin: datetime
    motivo: str = Field(min_length=1, max_length=180)


class BloqueoActualizar(BaseModel):
    """Partial update body (PATCH/PUT /api/v1/catalogo/bloqueos/{id})."""

    model_config = ConfigDict(extra="forbid")

    id_mesa: int | None = None
    inicio: datetime | None = None
    fin: datetime | None = None
    motivo: str | None = Field(default=None, min_length=1, max_length=180)

    @field_validator("fin")
    @classmethod
    def _validate_fin_after_inicio(cls, value, info):
        if value is not None and "inicio" in info.data and info.data["inicio"] is not None:
            if value <= info.data["inicio"]:
                raise ValueError("fin must be after inicio")
        return value
