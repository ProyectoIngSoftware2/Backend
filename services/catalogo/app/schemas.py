"""Pydantic request schemas for the catalogo microservice (Sprint 2).

Write operations are restricted to administrators by the service
dependencies; these schemas define the accepted business fields only
(``extra="forbid"`` rejects unknown keys with HTTP 422, so no protected
column can be mass-assigned).
"""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Exact values of the CHECK constraint mesas_estado_check.
EstadoMesa = Literal["disponible", "mantenimiento"]


class MesaCreate(BaseModel):
    """Body of POST /api/v1/catalogo/mesas."""

    model_config = ConfigDict(extra="forbid")

    numero_mesa: str = Field(min_length=1, max_length=20)
    capacidad: int = Field(gt=0)
    ubicacion: str | None = Field(default=None, max_length=100)
    estado: EstadoMesa = "disponible"
    activa: bool = True


class MesaActualizar(BaseModel):
    """Partial update body (PATCH/PUT /api/v1/catalogo/mesas/{id}).

    Only the keys present in the request are updated;
    ``ubicacion`` may be cleared (nullable column), the rest reject an
    explicit ``null``.
    """

    model_config = ConfigDict(extra="forbid")

    numero_mesa: str | None = Field(default=None, min_length=1, max_length=20)
    capacidad: int | None = Field(default=None, gt=0)
    ubicacion: str | None = Field(default=None, max_length=100)
    estado: EstadoMesa | None = None
    activa: bool | None = None

    @field_validator("numero_mesa", "capacidad", "estado", "activa")
    @classmethod
    def _reject_null(cls, value):
        # Runs only for explicitly supplied keys (defaults are not
        # validated), so ``null`` answers 422 while an absent key
        # means "do not update".
        if value is None:
            raise ValueError("must not be null")
        return value


class PlatilloCreate(BaseModel):
    """Body of POST /api/v1/catalogo/platillos."""

    model_config = ConfigDict(extra="forbid")

    nombre: str = Field(min_length=1, max_length=120)
    descripcion: str | None = Field(default=None, max_length=1000)
    precio: Decimal = Field(ge=0)
    disponible: bool = True


class PlatilloActualizar(BaseModel):
    """Partial update body (PATCH/PUT /api/v1/catalogo/platillos/{id})."""

    model_config = ConfigDict(extra="forbid")

    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    descripcion: str | None = Field(default=None, max_length=1000)
    precio: Decimal | None = Field(default=None, ge=0)
    disponible: bool | None = None

    @field_validator("nombre", "precio", "disponible")
    @classmethod
    def _reject_null(cls, value):
        if value is None:
            raise ValueError("must not be null")
        return value
