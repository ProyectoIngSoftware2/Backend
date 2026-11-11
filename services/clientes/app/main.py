"""Clientes microservice.

Responsible for customer-related data and operations using the
``clientes`` table of the approved database design, plus the shared
``usuarios`` account table used by the authentication layer.

Sprint 2 (authentication and authorization):

* ``POST /api/v1/auth/login`` lives in the **auth microservice**
  (``services/auth``), which is the only login provider of the system;
  this service only provisions accounts (see below).
* ``GET  /api/v1/clientes``      - administrator only.
* ``GET  /api/v1/clientes/{id}`` - administrator or the resource owner.
* ``POST /api/v1/clientes``      - public self-registration (always
  creates ``rol='cliente'``; protected fields are never accepted).
* ``PATCH|PUT /api/v1/clientes/{id}`` - administrator or owner, only
  the whitelisted business fields.
* ``DELETE /api/v1/clientes/{id}``     - administrator only, logical
  deactivation (``activo=false`` on ``clientes`` and ``usuarios``).

Password hashes are never returned by any endpoint. Ownership is
enforced inside the SQL statements themselves (``AND id_usuario = %s``)
so a client can never read or modify another client's record (IDOR).
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
from fastapi import Depends, FastAPI, HTTPException
from psycopg.rows import dict_row

from shared.auth import (
    ROLE_ADMIN,
    ROLE_CLIENT,
    CurrentUser,
    get_current_user,
    hash_password,
    require_roles,
)
from shared.database import check_connection, get_connection

from .schemas import ClienteActualizar, ClienteRegistro
from .schemas_usuarios import (
    RolActualizar,
    RolCreate,
    UsuarioActualizar,
    UsuarioCreate,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Clientes Service",
    description=(
        "Customer management microservice for Punto y Sal "
        "(tables: clientes, usuarios). Handles public registration "
        "and customer CRUD; authentication lives in the auth "
        "microservice."
    ),
    version="1.0.0",
)

# Columns returned by the API (never id_usuario, never password_hash).
_CLIENT_COLUMNS = (
    "id_cliente, nombre_completo, numero_identidad, telefono, correo, "
    "fecha_registro, activo"
)

# Whitelist for partial updates: only these request fields may change
# the database, and only to these columns (no rol, activo, id_usuario
# or password_hash can ever be updated through this endpoint).
_UPDATABLE_COLUMNS = {
    "nombre_completo": "nombre_completo",
    "telefono": "telefono",
    "correo": "correo",
    "numero_identidad": "numero_identidad",
}


@app.get("/health")
def health():
    """Liveness/readiness probe: verifies the database connection."""
    if not check_connection():
        raise HTTPException(
            status_code=503,
            detail="Database connection failed",
        )
    return {
        "service": "clientes",
        "status": "ok",
        "database": "connected",
    }



# ---------------------------------------------------------------------------
# Customers (CRUD)
# ---------------------------------------------------------------------------


@app.get("/api/v1/clientes")
def list_customers(
    user: CurrentUser = Depends(require_roles(ROLE_ADMIN)),
):
    """Return all registered customers (administrators only)."""
    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT {_CLIENT_COLUMNS}
                    FROM clientes
                    ORDER BY id_cliente;
                    """
                )
                rows = cur.fetchall()
    except psycopg.OperationalError:
        # Connection-class failures: the database is unreachable.
        logger.exception("Database connection failed while listing customers")
        raise HTTPException(
            status_code=503,
            detail="Database connection failed",
        )
    except Exception:
        # Anything else is an unexpected internal error: log it, but do
        # not tell the client what happened beyond a generic message.
        logger.exception("Unexpected error while listing customers")
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        )
    return {"data": rows}


@app.get("/api/v1/clientes/{id_cliente}")
def get_customer(
    id_cliente: int,
    user: CurrentUser = Depends(get_current_user),
):
    """Return one customer: administrators any, clients only their own.

    For a client the ownership condition is part of the WHERE clause,
    so another customer's record simply does not exist for them (404,
    which also prevents enumerating identifiers).
    """
    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                if user.rol == ROLE_ADMIN:
                    cur.execute(
                        f"""
                        SELECT {_CLIENT_COLUMNS}
                        FROM clientes
                        WHERE id_cliente = %s;
                        """,
                        (id_cliente,),
                    )
                else:
                    cur.execute(
                        f"""
                        SELECT {_CLIENT_COLUMNS}
                        FROM clientes
                        WHERE id_cliente = %s AND id_usuario = %s;
                        """,
                        (id_cliente, user.id_usuario),
                    )
                row = cur.fetchone()
    except psycopg.OperationalError:
        logger.exception(
            "Database connection failed while getting customer %s", id_cliente
        )
        raise HTTPException(
            status_code=503,
            detail="Database connection failed",
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception(
            "Unexpected error while getting customer %s", id_cliente
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        )
    if row is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return {"data": row}


@app.post("/api/v1/clientes", status_code=201)
def register_customer(payload: ClienteRegistro):
    """Public self-registration: creates the account and the profile.

    One transaction writes ``usuarios`` (rol fixed to ``cliente``,
    bcrypt hash) and the linked ``clientes`` row. Duplicate e-mail or
    identity number answer 409. The response contains no credentials.
    """
    # bcrypt processes at most 72 bytes (multi-byte characters count
    # more than once); reject longer secrets with a validation error
    # instead of letting the hashing call fail with a 500.
    if len(payload.password.encode("utf-8")) > 72:
        raise HTTPException(
            status_code=422,
            detail="Password must be at most 72 bytes long",
        )
    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO usuarios (correo, password_hash, rol, activo)
                    VALUES (%s, %s, %s, true)
                    RETURNING id_usuario;
                    """,
                    (
                        payload.correo,
                        hash_password(payload.password),
                        ROLE_CLIENT,
                    ),
                )
                usuario = cur.fetchone()
                cur.execute(
                    f"""
                    INSERT INTO clientes
                        (nombre_completo, telefono, correo,
                         numero_identidad, id_usuario)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING {_CLIENT_COLUMNS};
                    """,
                    (
                        payload.nombre_completo,
                        payload.telefono,
                        payload.correo,
                        payload.numero_identidad,
                        usuario["id_usuario"],
                    ),
                )
                row = cur.fetchone()
    except psycopg.errors.UniqueViolation:
        # usuarios.correo and clientes.numero_identidad are UNIQUE; the
        # transaction is rolled back so no half-created account remains.
        raise HTTPException(
            status_code=409,
            detail="Email or identity number already registered",
        )
    except psycopg.OperationalError:
        logger.exception("Database connection failed while registering")
        raise HTTPException(
            status_code=503,
            detail="Database connection failed",
        )
    except Exception:
        logger.exception("Unexpected error while registering a customer")
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        )
    return {"data": row}


@app.patch("/api/v1/clientes/{id_cliente}")
@app.put("/api/v1/clientes/{id_cliente}")
def update_customer(
    id_cliente: int,
    payload: ClienteActualizar,
    user: CurrentUser = Depends(get_current_user),
):
    """Update permitted fields of a customer (administrator or owner).

    Only the keys present in the body are updated (whitelist in
    ``_UPDATABLE_COLUMNS``); protected fields cannot be supplied at
    all (``extra="forbid"`` answers 422). Changing ``correo`` also
    updates ``usuarios.correo`` inside the same transaction so the
    login identity stays consistent (UNIQUE conflicts answer 409).
    """
    provided = payload.model_fields_set
    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                if user.rol == ROLE_ADMIN:
                    cur.execute(
                        """
                        SELECT id_cliente, id_usuario, correo
                        FROM clientes
                        WHERE id_cliente = %s;
                        """,
                        (id_cliente,),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id_cliente, id_usuario, correo
                        FROM clientes
                        WHERE id_cliente = %s AND id_usuario = %s;
                        """,
                        (id_cliente, user.id_usuario),
                    )
                target = cur.fetchone()
                if target is None:
                    raise HTTPException(
                        status_code=404, detail="Customer not found"
                    )

                updates = {
                    column: getattr(payload, field)
                    for field, column in _UPDATABLE_COLUMNS.items()
                    if field in provided
                }

                if not updates:
                    # Nothing to change: return the current record.
                    cur.execute(
                        f"""
                        SELECT {_CLIENT_COLUMNS}
                        FROM clientes
                        WHERE id_cliente = %s;
                        """,
                        (id_cliente,),
                    )
                    row = cur.fetchone()
                else:
                    if (
                        "correo" in updates
                        and updates["correo"] != target["correo"]
                        and target["id_usuario"] is not None
                    ):
                        cur.execute(
                            """
                            UPDATE usuarios
                               SET correo = %s
                             WHERE id_usuario = %s;
                            """,
                            (updates["correo"], target["id_usuario"]),
                        )
                    # Column names come from the fixed whitelist above,
                    # never from the request body.
                    set_clause = ", ".join(
                        f"{column} = %s" for column in updates
                    )
                    cur.execute(
                        f"""
                        UPDATE clientes
                           SET {set_clause}
                         WHERE id_cliente = %s
                        RETURNING {_CLIENT_COLUMNS};
                        """,
                        (*updates.values(), id_cliente),
                    )
                    row = cur.fetchone()
    except HTTPException:
        raise
    except psycopg.errors.UniqueViolation:
        raise HTTPException(
            status_code=409,
            detail="Email or identity number already registered",
        )
    except psycopg.OperationalError:
        logger.exception(
            "Database connection failed while updating customer %s", id_cliente
        )
        raise HTTPException(
            status_code=503,
            detail="Database connection failed",
        )
    except Exception:
        logger.exception(
            "Unexpected error while updating customer %s", id_cliente
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        )
    return {"data": row}


@app.delete("/api/v1/clientes/{id_cliente}")
def deactivate_customer(
    id_cliente: int,
    user: CurrentUser = Depends(require_roles(ROLE_ADMIN)),
):
    """Logically deactivate a customer (administrators only).

    ``activo=false`` is set on ``clientes`` and, when the profile is
    linked to an account, on ``usuarios`` as well, so the account can
    no longer log in. No row is physically deleted (reservations keep
    their foreign key).
    """
    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE clientes
                       SET activo = false
                     WHERE id_cliente = %s
                    RETURNING {_CLIENT_COLUMNS}, id_usuario;
                    """,
                    (id_cliente,),
                )
                row = cur.fetchone()
                if row is None:
                    raise HTTPException(
                        status_code=404, detail="Customer not found"
                    )
                if row["id_usuario"] is not None:
                    cur.execute(
                        """
                        UPDATE usuarios
                           SET activo = false
                         WHERE id_usuario = %s;
                        """,
                        (row["id_usuario"],),
                    )
    except HTTPException:
        raise
    except psycopg.OperationalError:
        logger.exception(
            "Database connection failed while deactivating customer %s",
            id_cliente,
        )
        raise HTTPException(
            status_code=503,
            detail="Database connection failed",
        )
    except Exception:
        logger.exception(
            "Unexpected error while deactivating customer %s", id_cliente
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        )
    data = {key: value for key, value in row.items() if key != "id_usuario"}
    return {"data": data}


# ---------------------------------------------------------------------------
# Users and roles (Sprint 2 requirement, delivered in Sprint 3).
#
# Administrator-only endpoints for managing internal system accounts
# and roles. Passwords are hashed with bcrypt and never returned.
# ---------------------------------------------------------------------------


@app.get("/api/v1/usuarios")
def list_usuarios(
    user: CurrentUser = Depends(require_roles(ROLE_ADMIN)),
):
    """Return all internal users (administrators only)."""
    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id_usuario, correo, rol, activo, fecha_creacion
                    FROM usuarios
                    ORDER BY id_usuario;
                    """
                )
                rows = cur.fetchall()
    except psycopg.OperationalError:
        logger.exception("Database connection failed while listing users")
        raise HTTPException(status_code=503, detail="Database connection failed")
    except Exception:
        logger.exception("Unexpected error while listing users")
        raise HTTPException(status_code=500, detail="Internal server error")
    return {"data": rows}


@app.get("/api/v1/usuarios/{id_usuario}")
def get_usuario(
    id_usuario: int,
    user: CurrentUser = Depends(require_roles(ROLE_ADMIN)),
):
    """Return one internal user by ID (administrators only)."""
    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id_usuario, correo, rol, activo, fecha_creacion
                    FROM usuarios
                    WHERE id_usuario = %s;
                    """,
                    (id_usuario,),
                )
                row = cur.fetchone()
    except psycopg.OperationalError:
        logger.exception("Database connection failed while getting user %s", id_usuario)
        raise HTTPException(status_code=503, detail="Database connection failed")
    except Exception:
        logger.exception("Unexpected error while getting user %s", id_usuario)
        raise HTTPException(status_code=500, detail="Internal server error")
    if row is None:
        raise HTTPException(status_code=404, detail="User not found")
    return {"data": row}


@app.post("/api/v1/usuarios", status_code=201)
def create_usuario(
    payload: UsuarioCreate,
    user: CurrentUser = Depends(require_roles(ROLE_ADMIN)),
):
    """Create a new internal user (administrators only).

    The password is hashed with bcrypt server-side. The role must be
    one of the valid roles (administrador, cliente). Duplicate emails
    answer 409.
    """
    if payload.rol not in ("administrador", "cliente"):
        raise HTTPException(status_code=422, detail="Invalid role")
    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO usuarios (correo, password_hash, rol, activo)
                    VALUES (%s, %s, %s, true)
                    RETURNING id_usuario, correo, rol, activo, fecha_creacion;
                    """,
                    (
                        payload.correo,
                        hash_password(payload.password),
                        payload.rol,
                    ),
                )
                row = cur.fetchone()
    except psycopg.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="Email already registered")
    except psycopg.OperationalError:
        logger.exception("Database connection failed while creating user")
        raise HTTPException(status_code=503, detail="Database connection failed")
    except Exception:
        logger.exception("Unexpected error while creating user")
        raise HTTPException(status_code=500, detail="Internal server error")
    return {"data": row}


@app.patch("/api/v1/usuarios/{id_usuario}")
@app.put("/api/v1/usuarios/{id_usuario}")
def update_usuario(
    id_usuario: int,
    payload: UsuarioActualizar,
    user: CurrentUser = Depends(require_roles(ROLE_ADMIN)),
):
    """Update permitted fields of an internal user (administrators only).

    Only the keys present in the body are updated. ``rol`` and ``activo``
    are administrator-controlled fields. ``password`` is not updatable
    through this endpoint.
    """
    provided = payload.model_fields_set
    updates = {}
    for field in ("nombre_completo", "correo", "rol", "activo"):
        if field in provided:
            updates[field] = getattr(payload, field)

    if not updates:
        return {"data": {"id_usuario": id_usuario, "message": "No changes"}}

    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id_usuario, correo, rol, activo
                    FROM usuarios
                    WHERE id_usuario = %s;
                    """,
                    (id_usuario,),
                )
                target = cur.fetchone()
                if target is None:
                    raise HTTPException(status_code=404, detail="User not found")

                set_clause = ", ".join(f"{column} = %s" for column in updates)
                cur.execute(
                    f"""
                    UPDATE usuarios
                       SET {set_clause}
                     WHERE id_usuario = %s
                    RETURNING id_usuario, correo, rol, activo, fecha_creacion;
                    """,
                    (*updates.values(), id_usuario),
                )
                row = cur.fetchone()
    except HTTPException:
        raise
    except psycopg.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="Email already registered")
    except psycopg.OperationalError:
        logger.exception("Database connection failed while updating user %s", id_usuario)
        raise HTTPException(status_code=503, detail="Database connection failed")
    except Exception:
        logger.exception("Unexpected error while updating user %s", id_usuario)
        raise HTTPException(status_code=500, detail="Internal server error")
    return {"data": row}


@app.delete("/api/v1/usuarios/{id_usuario}")
def deactivate_usuario(
    id_usuario: int,
    user: CurrentUser = Depends(require_roles(ROLE_ADMIN)),
):
    """Logically deactivate an internal user (administrators only).

    Sets ``activo = false`` so the account can no longer log in.
    Prevents self-deactivation.
    """
    if id_usuario == user.id_usuario:
        raise HTTPException(
            status_code=403, detail="Cannot deactivate your own account"
        )
    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE usuarios
                       SET activo = false
                     WHERE id_usuario = %s
                    RETURNING id_usuario, correo, rol, activo, fecha_creacion;
                    """,
                    (id_usuario,),
                )
                row = cur.fetchone()
    except psycopg.OperationalError:
        logger.exception("Database connection failed while deactivating user %s", id_usuario)
        raise HTTPException(status_code=503, detail="Database connection failed")
    except Exception:
        logger.exception("Unexpected error while deactivating user %s", id_usuario)
        raise HTTPException(status_code=500, detail="Internal server error")
    if row is None:
        raise HTTPException(status_code=404, detail="User not found")
    return {"data": row}


@app.get("/api/v1/roles")
def list_roles():
    """Return all available roles (public read)."""
    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id_rol, nombre, descripcion, activo
                    FROM roles
                    ORDER BY id_rol;
                    """
                )
                rows = cur.fetchall()
    except psycopg.OperationalError:
        logger.exception("Database connection failed while listing roles")
        raise HTTPException(status_code=503, detail="Database connection failed")
    except Exception:
        logger.exception("Unexpected error while listing roles")
        raise HTTPException(status_code=500, detail="Internal server error")
    return {"data": rows}


@app.get("/api/v1/roles/{id_rol}")
def get_role(id_rol: int):
    """Return one role by ID (public read)."""
    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id_rol, nombre, descripcion, activo
                    FROM roles
                    WHERE id_rol = %s;
                    """,
                    (id_rol,),
                )
                row = cur.fetchone()
    except psycopg.OperationalError:
        logger.exception("Database connection failed while getting role %s", id_rol)
        raise HTTPException(status_code=503, detail="Database connection failed")
    except Exception:
        logger.exception("Unexpected error while getting role %s", id_rol)
        raise HTTPException(status_code=500, detail="Internal server error")
    if row is None:
        raise HTTPException(status_code=404, detail="Role not found")
    return {"data": row}


@app.post("/api/v1/roles", status_code=201)
def create_role(
    payload: RolCreate,
    user: CurrentUser = Depends(require_roles(ROLE_ADMIN)),
):
    """Create a new role (administrators only)."""
    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO roles (nombre, descripcion, activo)
                    VALUES (%s, %s, %s)
                    RETURNING id_rol, nombre, descripcion, activo;
                    """,
                    (payload.nombre, payload.descripcion, payload.activo),
                )
                row = cur.fetchone()
    except psycopg.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="Role name already exists")
    except psycopg.OperationalError:
        logger.exception("Database connection failed while creating role")
        raise HTTPException(status_code=503, detail="Database connection failed")
    except Exception:
        logger.exception("Unexpected error while creating role")
        raise HTTPException(status_code=500, detail="Internal server error")
    return {"data": row}


@app.patch("/api/v1/roles/{id_rol}")
@app.put("/api/v1/roles/{id_rol}")
def update_role(
    id_rol: int,
    payload: RolActualizar,
    user: CurrentUser = Depends(require_roles(ROLE_ADMIN)),
):
    """Update a role (administrators only)."""
    provided = payload.model_fields_set
    updates = {}
    for field in ("nombre", "descripcion", "activo"):
        if field in provided:
            updates[field] = getattr(payload, field)

    if not updates:
        return {"data": {"id_rol": id_rol, "message": "No changes"}}

    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id_rol, nombre, descripcion, activo
                    FROM roles
                    WHERE id_rol = %s;
                    """,
                    (id_rol,),
                )
                target = cur.fetchone()
                if target is None:
                    raise HTTPException(status_code=404, detail="Role not found")

                set_clause = ", ".join(f"{column} = %s" for column in updates)
                cur.execute(
                    f"""
                    UPDATE roles
                       SET {set_clause}
                     WHERE id_rol = %s
                    RETURNING id_rol, nombre, descripcion, activo;
                    """,
                    (*updates.values(), id_rol),
                )
                row = cur.fetchone()
    except HTTPException:
        raise
    except psycopg.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="Role name already exists")
    except psycopg.OperationalError:
        logger.exception("Database connection failed while updating role %s", id_rol)
        raise HTTPException(status_code=503, detail="Database connection failed")
    except Exception:
        logger.exception("Unexpected error while updating role %s", id_rol)
        raise HTTPException(status_code=500, detail="Internal server error")
    return {"data": row}

