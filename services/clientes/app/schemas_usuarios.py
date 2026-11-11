"""Pydantic request schemas for the usuarios y roles API (Sprint 2 requirement, Sprint 3 delivery).

Only business fields are accepted here. Protected columns
(``id_usuario``, ``password_hash``) are never accepted from the request
body (``extra="forbid"`` rejects unknown keys with HTTP 422).
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

VALID_ROLES = ("administrador", "cliente")


class UsuarioCreate(BaseModel):
    """Body of POST /api/v1/usuarios.

    The role is always one of the valid roles and is set explicitly.
    Password is required and hashed server-side.

    Note: ``nombre_completo`` belongs to the ``clientes`` table, not
    ``usuarios``, so it is not accepted through this endpoint.
    """

    model_config = ConfigDict(extra="forbid")

    correo: str = Field(min_length=3, max_length=254, pattern=EMAIL_PATTERN)
    password: str = Field(min_length=8, max_length=72)
    rol: str = Field(min_length=1, max_length=20)


class UsuarioActualizar(BaseModel):
    """Partial update body (PATCH/PUT /api/v1/usuarios/{id}).

    Only the keys present in the request are updated.
    ``rol`` and ``activo`` can only be changed by an administrator.
    ``correo`` changes are validated for uniqueness.

    Note: ``nombre_completo`` belongs to the ``clientes`` table, not
    ``usuarios``, so it is not updatable through this endpoint.
    """

    model_config = ConfigDict(extra="forbid")

    correo: str | None = Field(default=None, min_length=3, max_length=254, pattern=EMAIL_PATTERN)
    rol: str | None = Field(default=None, min_length=1, max_length=20)
    activo: bool | None = None

    @field_validator("rol")
    @classmethod
    def _validate_rol(cls, value):
        if value is not None and value not in VALID_ROLES:
            raise ValueError(f"rol must be one of: {', '.join(VALID_ROLES)}")
        return value


class RolCreate(BaseModel):
    """Body of POST /api/v1/roles.

    Only the roles defined in the database CHECK constraint
    (``administrador``, ``cliente``) are accepted.
    """

    model_config = ConfigDict(extra="forbid")

    nombre: str = Field(min_length=1, max_length=40)
    descripcion: str | None = Field(default=None, max_length=180)
    activo: bool = True

    @field_validator("nombre")
    @classmethod
    def _validate_nombre(cls, value: str) -> str:
        if value not in VALID_ROLES:
            raise ValueError(f"rol must be one of: {', '.join(VALID_ROLES)}")
        return value


class RolActualizar(BaseModel):
    """Partial update body (PATCH/PUT /api/v1/roles/{id})."""

    model_config = ConfigDict(extra="forbid")

    nombre: str | None = Field(default=None, min_length=1, max_length=40)
    descripcion: str | None = Field(default=None, max_length=180)
    activo: bool | None = None
