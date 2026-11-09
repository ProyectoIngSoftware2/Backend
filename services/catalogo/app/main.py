"""Catalogo microservice.

Responsible for restaurant resources and menu information using the
`mesas` (restaurant tables) and `platillos` (menu items) tables of the
approved database design.

Sprint 2 (authentication and authorization):

* reads (``GET``) stay public so the menu and the tables can be
  browsed without a token (existing behaviour preserved);
* every write operation (``POST``/``PATCH``/``PUT``/``DELETE``) is
  restricted to the ``administrador`` role: clients receive 401
  without a token and 403 with a token of insufficient permissions;
* deletions are logical (``activa=false`` / ``disponible=false``) so
  reservations that reference the resource keep their foreign keys.
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

from shared.auth import ROLE_ADMIN, CurrentUser, require_roles
from shared.database import check_connection, get_connection

from .schemas import (
    MesaActualizar,
    MesaCreate,
    PlatilloActualizar,
    PlatilloCreate,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Catalogo Service",
    description=(
        "Restaurant resources and menu microservice for Punto y Sal "
        "(tables: mesas, platillos). Reads are public; writes require "
        "an administrator JWT."
    ),
    version="1.0.0",
)

# Columns returned by the API.
_MESA_COLUMNS = "id_mesa, numero_mesa, capacidad, ubicacion, estado, activa"
_PLATILLO_COLUMNS = (
    "id_platillo, nombre, descripcion, precio, disponible, fecha_creacion"
)

# Whitelists for partial updates: request field -> column (fixed in
# code, never taken from the request body).
_MESA_UPDATABLE = {
    "numero_mesa": "numero_mesa",
    "capacidad": "capacidad",
    "ubicacion": "ubicacion",
    "estado": "estado",
    "activa": "activa",
}
_PLATILLO_UPDATABLE = {
    "nombre": "nombre",
    "descripcion": "descripcion",
    "precio": "precio",
    "disponible": "disponible",
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
        "service": "catalogo",
        "status": "ok",
        "database": "connected",
    }


# ---------------------------------------------------------------------------
# Reads (public: preserved from Sprint 1)
# ---------------------------------------------------------------------------


@app.get("/api/v1/catalogo/mesas")
def list_tables():
    """Return all restaurant tables with their status (read-only)."""
    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id_mesa, numero_mesa, capacidad, ubicacion,
                           estado, activa
                    FROM mesas
                    ORDER BY numero_mesa;
                    """
                )
                rows = cur.fetchall()
    except psycopg.OperationalError:
        logger.exception("Database connection failed while listing tables")
        raise HTTPException(
            status_code=503,
            detail="Database connection failed",
        )
    except Exception:
        logger.exception("Unexpected error while listing tables")
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        )
    return {"data": rows}


@app.get("/api/v1/catalogo/mesas/{id_mesa}")
def get_table(id_mesa: int):
    """Return one restaurant table by identifier (read-only)."""
    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id_mesa, numero_mesa, capacidad, ubicacion,
                           estado, activa
                    FROM mesas
                    WHERE id_mesa = %s;
                    """,
                    (id_mesa,),
                )
                row = cur.fetchone()
    except psycopg.OperationalError:
        logger.exception("Database connection failed while getting table %s", id_mesa)
        raise HTTPException(
            status_code=503,
            detail="Database connection failed",
        )
    except Exception:
        logger.exception("Unexpected error while getting table %s", id_mesa)
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        )
    if row is None:
        raise HTTPException(status_code=404, detail="Table not found")
    return {"data": row}


@app.get("/api/v1/catalogo/platillos")
def list_dishes():
    """Return all menu items with their availability (read-only)."""
    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id_platillo, nombre, descripcion, precio,
                           disponible, fecha_creacion
                    FROM platillos
                    ORDER BY id_platillo;
                    """
                )
                rows = cur.fetchall()
    except psycopg.OperationalError:
        logger.exception("Database connection failed while listing dishes")
        raise HTTPException(
            status_code=503,
            detail="Database connection failed",
        )
    except Exception:
        logger.exception("Unexpected error while listing dishes")
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        )
    return {"data": rows}


@app.get("/api/v1/catalogo/platillos/{id_platillo}")
def get_dish(id_platillo: int):
    """Return one menu item by identifier (read-only)."""
    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id_platillo, nombre, descripcion, precio,
                           disponible, fecha_creacion
                    FROM platillos
                    WHERE id_platillo = %s;
                    """,
                    (id_platillo,),
                )
                row = cur.fetchone()
    except psycopg.OperationalError:
        logger.exception(
            "Database connection failed while getting dish %s", id_platillo
        )
        raise HTTPException(
            status_code=503,
            detail="Database connection failed",
        )
    except Exception:
        logger.exception("Unexpected error while getting dish %s", id_platillo)
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        )
    if row is None:
        raise HTTPException(status_code=404, detail="Dish not found")
    return {"data": row}


# ---------------------------------------------------------------------------
# Writes (administrators only)
# ---------------------------------------------------------------------------


@app.post("/api/v1/catalogo/mesas", status_code=201)
def create_table(
    payload: MesaCreate,
    user: CurrentUser = Depends(require_roles(ROLE_ADMIN)),
):
    """Create a restaurant table (administrators only).

    ``numero_mesa`` is UNIQUE: a duplicate answers 409. The response
    contains no internal identifiers beyond the primary key.
    """
    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO mesas
                        (numero_mesa, capacidad, ubicacion, estado, activa)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING {_MESA_COLUMNS};
                    """,
                    (
                        payload.numero_mesa,
                        payload.capacidad,
                        payload.ubicacion,
                        payload.estado,
                        payload.activa,
                    ),
                )
                row = cur.fetchone()
    except psycopg.errors.UniqueViolation:
        raise HTTPException(
            status_code=409,
            detail="Table number already registered",
        )
    except psycopg.OperationalError:
        logger.exception("Database connection failed while creating a table")
        raise HTTPException(
            status_code=503,
            detail="Database connection failed",
        )
    except Exception:
        logger.exception("Unexpected error while creating a table")
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        )
    return {"data": row}


@app.patch("/api/v1/catalogo/mesas/{id_mesa}")
@app.put("/api/v1/catalogo/mesas/{id_mesa}")
def update_table(
    id_mesa: int,
    payload: MesaActualizar,
    user: CurrentUser = Depends(require_roles(ROLE_ADMIN)),
):
    """Update a restaurant table (administrators only).

    Only the keys present in the body are updated (whitelist above).
    """
    provided = payload.model_fields_set
    updates = {
        column: getattr(payload, field)
        for field, column in _MESA_UPDATABLE.items()
        if field in provided
    }
    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                if not updates:
                    cur.execute(
                        f"""
                        SELECT {_MESA_COLUMNS}
                        FROM mesas
                        WHERE id_mesa = %s;
                        """,
                        (id_mesa,),
                    )
                    row = cur.fetchone()
                    if row is None:
                        raise HTTPException(
                            status_code=404, detail="Table not found"
                        )
                    return {"data": row}

                # Column names come from the fixed whitelist above,
                # never from the request body.
                set_clause = ", ".join(
                    f"{column} = %s" for column in updates
                )
                cur.execute(
                    f"""
                    UPDATE mesas
                       SET {set_clause}
                     WHERE id_mesa = %s
                    RETURNING {_MESA_COLUMNS};
                    """,
                    (*updates.values(), id_mesa),
                )
                row = cur.fetchone()
    except HTTPException:
        raise
    except psycopg.errors.UniqueViolation:
        raise HTTPException(
            status_code=409,
            detail="Table number already registered",
        )
    except psycopg.OperationalError:
        logger.exception(
            "Database connection failed while updating table %s", id_mesa
        )
        raise HTTPException(
            status_code=503,
            detail="Database connection failed",
        )
    except Exception:
        logger.exception("Unexpected error while updating table %s", id_mesa)
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        )
    if row is None:
        raise HTTPException(status_code=404, detail="Table not found")
    return {"data": row}


@app.delete("/api/v1/catalogo/mesas/{id_mesa}")
def deactivate_table(
    id_mesa: int,
    user: CurrentUser = Depends(require_roles(ROLE_ADMIN)),
):
    """Logically deactivate a restaurant table (administrators only).

    Only ``activa=false`` is written: reservations that reference the
    table keep their foreign key (a physical DELETE would be rejected
    by the database once a reservation exists).
    """
    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE mesas
                       SET activa = false
                     WHERE id_mesa = %s
                    RETURNING {_MESA_COLUMNS};
                    """,
                    (id_mesa,),
                )
                row = cur.fetchone()
    except psycopg.OperationalError:
        logger.exception(
            "Database connection failed while deactivating table %s", id_mesa
        )
        raise HTTPException(
            status_code=503,
            detail="Database connection failed",
        )
    except Exception:
        logger.exception(
            "Unexpected error while deactivating table %s", id_mesa
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        )
    if row is None:
        raise HTTPException(status_code=404, detail="Table not found")
    return {"data": row}


@app.post("/api/v1/catalogo/platillos", status_code=201)
def create_dish(
    payload: PlatilloCreate,
    user: CurrentUser = Depends(require_roles(ROLE_ADMIN)),
):
    """Create a menu item (administrators only).

    ``precio`` must be >= 0 (422 otherwise) and is stored exactly as
    provided; availability defaults to ``disponible=true``.
    """
    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO platillos
                        (nombre, descripcion, precio, disponible)
                    VALUES (%s, %s, %s, %s)
                    RETURNING {_PLATILLO_COLUMNS};
                    """,
                    (
                        payload.nombre,
                        payload.descripcion,
                        payload.precio,
                        payload.disponible,
                    ),
                )
                row = cur.fetchone()
    except psycopg.OperationalError:
        logger.exception("Database connection failed while creating a dish")
        raise HTTPException(
            status_code=503,
            detail="Database connection failed",
        )
    except Exception:
        logger.exception("Unexpected error while creating a dish")
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        )
    return {"data": row}


@app.patch("/api/v1/catalogo/platillos/{id_platillo}")
@app.put("/api/v1/catalogo/platillos/{id_platillo}")
def update_dish(
    id_platillo: int,
    payload: PlatilloActualizar,
    user: CurrentUser = Depends(require_roles(ROLE_ADMIN)),
):
    """Update a menu item (administrators only).

    Only the keys present in the body are updated (whitelist above).
    """
    provided = payload.model_fields_set
    updates = {
        column: getattr(payload, field)
        for field, column in _PLATILLO_UPDATABLE.items()
        if field in provided
    }
    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                if not updates:
                    cur.execute(
                        f"""
                        SELECT {_PLATILLO_COLUMNS}
                        FROM platillos
                        WHERE id_platillo = %s;
                        """,
                        (id_platillo,),
                    )
                    row = cur.fetchone()
                    if row is None:
                        raise HTTPException(
                            status_code=404, detail="Dish not found"
                        )
                    return {"data": row}

                set_clause = ", ".join(
                    f"{column} = %s" for column in updates
                )
                cur.execute(
                    f"""
                    UPDATE platillos
                       SET {set_clause}
                     WHERE id_platillo = %s
                    RETURNING {_PLATILLO_COLUMNS};
                    """,
                    (*updates.values(), id_platillo),
                )
                row = cur.fetchone()
    except HTTPException:
        raise
    except psycopg.OperationalError:
        logger.exception(
            "Database connection failed while updating dish %s", id_platillo
        )
        raise HTTPException(
            status_code=503,
            detail="Database connection failed",
        )
    except Exception:
        logger.exception("Unexpected error while updating dish %s", id_platillo)
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        )
    if row is None:
        raise HTTPException(status_code=404, detail="Dish not found")
    return {"data": row}


@app.delete("/api/v1/catalogo/platillos/{id_platillo}")
def deactivate_dish(
    id_platillo: int,
    user: CurrentUser = Depends(require_roles(ROLE_ADMIN)),
):
    """Logically remove a menu item (administrators only).

    Only ``disponible=false`` is written so historical reservations
    keep their ``reserva_platillos`` rows intact.
    """
    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE platillos
                       SET disponible = false
                     WHERE id_platillo = %s
                    RETURNING {_PLATILLO_COLUMNS};
                    """,
                    (id_platillo,),
                )
                row = cur.fetchone()
    except psycopg.OperationalError:
        logger.exception(
            "Database connection failed while deactivating dish %s", id_platillo
        )
        raise HTTPException(
            status_code=503,
            detail="Database connection failed",
        )
    except Exception:
        logger.exception(
            "Unexpected error while deactivating dish %s", id_platillo
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        )
    if row is None:
        raise HTTPException(status_code=404, detail="Dish not found")
    return {"data": row}
