"""Reservas microservice.

Responsible for reservation-related operations and reservation history using
the reservation tables of the approved database design:
`reservas`, `reserva_platillos`, `historial_estados` and `notificaciones`.

Table ownership (post-audit correction F-01): this service never queries
another service's tables. Dish names shown in the reservation detail are
resolved by calling the catalogo microservice over HTTP
(`GET /api/v1/catalogo/platillos/{id}`) with a short timeout and controlled
error responses. This is an implemented technical clarification; team
approval is PENDING (see docs/sprint-1/design-change-log.md).

Read-only endpoints only in Sprint 1; reservation CRUD belongs to a later
sprint. The database triggers generate the reservation code, status history
and notifications automatically.
"""

import logging
import sys
from pathlib import Path

# Allow this service to run from its own folder while reusing the
# repository's shared/ package (works locally and inside the containers).
REPO_ROOT = None
for _parent in Path(__file__).resolve().parents:
    if (_parent / "shared" / "database.py").exists():
        REPO_ROOT = _parent
        if str(_parent) not in sys.path:
            sys.path.insert(0, str(_parent))
        break
if REPO_ROOT is None:  # pragma: no cover - shared/ always ships with the service
    REPO_ROOT = Path(__file__).resolve().parents[3]

import httpx
import psycopg
from fastapi import FastAPI, HTTPException
from psycopg.rows import dict_row
from pydantic_settings import BaseSettings, SettingsConfigDict

from shared.database import check_connection, get_connection

logger = logging.getLogger(__name__)

# Timeout (seconds) for service-to-service calls to catalogo.
CATALOGO_TIMEOUT = 5.0


class ReservasSettings(BaseSettings):
    """Runtime configuration loaded from environment variables.

    CATALOGO_SERVICE_URL points at the catalogo microservice:
    http://localhost:8003 locally, http://catalogo:8003 inside Docker
    Compose. It is also read from the optional repository-root .env file,
    following the same convention as the gateway.
    """

    CATALOGO_SERVICE_URL: str = "http://localhost:8003"

    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = ReservasSettings()

app = FastAPI(
    title="Reservas Service",
    description=(
        "Reservation management microservice for Punto y Sal "
        "(tables: reservas, reserva_platillos, historial_estados, "
        "notificaciones). Dish names are resolved through the catalogo "
        "microservice over HTTP; this service never queries other "
        "services' tables."
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
        "service": "reservas",
        "status": "ok",
        "database": "connected",
    }


@app.get("/api/v1/reservas")
def list_reservations():
    """Return all reservations (read-only, own tables only)."""
    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT r.id_reserva, r.codigo_reserva, r.id_cliente,
                           r.id_mesa, r.fecha_hora_inicio, r.duracion_minutos,
                           r.cantidad_personas, r.estado, r.observaciones,
                           r.fecha_creacion, r.fecha_actualizacion,
                           r.id_administrador
                    FROM reservas r
                    ORDER BY r.fecha_hora_inicio;
                    """
                )
                rows = cur.fetchall()
    except psycopg.OperationalError:
        logger.exception("Database connection failed while listing reservations")
        raise HTTPException(
            status_code=503,
            detail="Database connection failed",
        )
    except Exception:
        logger.exception("Unexpected error while listing reservations")
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        )
    return {"data": rows}


def _catalogo_client() -> httpx.Client:
    """HTTP client used for service-to-service calls to catalogo.

    Kept as a small seam so tests can substitute a mock transport.
    """
    return httpx.Client(timeout=CATALOGO_TIMEOUT)


def _fetch_dish_names(id_platillos: list) -> dict:
    """Resolve dish ids to names by calling the catalogo microservice.

    Read-only HTTP calls; catalogo owns the `platillos` table, so this
    service never queries it directly (F-01). Controlled errors only:
    504 when catalogo times out, 503 when it is unreachable or answers
    with an error status. Internal URLs are never exposed to clients.
    """
    names: dict = {}
    base_url = settings.CATALOGO_SERVICE_URL.rstrip("/")

    with _catalogo_client() as client:
        # dict.fromkeys() de-duplicates while preserving order.
        for dish_id in dict.fromkeys(id_platillos):
            url = f"{base_url}/api/v1/catalogo/platillos/{dish_id}"
            try:
                response = client.get(url)
            except httpx.TimeoutException:
                logger.warning("Catalogo timed out while resolving dish %s", dish_id)
                raise HTTPException(
                    status_code=504,
                    detail="Catalogo service did not respond in time",
                )
            except httpx.HTTPError:
                logger.warning(
                    "Catalogo unreachable while resolving dish %s", dish_id
                )
                raise HTTPException(
                    status_code=503,
                    detail="Catalogo service is unavailable",
                )

            if response.status_code == 404:
                # Defensive: the foreign key guarantees the dish exists;
                # if catalogo disagrees we degrade to a missing name.
                names[dish_id] = None
                continue
            if response.status_code != 200:
                logger.warning(
                    "Catalogo answered %s while resolving dish %s",
                    response.status_code,
                    dish_id,
                )
                raise HTTPException(
                    status_code=503,
                    detail="Catalogo service is unavailable",
                )
            try:
                payload = response.json()
            except ValueError:
                logger.warning("Catalogo returned a non-JSON body for dish %s", dish_id)
                raise HTTPException(
                    status_code=503,
                    detail="Catalogo service is unavailable",
                )
            names[dish_id] = (payload.get("data") or {}).get("nombre")

    return names


def _build_dishes(dish_rows: list) -> list:
    """Merge reserva_platillos rows with names from catalogo (F-01).

    Preserves the original response contract: each item contains
    id_platillo, nombre, cantidad, precio_unitario and observaciones.
    """
    if not dish_rows:
        # Nothing to resolve: catalogo is not called at all.
        return []

    names = _fetch_dish_names([row["id_platillo"] for row in dish_rows])
    return [
        {
            "id_platillo": row["id_platillo"],
            "nombre": names.get(row["id_platillo"]),
            "cantidad": row["cantidad"],
            "precio_unitario": row["precio_unitario"],
            "observaciones": row["observaciones"],
        }
        for row in dish_rows
    ]


@app.get("/api/v1/reservas/{codigo_reserva}")
def get_reservation(codigo_reserva: str):
    """Return one reservation with its dishes and status history (read-only).

    Dish names are fetched from the catalogo microservice over HTTP
    after the database work completes, so an HTTP failure can never be
    mistaken for a database failure.
    """
    reservation = None
    dish_rows = []
    history = []

    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id_reserva, codigo_reserva, id_cliente, id_mesa,
                           fecha_hora_inicio, duracion_minutos,
                           cantidad_personas, estado, observaciones,
                           fecha_creacion, fecha_actualizacion,
                           id_administrador
                    FROM reservas
                    WHERE codigo_reserva = %s;
                    """,
                    (codigo_reserva,),
                )
                reservation = cur.fetchone()

                if reservation is not None:
                    # Own table only: names come from catalogo (see F-01).
                    cur.execute(
                        """
                        SELECT id_platillo, cantidad, precio_unitario,
                               observaciones
                        FROM reserva_platillos
                        WHERE id_reserva = %s
                        ORDER BY id_reserva_platillo;
                        """,
                        (reservation["id_reserva"],),
                    )
                    dish_rows = cur.fetchall()

                    cur.execute(
                        """
                        SELECT id_historial, estado_anterior, estado_nuevo,
                               id_administrador, comentario, fecha_cambio
                        FROM historial_estados
                        WHERE id_reserva = %s
                        ORDER BY fecha_cambio;
                        """,
                        (reservation["id_reserva"],),
                    )
                    history = cur.fetchall()
    except psycopg.OperationalError:
        logger.exception(
            "Database connection failed while getting reservation %s",
            codigo_reserva,
        )
        raise HTTPException(
            status_code=503,
            detail="Database connection failed",
        )
    except Exception:
        logger.exception(
            "Unexpected error while getting reservation %s", codigo_reserva
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        )

    # Checked outside the try block so the 404 is not converted into a
    # 500/503. A reservation without dishes never calls catalogo.
    if reservation is None:
        raise HTTPException(status_code=404, detail="Reservation not found")

    dishes = _build_dishes(dish_rows)

    return {
        "data": reservation,
        "platillos": dishes,
        "historial": history,
    }
