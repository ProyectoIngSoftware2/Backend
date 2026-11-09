"""Shared JWT authentication and authorization utilities.

This module is the canonical authentication layer for the Punto y Sal
backend (Sprint 2). Every microservice imports it with the same
``sys.path`` seam used for :mod:`shared.database`, so there is exactly
one authentication mechanism in the system:

* bcrypt password hashing: ``hash_password`` / ``verify_password``;
* JWT access tokens: ``create_access_token`` / ``decode_token``;
* FastAPI dependencies to protect endpoints: ``get_current_user``
  (authentication) and ``require_roles`` (role-based authorization).

Configuration comes from environment variables (or the repository-root
``.env`` file read by pydantic-settings); nothing is ever hardcoded:

* ``JWT_SECRET``         required signing secret (never logged, never
                         returned by any endpoint);
* ``JWT_ALGORITHM``      ``HS256`` (default), ``HS384`` or ``HS512``;
* ``JWT_EXPIRE_MINUTES`` token lifetime in minutes (default 60).

Security rules implemented here:

* the authenticated identity (``sub``) and role come exclusively from
  the signed token — values supplied by the frontend are never trusted;
* malformed, expired or wrongly signed tokens are rejected with 401;
* a valid token with an insufficient role is rejected with 403 (raised
  by ``require_roles``);
* roles are exactly the values allowed by the database CHECK
  constraint on ``usuarios.rol``: ``administrador`` and ``cliente``.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Sequence

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository root, where the optional local .env file is located.
BASE_DIR = Path(__file__).resolve().parent.parent

# Roles as defined by the database (usuarios_rol_check). No other role
# exists in the established project specification.
ROLE_ADMIN = "administrador"
ROLE_CLIENT = "cliente"
VALID_ROLES = (ROLE_ADMIN, ROLE_CLIENT)

# Only symmetric HMAC algorithms are accepted; anything else (notably
# the "none" algorithm) is rejected at configuration time.
_ALLOWED_ALGORITHMS = ("HS256", "HS384", "HS512")

# A signing secret must be long enough to resist brute force.
MIN_SECRET_LENGTH = 32

# 401 responses always challenge the client with the Bearer scheme.
_BEARER_CHALLENGE = {"WWW-Authenticate": "Bearer"}

# Single shared bearer extractor. ``auto_error=False`` keeps us in
# control of the status code: a missing or non-bearer credential must
# be a 401, never the403 that FastAPI's default would return.
_bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="Bearer",
    description=(
        "JWT access token returned by POST /api/v1/auth/login. "
        "Send it as: Authorization: Bearer <access_token>"
    ),
)


class AuthSettings(BaseSettings):
    """Authentication settings loaded from environment / .env."""

    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Lazy singleton: importing this module never requires the secret, so
# services still start and /health still answers when it is missing;
# the first authentication operation then fails closed with a clear
# configuration error instead of silently using a default secret.
_settings: AuthSettings | None = None


def get_auth_settings() -> AuthSettings:
    """Return the validated auth settings (cached after first use)."""
    global _settings
    if _settings is None:
        try:
            settings = AuthSettings()
        except ValidationError as exc:  # JWT_SECRET missing/invalid type
            raise RuntimeError(
                "JWT_SECRET is not configured. Set the JWT_SECRET "
                "environment variable (see .env.example)."
            ) from exc
        if len(settings.JWT_SECRET) < MIN_SECRET_LENGTH:
            raise RuntimeError(
                f"JWT_SECRET must be at least {MIN_SECRET_LENGTH} "
                "characters long (use a long random value, see "
                ".env.example)."
            )
        if settings.JWT_ALGORITHM not in _ALLOWED_ALGORITHMS:
            raise RuntimeError(
                "JWT_ALGORITHM must be one of: "
                + ", ".join(_ALLOWED_ALGORITHMS)
            )
        if not 1 <= settings.JWT_EXPIRE_MINUTES <= 60 * 24 * 7:
            raise RuntimeError(
                "JWT_EXPIRE_MINUTES must be between 1 and 10080 (7 days)."
            )
        _settings = settings
    return _settings


def reset_auth_settings() -> None:
    """Drop the cached settings (used by tests that change the env)."""
    global _settings
    _settings = None


# ---------------------------------------------------------------------------
# Password hashing (bcrypt)
# ---------------------------------------------------------------------------


def hash_password(password: str) -> str:
    """Return a bcrypt hash for ``password``.

    bcrypt hashes never contain the plain password and are safe to
    store in ``usuarios.password_hash``. bcrypt only processes the
    first 72 bytes, so callers must validate the length beforehand
    (the registration schema caps passwords at 72 characters).
    """
    return bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Constant-shape check of ``password`` against ``password_hash``.

    Returns ``False`` for missing or malformed values instead of
    raising, so authentication failures stay indistinguishable.
    """
    if not password or not password_hash:
        return False
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"), password_hash.encode("utf-8")
        )
    except (ValueError, TypeError):
        # Includes bcrypt's ">72 bytes" ValueError and any value that
        # is not a well-formed bcrypt hash (e.g. legacy placeholders).
        return False


# ---------------------------------------------------------------------------
# JWT creation and validation
# ---------------------------------------------------------------------------


def create_access_token(
    *,
    id_usuario: int,
    rol: str,
    correo: str,
    id_cliente: int | None = None,
    id_administrador: int | None = None,
) -> str:
    """Create a signed JWT access token.

    Claims: ``sub`` (stringified user id), ``rol``, ``correo``,
    ``iat`` and ``exp``, plus the profile identifier of the role
    (``id_cliente`` or ``id_administrador``) when the account is
    linked to one. The profile claim is resolved from the database at
    login time and then trusted because the token is signed: it lets
    every microservice enforce ownership on its own tables without
    querying another service's tables (rule F-01). The signing secret
    never leaves the server.
    """
    if rol not in VALID_ROLES:
        raise ValueError(f"Unknown role: {rol}")
    settings = get_auth_settings()
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(int(id_usuario)),
        "rol": rol,
        "correo": correo,
        "iat": int(now.timestamp()),
        "exp": int(
            (
                now
                + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
            ).timestamp()
        ),
    }
    if id_cliente is not None:
        claims["id_cliente"] = int(id_cliente)
    if id_administrador is not None:
        claims["id_administrador"] = int(id_administrador)
    return jwt.encode(claims, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


class TokenError(Exception):
    """Raised when a token cannot be accepted (message is safe to show)."""


def decode_token(token: str) -> dict:
    """Validate ``token`` and return its claims.

    Raises :class:`TokenError` for malformed, expired, wrongly signed
    or incomplete tokens. The signature and expiration are verified by
    PyJWT with the configured algorithm only.
    """
    settings = get_auth_settings()
    try:
        claims = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("Token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("Invalid authentication credentials") from exc

    sub = claims.get("sub")
    rol = claims.get("rol")
    if sub is None or rol not in VALID_ROLES:
        # Refuse tokens that are signed but carry an unusable identity
        # or an unknown role (e.g. forged claims with an old secret).
        raise TokenError("Invalid authentication credentials")
    try:
        int(sub)
    except (TypeError, ValueError) as exc:
        raise TokenError("Invalid authentication credentials") from exc
    for key in ("id_cliente", "id_administrador"):
        value = claims.get(key)
        if value is None:
            continue
        try:
            claims[key] = int(value)
        except (TypeError, ValueError) as exc:
            # A signed token with a malformed profile claim is broken:
            # refuse it instead of guessing.
            raise TokenError("Invalid authentication credentials") from exc
    return claims


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CurrentUser:
    """Authenticated identity extracted from a validated JWT.

    ``id_cliente`` / ``id_administrador`` are the profile identifiers
    recorded in the token at login (``None`` when the account has no
    linked profile for that role).
    """

    id_usuario: int
    rol: str
    correo: str
    id_cliente: int | None = None
    id_administrador: int | None = None


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        _bearer_scheme
    ),
) -> CurrentUser:
    """FastAPI dependency: require a valid bearer JWT (else 401).

    The identity and role come exclusively from the verified token;
    headers or bodies supplied by the client are never trusted.
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers=_BEARER_CHALLENGE,
        )
    try:
        claims = decode_token(credentials.credentials)
    except TokenError as exc:
        raise HTTPException(
            status_code=401,
            detail=str(exc),
            headers=_BEARER_CHALLENGE,
        ) from exc
    return CurrentUser(
        id_usuario=int(claims["sub"]),
        rol=claims["rol"],
        correo=claims.get("correo", ""),
        id_cliente=claims.get("id_cliente"),
        id_administrador=claims.get("id_administrador"),
    )


def require_roles(
    *roles: str,
) -> Callable[[HTTPAuthorizationCredentials | None], CurrentUser]:
    """Dependency factory: require a valid JWT *and* one of ``roles``.

    * missing / invalid / expired token -> 401;
    * valid token with another role      -> 403.

    Usage::

        @app.get("/...")
        def endpoint(user: CurrentUser = Depends(require_roles(ROLE_ADMIN))):
            ...
    """
    unknown = [role for role in roles if role not in VALID_ROLES]
    if unknown:
        raise ValueError(f"Unknown role(s): {', '.join(unknown)}")
    allowed: Sequence[str] = tuple(roles)

    def dependency(
        user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        if user.rol not in allowed:
            raise HTTPException(
                status_code=403,
                detail="Not enough permissions",
            )
        return user

    return dependency
