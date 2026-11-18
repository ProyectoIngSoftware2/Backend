"""Pydantic request schemas for the reservation dish details API (Sprint 3).

Dish lines belong to a reservation. Prices are always sourced from the
catalog service, never from the client.
"""

from pydantic import BaseModel, ConfigDict, Field


class ReservaPlatilloLineCreate(BaseModel):
    """Body of POST /api/v1/reservas/{codigo}/platillos.

    ``id_platillo`` must exist in the catalogo service. ``precio_unitario``
    is NOT accepted from the client — it is resolved from catalogo.
    """

    model_config = ConfigDict(extra="forbid")

    id_platillo: int = Field(gt=0)
    cantidad: int = Field(gt=0, le=50)
    observaciones: str | None = Field(default=None, max_length=500)


class ReservaPlatilloLineActualizar(BaseModel):
    """Partial update body (PATCH/PUT /api/v1/reservas/{codigo}/platillos/{detalleId})."""

    model_config = ConfigDict(extra="forbid")

    cantidad: int | None = Field(default=None, gt=0, le=50)
    observaciones: str | None = Field(default=None, max_length=500)
