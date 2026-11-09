"""Pydantic request schemas for the clientes microservice (Sprint 2).

Only business fields are accepted here: ``rol``, ``activo``,
``id_usuario`` and ``password_hash`` are absent on purpose so a client
can never mass-assign protected fields (``extra="forbid"`` rejects any
unknown key with HTTP 422).
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Light e-mail shape check without adding the email-validator dependency
# (structural validation only; deliverability is not checked).
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

# bcrypt only processes the first 72 bytes of a password.
MAX_PASSWORD_LENGTH = 72


class LoginRequest(BaseModel):
    """Credentials for POST /api/v1/auth/login."""

    model_config = ConfigDict(extra="forbid")

    correo: str = Field(min_length=3, max_length=254, pattern=EMAIL_PATTERN)
    password: str = Field(min_length=1, max_length=128)


class ClienteRegistro(BaseModel):
    """Public self-registration body (POST /api/v1/clientes).

    The account is always created with ``rol='cliente'`` and
    ``activo=true`` inside the service; those values are not accepted
    from the request body.
    """

    model_config = ConfigDict(extra="forbid")

    nombre_completo: str = Field(min_length=1, max_length=120)
    correo: str = Field(min_length=3, max_length=254, pattern=EMAIL_PATTERN)
    password: str = Field(min_length=8, max_length=MAX_PASSWORD_LENGTH)
    telefono: str = Field(min_length=1, max_length=30)
    numero_identidad: str | None = Field(
        default=None, min_length=1, max_length=30
    )


class ClienteActualizar(BaseModel):
    """Partial update body (PATCH/PUT /api/v1/clientes/{id}).

    Every field is optional: only the keys actually present in the
    request are updated. ``numero_identidad`` may be cleared (the
    column is nullable); ``nombre_completo``, ``telefono`` and
    ``correo`` reject an explicit ``null`` because they are required
    by the database (``correo`` is also the login identity).
    """

    model_config = ConfigDict(extra="forbid")

    nombre_completo: str | None = Field(
        default=None, min_length=1, max_length=120
    )
    telefono: str | None = Field(default=None, min_length=1, max_length=30)
    correo: str | None = Field(
        default=None, min_length=3, max_length=254, pattern=EMAIL_PATTERN
    )
    numero_identidad: str | None = Field(
        default=None, min_length=1, max_length=30
    )

    @field_validator("nombre_completo", "telefono", "correo", mode="before")
    @classmethod
    def _reject_null(cls, value):
        # Validators only run for explicitly supplied values (defaults
        # are not validated), so this rejects ``null`` in the request
        # while still treating an absent key as "do not update".
        if value is None:
            raise ValueError("must not be null")
        return value
