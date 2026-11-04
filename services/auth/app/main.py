"""Auth microservice (Sprint 2, Option B).

Responsible for authentication only: it validates credentials against
the unified `usuarios` table and issues signed JWT access tokens using
the shared security layer (`shared/security.py`).

Design notes:
    * Login reads ONLY the `usuarios` table (correo + bcrypt
      password_hash + activo + rol); legacy password columns are never
      read here.
    * Failure responses never reveal whether the account exists: unknown
      user, wrong password and disabled account all return the same 401.
    * Read-only Sprint 1 endpoints elsewhere are unaffected; this service
      only exposes POST /api/v1/auth/login plus its health probe.
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
from pydantic import BaseModel
from psycopg.rows import dict_row

from shared.database import check_connection, get_connection
from shared.security import (
    create_access_token,
    settings as security_settings,
    verify_password,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Auth Service",
    description=(
        "Authentication microservice for Punto y Sal: validates "
        "credentials against the usuarios table and issues JWT access "
        "tokens (Sprint 2, Option B)."
    ),
    version="1.0.0",
)


class LoginRequest(BaseModel):
    """Body of POST /api/v1/auth/login."""

    correo: str
    password: str


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

    Error contract (never leaks internals or account existence):
        422 - malformed body (FastAPI/pydantic validation)
        401 - unknown correo, wrong password or inactive account
        503 - database unreachable
        500 - unexpected internal error
    """
    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id_usuario, correo, password_hash, rol, activo
                    FROM usuarios
                    WHERE correo = %s;
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
    # apart from "wrong password" or "disabled account".
    if (
        row is None
        or not row.get("activo")
        or not verify_password(payload.password, row["password_hash"])
    ):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(
        {
            "sub": str(row["id_usuario"]),
            "role": row["rol"],
            "correo": row["correo"],
        }
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": security_settings.JWT_EXPIRATION_MINUTES * 60,
        "role": row["rol"],
    }
