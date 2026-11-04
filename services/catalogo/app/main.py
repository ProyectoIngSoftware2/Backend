"""Catalogo microservice.

Responsible for restaurant resources and menu information using the
`mesas` (restaurant tables) and `platillos` (menu items) tables of the
approved database design. Read-only endpoints only in Sprint 1;
resource CRUD belongs to a later sprint.
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
from psycopg.rows import dict_row

from shared.database import check_connection, get_connection

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Catalogo Service",
    description=(
        "Restaurant resources and menu microservice for Punto y Sal "
        "(tables: mesas, platillos)."
    ),
    version="1.0.0",
)


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
