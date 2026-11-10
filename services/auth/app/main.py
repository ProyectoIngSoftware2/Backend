"""Auth microservice: the ONLY authentication provider (Sprint 2).

Responsible for authentication only: it validates credentials against
the unified `usuarios` table and issues signed JWT access tokens using
the shared authentication layer (`shared/auth.py`) — the single
security implementation of the system.

Design notes:
    * Login reads `usuarios` (correo + bcrypt password_hash + activo +
      rol) and the 1:1 profile-link columns created by
      `database/sprint2_auth_schema.sql` (`clientes.id_usuario`,
      `administradores.id_usuario`) so the token can carry the profile
      id (``id_cliente`` / ``id_administrador``) required by every
      ownership rule. Only those link columns are read — never business
      data — and the services never query another service's tables at
      runtime because the profile id travels inside the signed token
      (rule F-01).
    * Failure responses never reveal whether the account exists: unknown
      user, wrong password and disabled account all return the same 401
      ``Invalid credentials`` (uniform anti-enumeration contract).
    * Timing-side-channel mitigation (NOT a claim of constant-time
      behaviour): every attempt — unknown, inactive or active — runs
      exactly one bcrypt verification. Unknown accounts are checked
      against a dummy hash generated ONCE at module import, so response
      time does not reveal whether an e-mail exists.
    * This service exposes POST /api/v1/auth/login plus its health
      probe; registration stays a public business endpoint in the
      clientes microservice (server-forced ``cliente`` role).
"""

import logging
import sys
from pathlib import Path

# Allow this service to run from its own folder while reusing the
# repository's shared/ package (works locally and inside the containers).
for _parent in Path(__file__).resolve().parents:
    if (_parent / "shared" / "database.py").exists():
        if str(_parent) not in sys.path:
            sys.path.insert(0, str(_parent))
        break

import psycopg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from psycopg.rows import dict_row

from shared.auth import (
    create_access_token,
    get_auth_settings,
    hash_password,
    verify_password,
)
from shared.database import check_connection, get_connection

logger = logging.getLogger(__name__)

# Timing-side-channel mitigation (documented, not constant-time):
# generated ONCE at import (never per request), this valid bcrypt hash
# belongs to no account. Unknown e-mails are verified against it so
# every login attempt performs exactly one bcrypt operation and the
# response time cannot be used to enumerate accounts.
_DUMMY_PASSWORD_HASH = hash_password(
    "pys-timing-equalization-not-a-real-account"
)

# Same e-mail shape rule used by the business schemas (validation
# happens before any database access).
_EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

# 401 responses challenge the client with the Bearer scheme.
_BEARER_CHALLENGE = {"WWW-Authenticate": "Bearer"}

app = FastAPI(
    title="Auth Service",
    description=(
        "Authentication microservice for Punto y Sal: validates "
        "credentials against the usuarios table and issues JWT access "
        "tokens with the canonical claims (sub, rol, iat, exp and the "
        "profile id)."
    ),
    version="1.0.0",
)


class LoginRequest(BaseModel):
    """Body of POST /api/v1/auth/login."""

    model_config = ConfigDict(extra="forbid")

    correo: str = Field(min_length=3, max_length=254, pattern=_EMAIL_PATTERN)
    password: str = Field(min_length=1, max_length=128)


@app.get("/health")
def health():
    """Liveness/readiness probe: verifies the database connection."""
    if not check_connection():
        raise HTTPException(
            status_code=503,
            detail="Database connection failed",
        )
    return {
        "service": "auth",
        "status": "ok",
        "database": "connected",
    }


@app.post("/api/v1/auth/login")
def login(payload: LoginRequest):
    """Validate credentials and return a signed JWT access token.

    Success 200: ``access_token``, ``token_type``, ``expires_in``
    (seconds), ``rol``, ``correo``, ``id_usuario`` and the profile id
    (``id_cliente`` / ``id_administrador``, null for the other role).
    The token claims are exactly ``sub``, ``rol``, ``correo``, ``iat``,
    ``exp`` plus the profile id — the canonical structure used by every
    service.

    Error contract (never leaks internals or account existence):
        422 - malformed body (FastAPI/pydantic validation)
        401 - unknown correo, wrong password or inactive account
               (identical ``Invalid credentials`` detail + Bearer
               challenge: accounts cannot be enumerated)
        503 - database unreachable
        500 - unexpected internal error
    """
    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT u.id_usuario, u.correo, u.password_hash,
                           u.rol, u.activo,
                           c.id_cliente, a.id_administrador
                    FROM usuarios u
                    LEFT JOIN clientes c ON c.id_usuario = u.id_usuario
                    LEFT JOIN administradores a
                           ON a.id_usuario = u.id_usuario
                    WHERE u.correo = %s;
                    """,
                    (payload.correo,),
                )
                row = cur.fetchone()
    except psycopg.OperationalError:
        # Connection-class failures: the database is unreachable.
        logger.exception("Database connection failed during login")
        raise HTTPException(
            status_code=503,
            detail="Database connection failed",
        )
    except Exception:
        # Unexpected internal error: log it, never expose the cause.
        logger.exception("Unexpected error during login")
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        )

    # Uniform 401: an attacker must not be able to tell "no such user"
    # apart from "wrong password" or "disabled account". Checked
    # outside the try block so authentication failures are never
    # converted into a 500/503.
    #
    # Timing-side-channel mitigation (not claimed to be constant-time):
    # each attempt runs exactly one bcrypt verification — against the
    # stored hash when the account has one (active or not), otherwise
    # against the module-level dummy hash — so unknown and inactive
    # accounts cost the same password check as a real one.
    stored_hash = row["password_hash"] if row is not None else None
    if stored_hash:
        # Existing account (active or inactive): real verification.
        # For inactive accounts the outcome is deliberately ignored
        # below — they can never log in, but they still burn a check.
        password_ok = verify_password(payload.password, stored_hash)
    else:
        # Unknown e-mail (or unusable stored hash): burn an equal
        # verification against the dummy hash.
        verify_password(payload.password, _DUMMY_PASSWORD_HASH)
        password_ok = False

    if not password_ok or row is None or not row["activo"]:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers=_BEARER_CHALLENGE,
        )

    settings = get_auth_settings()
    token = create_access_token(
        id_usuario=row["id_usuario"],
        rol=row["rol"],
        correo=row["correo"],
        id_cliente=row["id_cliente"],
        id_administrador=row["id_administrador"],
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": settings.JWT_EXPIRE_MINUTES * 60,
        "rol": row["rol"],
        "correo": row["correo"],
        "id_usuario": row["id_usuario"],
        "id_cliente": row["id_cliente"],
        "id_administrador": row["id_administrador"],
    }
