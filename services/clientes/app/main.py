"""Clientes microservice.

Responsible for customer-related data and operations using the `clientes`
table of the approved database design. Read-only endpoints only in Sprint 1;
customer CRUD belongs to a later sprint.
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
    title="Clientes Service",
    description="Customer management microservice for Punto y Sal (table: clientes).",
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
        "service": "clientes",
        "status": "ok",
        "database": "connected",
    }


@app.get("/api/v1/clientes")
def list_customers():
    """Return all registered customers (read-only)."""
    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id_cliente, nombre_completo, numero_identidad,
                           telefono, correo, fecha_registro, activo
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
def get_customer(id_cliente: int):
    """Return one customer by identifier (read-only)."""
    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id_cliente, nombre_completo, numero_identidad,
                           telefono, correo, fecha_registro, activo
                    FROM clientes
                    WHERE id_cliente = %s;
                    """,
                    (id_cliente,),
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
