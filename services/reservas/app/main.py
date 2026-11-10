"""Reservas microservice.

Responsible for reservation-related operations and reservation history using
the reservation tables of the approved database design:
`reservas`, `reserva_platillos`, `historial_estados` and `notificaciones`.

Table ownership (post-audit correction F-01): this service never queries
another service's tables. Dish names shown in the reservation detail are
resolved by calling the catalogo microservice over HTTP
(`GET /api/v1/catalogo/platillos/{id}`) with a short timeout and controlled
error responses. The caller's client identity comes from the signed JWT
(``id_cliente`` claim resolved at login), so ownership checks stay inside
this service's own tables.

Sprint 2 (authentication and authorization):

* ``GET    /api/v1/reservas``            - administrators only.
* ``GET    /api/v1/reservas/{codigo}``   - administrator or owner.
* ``POST   /api/v1/reservas``            - authenticated; clients are
  always linked to their own identity, administrators may create a
  reservation for any customer (``id_cliente``).
* ``PATCH|PUT /api/v1/reservas/{codigo}``- owner or administrator;
  clients may only request ``estado='cancelada'``.
* ``DELETE /api/v1/reservas/{codigo}``   - logical cancellation
  (owner or administrator).

Status transitions, mesa validation, status history and notifications
remain the exclusive responsibility of the existing database triggers;
this service never duplicates that logic. Dish prices come from the
catalogo microservice, never from the request body.
"""

import logging
import sys
from decimal import Decimal
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
from fastapi import Depends, FastAPI, HTTPException
from psycopg.rows import dict_row
from pydantic_settings import BaseSettings, SettingsConfigDict

from shared.auth import (
    ROLE_ADMIN,
    ROLE_CLIENT,
    CurrentUser,
    get_current_user,
    require_roles,
)
from shared.database import check_connection, get_connection

from .schemas import ReservaCreate, ReservaUpdate

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

# Columns returned by the API.
_RESERVA_COLUMNS = (
    "id_reserva, codigo_reserva, id_cliente, id_mesa, fecha_hora_inicio, "
    "duracion_minutos, cantidad_personas, estado, observaciones, "
    "fecha_creacion, fecha_actualizacion, id_administrador"
)

# Whitelist for partial updates: request field -> column. Nothing else
# (never id_cliente, never codigo_reserva) can be modified through the
# update endpoint.
_UPDATABLE_COLUMNS = {
    "fecha_hora_inicio": "fecha_hora_inicio",
    "duracion_minutos": "duracion_minutos",
    "cantidad_personas": "cantidad_personas",
    "id_mesa": "id_mesa",
    "observaciones": "observaciones",
    "estado": "estado",
}


def _business_message(exc: Exception) -> str:
    """Return the primary message of a database error.

    Business-rule messages raised by the approved triggers (e.g. an
    invalid state transition or an unavailable mesa) are safe to show:
    they are part of the established specification. Falls back to a
    generic text when the driver provides no message.
    """
    diag = getattr(exc, "diag", None)
    message = getattr(diag, "message_primary", None) if diag else None
    return message or "Reservation data violates a business rule"


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
def list_reservations(
    user: CurrentUser = Depends(require_roles(ROLE_ADMIN)),
):
    """Return all reservations (administrators only, read-only)."""
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


def _fetch_dish_prices(platillos: list) -> list:
    """Validate dishes and fetch their prices from catalogo (F-01).

    Called before writing anything: the ``precio_unitario`` stored for
    a new reservation always comes from the catalog (never from the
    request body, which cannot carry a price at all). Controlled
    errors: 400 for a dish that does not exist, 503/504 when catalogo
    cannot answer.
    """
    if not platillos:
        return []

    base_url = settings.CATALOGO_SERVICE_URL.rstrip("/")
    prices: dict = {}

    with _catalogo_client() as client:
        for dish_id in dict.fromkeys(item.id_platillo for item in platillos):
            url = f"{base_url}/api/v1/catalogo/platillos/{dish_id}"
            try:
                response = client.get(url)
            except httpx.TimeoutException:
                logger.warning("Catalogo timed out while validating dish %s", dish_id)
                raise HTTPException(
                    status_code=504,
                    detail="Catalogo service did not respond in time",
                )
            except httpx.HTTPError:
                logger.warning(
                    "Catalogo unreachable while validating dish %s", dish_id
                )
                raise HTTPException(
                    status_code=503,
                    detail="Catalogo service is unavailable",
                )
            if response.status_code == 404:
                raise HTTPException(
                    status_code=400,
                    detail=f"Dish {dish_id} does not exist",
                )
            if response.status_code != 200:
                raise HTTPException(
                    status_code=503,
                    detail="Catalogo service is unavailable",
                )
            try:
                payload = response.json()
            except ValueError:
                raise HTTPException(
                    status_code=503,
                    detail="Catalogo service is unavailable",
                )
            precio = (payload.get("data") or {}).get("precio")
            if precio is None:
                raise HTTPException(
                    status_code=503,
                    detail="Catalogo service is unavailable",
                )
            prices[dish_id] = precio

    return [
        {
            "id_platillo": item.id_platillo,
            "cantidad": item.cantidad,
            "precio_unitario": Decimal(str(prices[item.id_platillo])),
            "observaciones": item.observaciones,
        }
        for item in platillos
    ]


@app.get("/api/v1/reservas/{codigo_reserva}")
def get_reservation(
    codigo_reserva: str,
    user: CurrentUser = Depends(get_current_user),
):
    """Return one reservation with its dishes and status history.

    Administrators may read any reservation; clients only their own,
    because the ownership condition (``id_cliente`` taken from the
    signed JWT) is part of the WHERE clause. Another customer's
    reservation therefore answers 404 and cannot be enumerated.

    Dish names are fetched from the catalogo microservice over HTTP
    after the database work completes, so an HTTP failure can never be
    mistaken for a database failure.
    """
    reservation = None
    dish_rows = []
    history = []

    if user.rol != ROLE_ADMIN and user.id_cliente is None:
        # A client account without a linked profile owns nothing.
        raise HTTPException(status_code=404, detail="Reservation not found")

    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                if user.rol == ROLE_ADMIN:
                    cur.execute(
                        f"""
                        SELECT {_RESERVA_COLUMNS}
                        FROM reservas
                        WHERE codigo_reserva = %s;
                        """,
                        (codigo_reserva,),
                    )
                else:
                    cur.execute(
                        f"""
                        SELECT {_RESERVA_COLUMNS}
                        FROM reservas
                        WHERE codigo_reserva = %s AND id_cliente = %s;
                        """,
                        (codigo_reserva, user.id_cliente),
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


@app.post("/api/v1/reservas", status_code=201)
def create_reservation(
    payload: ReservaCreate,
    user: CurrentUser = Depends(get_current_user),
):
    """Create a reservation (authenticated).

    * role ``cliente``: the reservation is always linked to the
      caller's own ``id_cliente`` (from the signed token). Supplying
      another customer's id is rejected with 403; a body without a
      matching id is simply ignored in favour of the token identity.
    * role ``administrador``: ``id_cliente`` is required and validated
      by the foreign key (400 when it does not exist).
    * ``codigo_reserva``, ``estado='pendiente'``, history and
      notifications are generated by the database (defaults/triggers).
    * dish prices are read from catalogo before writing anything.
    """
    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                if user.rol == ROLE_CLIENT:
                    if user.id_cliente is None:
                        raise HTTPException(
                            status_code=403,
                            detail="Client profile not found",
                        )
                    if (
                        payload.id_cliente is not None
                        and payload.id_cliente != user.id_cliente
                    ):
                        raise HTTPException(
                            status_code=403,
                            detail=(
                                "Clients cannot create reservations for "
                                "another customer"
                            ),
                        )
                    id_cliente = user.id_cliente
                    id_administrador = None
                else:
                    if payload.id_cliente is None:
                        raise HTTPException(
                            status_code=400,
                            detail="id_cliente is required for administrators",
                        )
                    id_cliente = payload.id_cliente
                    id_administrador = user.id_administrador

                # Prices come from catalogo (HTTP) while no row has
                # been written yet: a catalog failure aborts cleanly.
                dish_rows = _fetch_dish_prices(payload.platillos)

                cur.execute(
                    f"""
                    INSERT INTO reservas
                        (id_cliente, id_mesa, fecha_hora_inicio,
                         duracion_minutos, cantidad_personas,
                         observaciones, id_administrador)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING {_RESERVA_COLUMNS};
                    """,
                    (
                        id_cliente,
                        payload.id_mesa,
                        payload.fecha_hora_inicio,
                        payload.duracion_minutos,
                        payload.cantidad_personas,
                        payload.observaciones,
                        id_administrador,
                    ),
                )
                row = cur.fetchone()

                for dish in dish_rows:
                    cur.execute(
                        """
                        INSERT INTO reserva_platillos
                            (id_reserva, id_platillo, cantidad,
                             precio_unitario, observaciones)
                        VALUES (%s, %s, %s, %s, %s);
                        """,
                        (
                            row["id_reserva"],
                            dish["id_platillo"],
                            dish["cantidad"],
                            dish["precio_unitario"],
                            dish["observaciones"],
                        ),
                    )
    except HTTPException:
        raise
    except psycopg.OperationalError:
        logger.exception("Database connection failed while creating a reservation")
        raise HTTPException(
            status_code=503,
            detail="Database connection failed",
        )
    except psycopg.errors.RaiseException as exc:
        # Business rules implemented as database triggers (mesa
        # validation, capacity, state must start as pendiente...).
        logger.warning("Reservation rejected by a business rule: %s", exc)
        raise HTTPException(status_code=400, detail=_business_message(exc))
    except psycopg.errors.UniqueViolation:
        raise HTTPException(
            status_code=409,
            detail="Duplicate dish in reservation",
        )
    except psycopg.errors.IntegrityError as exc:
        # Foreign key (unknown customer/mesa) or CHECK violation.
        logger.warning("Reservation rejected by the database: %s", exc)
        raise HTTPException(
            status_code=400,
            detail="Referenced resource does not exist or is invalid",
        )
    except Exception:
        logger.exception("Unexpected error while creating a reservation")
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        )
    return {"data": row}


@app.patch("/api/v1/reservas/{codigo_reserva}")
@app.put("/api/v1/reservas/{codigo_reserva}")
def update_reservation(
    codigo_reserva: str,
    payload: ReservaUpdate,
    user: CurrentUser = Depends(get_current_user),
):
    """Modify a reservation (owner or administrator).

    * ownership is enforced in the WHERE clause (``id_cliente`` from
      the JWT for clients), so another customer's reservation answers
      404;
    * clients may only change ``estado`` to ``cancelada`` (403 for any
      other status);
    * administrators may request any transition; the database trigger
      validates it and answers 400 when the transition is not allowed;
    * when an administrator changes the status, the reservation is
      stamped with their administrative profile (from the JWT).
    """
    provided = payload.model_fields_set
    updates = {
        column: getattr(payload, field)
        for field, column in _UPDATABLE_COLUMNS.items()
        if field in provided
    }

    if user.rol != ROLE_ADMIN:
        if user.id_cliente is None:
            raise HTTPException(status_code=404, detail="Reservation not found")
        if "estado" in updates and updates["estado"] != "cancelada":
            raise HTTPException(
                status_code=403,
                detail="Only cancellation is allowed for clients",
            )

    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                if user.rol == ROLE_ADMIN:
                    cur.execute(
                        f"""
                        SELECT {_RESERVA_COLUMNS}
                        FROM reservas
                        WHERE codigo_reserva = %s;
                        """,
                        (codigo_reserva,),
                    )
                else:
                    cur.execute(
                        f"""
                        SELECT {_RESERVA_COLUMNS}
                        FROM reservas
                        WHERE codigo_reserva = %s AND id_cliente = %s;
                        """,
                        (codigo_reserva, user.id_cliente),
                    )
                target = cur.fetchone()
                if target is None:
                    raise HTTPException(
                        status_code=404, detail="Reservation not found"
                    )

                if not updates:
                    # Nothing to change: return the current record.
                    return {"data": target}

                if (
                    "estado" in updates
                    and user.rol == ROLE_ADMIN
                    and user.id_administrador is not None
                ):
                    # Stamp the acting administrator on a status change
                    # (the history trigger records it).
                    updates["id_administrador"] = user.id_administrador

                # Column names come from the fixed whitelist above,
                # never from the request body.
                set_clause = ", ".join(
                    f"{column} = %s" for column in updates
                )
                cur.execute(
                    f"""
                    UPDATE reservas
                       SET {set_clause}
                     WHERE id_reserva = %s
                    RETURNING {_RESERVA_COLUMNS};
                    """,
                    (*updates.values(), target["id_reserva"]),
                )
                row = cur.fetchone()
    except HTTPException:
        raise
    except psycopg.OperationalError:
        logger.exception(
            "Database connection failed while updating reservation %s",
            codigo_reserva,
        )
        raise HTTPException(
            status_code=503,
            detail="Database connection failed",
        )
    except psycopg.errors.RaiseException as exc:
        # Estado transition or mesa validation (database triggers).
        logger.warning("Reservation update rejected by a rule: %s", exc)
        raise HTTPException(status_code=400, detail=_business_message(exc))
    except psycopg.errors.UniqueViolation:
        raise HTTPException(
            status_code=409,
            detail="Conflicting reservation data",
        )
    except psycopg.errors.IntegrityError as exc:
        logger.warning("Reservation update rejected by the database: %s", exc)
        raise HTTPException(
            status_code=400,
            detail="Referenced resource does not exist or is invalid",
        )
    except Exception:
        logger.exception(
            "Unexpected error while updating reservation %s", codigo_reserva
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        )
    return {"data": row}


@app.delete("/api/v1/reservas/{codigo_reserva}")
def cancel_reservation(
    codigo_reserva: str,
    user: CurrentUser = Depends(get_current_user),
):
    """Logically cancel a reservation (owner or administrator).

    The reservation keeps its rows: only ``estado`` changes to
    ``cancelada``. The existing trigger decides whether the current
    state allows that transition (e.g. a ``completada`` reservation
    cannot be cancelled) and answers 400 when it does not; history and
    notifications are generated by the same triggers.
    """
    if user.rol != ROLE_ADMIN and user.id_cliente is None:
        raise HTTPException(status_code=404, detail="Reservation not found")

    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                if user.rol == ROLE_ADMIN:
                    cur.execute(
                        """
                        SELECT id_reserva
                        FROM reservas
                        WHERE codigo_reserva = %s;
                        """,
                        (codigo_reserva,),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id_reserva
                        FROM reservas
                        WHERE codigo_reserva = %s AND id_cliente = %s;
                        """,
                        (codigo_reserva, user.id_cliente),
                    )
                target = cur.fetchone()
                if target is None:
                    raise HTTPException(
                        status_code=404, detail="Reservation not found"
                    )

                if (
                    user.rol == ROLE_ADMIN
                    and user.id_administrador is not None
                ):
                    cur.execute(
                        """
                        UPDATE reservas
                           SET estado = 'cancelada',
                               id_administrador = %s
                         WHERE id_reserva = %s
                        RETURNING id_reserva, codigo_reserva, id_cliente,
                                  id_mesa, fecha_hora_inicio,
                                  duracion_minutos, cantidad_personas,
                                  estado, observaciones, fecha_creacion,
                                  fecha_actualizacion, id_administrador;
                        """,
                        (user.id_administrador, target["id_reserva"]),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE reservas
                           SET estado = 'cancelada'
                         WHERE id_reserva = %s
                        RETURNING id_reserva, codigo_reserva, id_cliente,
                                  id_mesa, fecha_hora_inicio,
                                  duracion_minutos, cantidad_personas,
                                  estado, observaciones, fecha_creacion,
                                  fecha_actualizacion, id_administrador;
                        """,
                        (target["id_reserva"],),
                    )
                row = cur.fetchone()
    except HTTPException:
        raise
    except psycopg.OperationalError:
        logger.exception(
            "Database connection failed while cancelling reservation %s",
            codigo_reserva,
        )
        raise HTTPException(
            status_code=503,
            detail="Database connection failed",
        )
    except psycopg.errors.RaiseException as exc:
        # The cancellation rules of the approved trigger.
        logger.warning("Reservation cancellation rejected by a rule: %s", exc)
        raise HTTPException(status_code=400, detail=_business_message(exc))
    except Exception:
        logger.exception(
            "Unexpected error while cancelling reservation %s", codigo_reserva
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        )
    return {"data": row}
