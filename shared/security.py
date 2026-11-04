"""Shared security layer for Sprint 2 (Option B): passwords, JWT and RBAC.

This module is intentionally standalone: it does NOT import
``shared.database`` (or anything that requires ``DATABASE_URL``), so it can
be imported and unit-tested without a live database connection or a local
``.env`` file. Security settings fall back to safe defaults:

    JWT_SECRET             -> fallback dev secret (a warning is logged)
    JWT_ALGORITHM          -> HS256
    JWT_EXPIRATION_MINUTES -> 60

Values are resolved from environment variables first, then from the
optional repository-root ``.env`` file, then from the defaults above.
Replace ``JWT_SECRET`` before any real deployment; never commit a real
``.env``.

Provided helpers:
    hash_password(password) -> str                 (bcrypt)
    verify_password(plain, hashed) -> bool         (bcrypt)
    create_access_token(data, expires_delta) -> str (PyJWT)
    decode_access_token(token) -> dict             (PyJWT, raises on error)
    require_role(required_role)                    (FastAPI RBAC dependency)
"""

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Repository root, where the optional local .env file is located.
BASE_DIR = Path(__file__).resolve().parent.parent

# Dev-only placeholder secret. Used only when neither an environment
# variable nor a .env entry provides JWT_SECRET.
_DEV_FALLBACK_SECRET = "dev-only-insecure-jwt-secret-change-me"

# BCrypt rejects inputs longer than 72 bytes (silently truncates them,
# which would make long passwords weaker than they look).
_MAX_PASSWORD_BYTES = 72


class SecuritySettings(BaseSettings):
    """JWT settings with fallbacks so tests run without a .env file."""

    JWT_SECRET: str = _DEV_FALLBACK_SECRET
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 60

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = SecuritySettings()

if settings.JWT_SECRET == _DEV_FALLBACK_SECRET:
    logger.warning(
        "JWT_SECRET is not configured; using an insecure development "
        "fallback. Set JWT_SECRET in the environment or .env before "
        "deploying."
    )


# ---------------------------------------------------------------------
# Password hashing (bcrypt)
# ---------------------------------------------------------------------
def hash_password(password: str) -> str:
    """Return a bcrypt hash (with per-password salt) of ``password``.

    Raises:
        ValueError/TypeError: if ``password`` is empty, not a string, or
            longer than 72 bytes (bcrypt limit) — better to fail loudly
            than to store a silently truncated hash.
    """
    if not isinstance(password, str) or not password:
        raise ValueError("password must be a non-empty string")
    if len(password.encode("utf-8")) > _MAX_PASSWORD_BYTES:
        raise ValueError(
            f"password exceeds bcrypt's {_MAX_PASSWORD_BYTES}-byte limit"
        )
    return bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True iff ``plain_password`` matches ``hashed_password``.

    Never raises: a malformed or non-bcrypt stored hash simply does not
    match (returns False), so a bad row can never crash login.
    """
    if not isinstance(plain_password, str) or not isinstance(
        hashed_password, str
    ):
        return False
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------
# JWT creation / validation (PyJWT)
# ---------------------------------------------------------------------
def create_access_token(
    data: dict, expires_delta: timedelta | None = None
) -> str:
    """Return a signed JWT containing ``data`` plus ``exp``/``iat`` claims.

    ``data`` is copied, never mutated. When ``expires_delta`` is None the
    configured ``JWT_EXPIRATION_MINUTES`` is used.
    """
    to_encode = dict(data)
    now = datetime.now(timezone.utc)
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.JWT_EXPIRATION_MINUTES)
    to_encode["iat"] = now
    to_encode["exp"] = now + expires_delta
    return jwt.encode(
        to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM
    )


def decode_access_token(token: str) -> dict:
    """Validate and decode a JWT, returning its payload as a dict.

    Raises:
        jwt.ExpiredSignatureError: the token is expired.
        jwt.PyJWTError: the token is invalid, malformed, tampered with,
            or signed with a different secret/algorithm.
    """
    return jwt.decode(
        token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
    )


# ---------------------------------------------------------------------
# RBAC dependency (FastAPI)
# ---------------------------------------------------------------------
# auto_error=False: we return our own JSON 401 instead of FastAPI's
# plain-text default, keeping the repository's JSON error convention.
_bearer_scheme = HTTPBearer(auto_error=False)


def require_role(required_role: str):
    """Build a FastAPI dependency that enforces a single required role.

    The dependency extracts the ``Authorization: Bearer <jwt>`` header,
    validates it, and returns the decoded payload when the token carries
    ``role == required_role``. Otherwise it raises:

        401 - missing, expired or invalid token
        403 - valid token but insufficient role

    Usage:
        @app.post("/api/v1/thing")
        def create_thing(payload=Depends(require_role("admin"))):
            ...
    """

    def _dependency(
        credentials: HTTPAuthorizationCredentials | None = Depends(
            _bearer_scheme
        ),
    ) -> dict:
        auth_header = {"WWW-Authenticate": "Bearer"}
        if credentials is None or not credentials.credentials:
            raise HTTPException(
                status_code=401,
                detail="Missing bearer token",
                headers=auth_header,
            )
        try:
            payload = decode_access_token(credentials.credentials)
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=401,
                detail="Token has expired",
                headers=auth_header,
            )
        except jwt.PyJWTError:
            raise HTTPException(
                status_code=401,
                detail="Invalid token",
                headers=auth_header,
            )
        if payload.get("role") != required_role:
            raise HTTPException(
                status_code=403,
                detail="Insufficient permissions",
            )
        return payload

    return _dependency
