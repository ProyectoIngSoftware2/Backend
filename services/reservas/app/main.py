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

Sprint 4 (availability): ``GET /api/v1/disponibilidad`` (public,
read-only) computes the free time slots of a date from ``horarios``,
``bloqueos_horario``, ``mesas`` and ``reservas`` in one self-contained
query block inside this service: the availability answer must be
produced locally without fanning out over HTTP, so this read-only
access to the schedule/table tables is a task-authorized exception to
the write-path ownership rule above. No other service's tables are
ever written or modified here.

Sprint 4 (reports): ``GET /api/v1/reportes/reservas`` (administrators
only, read-only) returns reservation rows filtered by date range,
estado, client and mesa together with per-state totals. It reads only
this service's own ``reservas`` table: the filter ids are never joined
into another service's tables and the report performs no HTTP calls
(F-01).
"""

import logging
import sys
from datetime import date, datetime, time, timedelta
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
from .schemas_platillos import ReservaPlatilloLineActualizar, ReservaPlatilloLineCreate

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


# ---------------------------------------------------------------------------
# Reservation dish details (Sprint 3).
#
# Complete CRUD for dish lines associated with a reservation.
# Prices are always sourced from the catalogo service, never from the
# client. Ownership is enforced via the JWT id_cliente claim.
# ---------------------------------------------------------------------------


def _verify_reservation_ownership(conn, codigo_reserva: str, user: CurrentUser):
    """Return the reservation row if the user can access it, else None.

    Administrators can access any reservation; clients only their own.
    """
    if user.rol == ROLE_ADMIN:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id_reserva, codigo_reserva, id_cliente, estado
            FROM reservas
            WHERE codigo_reserva = %s;
            """,
            (codigo_reserva,),
        )
    else:
        if user.id_cliente is None:
            return None
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id_reserva, codigo_reserva, id_cliente, estado
            FROM reservas
            WHERE codigo_reserva = %s AND id_cliente = %s;
            """,
            (codigo_reserva, user.id_cliente),
        )
    return cur.fetchone()


def _is_reservation_modifiable(estado: str) -> bool:
    """Return True if the reservation state allows dish line changes."""
    return estado in ("pendiente", "aprobada")


@app.get("/api/v1/reservas/{codigo_reserva}/platillos")
def list_reservation_platillos(
    codigo_reserva: str,
    user: CurrentUser = Depends(get_current_user),
):
    """List dish lines for a reservation (owner or administrator)."""
    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                reservation = _verify_reservation_ownership(conn, codigo_reserva, user)
                if reservation is None:
                    raise HTTPException(status_code=404, detail="Reservation not found")

                cur.execute(
                    """
                    SELECT id_reserva_platillo, id_reserva, id_platillo,
                           cantidad, precio_unitario, observaciones
                    FROM reserva_platillos
                    WHERE id_reserva = %s
                    ORDER BY id_reserva_platillo;
                    """,
                    (reservation["id_reserva"],),
                )
                rows = cur.fetchall()
    except HTTPException:
        raise
    except psycopg.OperationalError:
        logger.exception(
            "Database connection failed while listing platillos for %s", codigo_reserva
        )
        raise HTTPException(status_code=503, detail="Database connection failed")
    except Exception:
        logger.exception(
            "Unexpected error while listing platillos for %s", codigo_reserva
        )
        raise HTTPException(status_code=500, detail="Internal server error")
    return {"data": rows}


@app.post("/api/v1/reservas/{codigo_reserva}/platillos", status_code=201)
def create_reservation_platillo(
    codigo_reserva: str,
    payload: ReservaPlatilloLineCreate,
    user: CurrentUser = Depends(get_current_user),
):
    """Add a dish line to a reservation (owner or administrator).

    The price is always sourced from the catalogo service.
    """
    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                reservation = _verify_reservation_ownership(conn, codigo_reserva, user)
                if reservation is None:
                    raise HTTPException(status_code=404, detail="Reservation not found")

                if not _is_reservation_modifiable(reservation["estado"]):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Cannot modify dishes for reservation in state '{reservation['estado']}'",
                    )

                # Check for duplicate dish line
                cur.execute(
                    """
                    SELECT 1 FROM reserva_platillos
                    WHERE id_reserva = %s AND id_platillo = %s;
                    """,
                    (reservation["id_reserva"], payload.id_platillo),
                )
                if cur.fetchone() is not None:
                    raise HTTPException(
                        status_code=409, detail="Dish already in this reservation"
                    )

                # Price comes from catalogo, never from the client
                dish_rows = _fetch_dish_prices(
                    [type("P", (), {"id_platillo": payload.id_platillo, "cantidad": payload.cantidad, "observaciones": payload.observaciones})()]
                )
                precio_unitario = dish_rows[0]["precio_unitario"]

                cur.execute(
                    """
                    INSERT INTO reserva_platillos
                        (id_reserva, id_platillo, cantidad, precio_unitario, observaciones)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id_reserva_platillo, id_reserva, id_platillo,
                              cantidad, precio_unitario, observaciones;
                    """,
                    (
                        reservation["id_reserva"],
                        payload.id_platillo,
                        payload.cantidad,
                        precio_unitario,
                        payload.observaciones,
                    ),
                )
                row = cur.fetchone()
    except HTTPException:
        raise
    except psycopg.OperationalError:
        logger.exception(
            "Database connection failed while adding platillo to %s", codigo_reserva
        )
        raise HTTPException(status_code=503, detail="Database connection failed")
    except Exception:
        logger.exception(
            "Unexpected error while adding platillo to %s", codigo_reserva
        )
        raise HTTPException(status_code=500, detail="Internal server error")
    return {"data": row}


@app.patch("/api/v1/reservas/{codigo_reserva}/platillos/{detalle_id}")
@app.put("/api/v1/reservas/{codigo_reserva}/platillos/{detalle_id}")
def update_reservation_platillo(
    codigo_reserva: str,
    detalle_id: int,
    payload: ReservaPlatilloLineActualizar,
    user: CurrentUser = Depends(get_current_user),
):
    """Update a dish line quantity/observations (owner or administrator)."""
    provided = payload.model_fields_set
    updates = {}
    for field in ("cantidad", "observaciones"):
        if field in provided:
            updates[field] = getattr(payload, field)

    if not updates:
        return {"data": {"id_reserva_platillo": detalle_id, "message": "No changes"}}

    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                reservation = _verify_reservation_ownership(conn, codigo_reserva, user)
                if reservation is None:
                    raise HTTPException(status_code=404, detail="Reservation not found")

                if not _is_reservation_modifiable(reservation["estado"]):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Cannot modify dishes for reservation in state '{reservation['estado']}'",
                    )

                # Verify the dish line belongs to this reservation
                cur.execute(
                    """
                    SELECT 1 FROM reserva_platillos
                    WHERE id_reserva_platillo = %s AND id_reserva = %s;
                    """,
                    (detalle_id, reservation["id_reserva"]),
                )
                if cur.fetchone() is None:
                    raise HTTPException(status_code=404, detail="Dish line not found")

                set_clause = ", ".join(f"{column} = %s" for column in updates)
                cur.execute(
                    f"""
                    UPDATE reserva_platillos
                       SET {set_clause}
                     WHERE id_reserva_platillo = %s
                    RETURNING id_reserva_platillo, id_reserva, id_platillo,
                              cantidad, precio_unitario, observaciones;
                    """,
                    (*updates.values(), detalle_id),
                )
                row = cur.fetchone()
    except HTTPException:
        raise
    except psycopg.OperationalError:
        logger.exception(
            "Database connection failed while updating platillo %s in %s",
            detalle_id,
            codigo_reserva,
        )
        raise HTTPException(status_code=503, detail="Database connection failed")
    except Exception:
        logger.exception(
            "Unexpected error while updating platillo %s in %s",
            detalle_id,
            codigo_reserva,
        )
        raise HTTPException(status_code=500, detail="Internal server error")
    return {"data": row}


@app.delete("/api/v1/reservas/{codigo_reserva}/platillos/{detalle_id}")
def delete_reservation_platillo(
    codigo_reserva: str,
    detalle_id: int,
    user: CurrentUser = Depends(get_current_user),
):
    """Remove a dish line from a reservation (owner or administrator)."""
    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                reservation = _verify_reservation_ownership(conn, codigo_reserva, user)
                if reservation is None:
                    raise HTTPException(status_code=404, detail="Reservation not found")

                if not _is_reservation_modifiable(reservation["estado"]):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Cannot modify dishes for reservation in state '{reservation['estado']}'",
                    )

                cur.execute(
                    """
                    DELETE FROM reserva_platillos
                     WHERE id_reserva_platillo = %s AND id_reserva = %s
                    RETURNING id_reserva_platillo;
                    """,
                    (detalle_id, reservation["id_reserva"]),
                )
                row = cur.fetchone()
    except HTTPException:
        raise
    except psycopg.OperationalError:
        logger.exception(
            "Database connection failed while deleting platillo %s from %s",
            detalle_id,
            codigo_reserva,
        )
        raise HTTPException(status_code=503, detail="Database connection failed")
    except Exception:
        logger.exception(
            "Unexpected error while deleting platillo %s from %s",
            detalle_id,
            codigo_reserva,
        )
        raise HTTPException(status_code=500, detail="Internal server error")
    if row is None:
        raise HTTPException(status_code=404, detail="Dish line not found")
    return {"data": row}


# ---------------------------------------------------------------------------
# Disponibilidad (Sprint 4, gap G6): read-only availability computation.
# ---------------------------------------------------------------------------

# Duration limits of a candidate reservation (mirrors the ``reservas``
# CHECK constraint: 15..720 minutes) and the default used when the
# caller does not send ``duracion_minutos``.
_DURACION_MIN = 15
_DURACION_MAX = 720
_DURACION_DEFAULT = 120


def _parse_disponibilidad_params(fecha, cantidad_personas, duracion_minutos):
    """Validate the query string of GET /api/v1/disponibilidad (400 on error).

    The parameters are read as raw strings and parsed manually so that
    every invalid input answers ``400 Bad Request`` (this endpoint's
    specification) instead of FastAPI's default ``422``. Returns
    ``(fecha_date, cantidad_personas, duracion_minutos)`` with the
    normalized values.
    """
    if fecha is None or not fecha.strip():
        raise HTTPException(
            status_code=400,
            detail="Query parameter 'fecha' is required (format YYYY-MM-DD)",
        )
    try:
        fecha_date = date.fromisoformat(fecha.strip())
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Query parameter 'fecha' must be a valid date in YYYY-MM-DD format",
        ) from exc

    personas = 1
    if cantidad_personas is not None and cantidad_personas.strip():
        try:
            personas = int(cantidad_personas.strip())
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail="Query parameter 'cantidad_personas' must be an integer",
            ) from exc
        if personas < 1:
            raise HTTPException(
                status_code=400,
                detail="Query parameter 'cantidad_personas' must be at least 1",
            )

    duracion = _DURACION_DEFAULT
    if duracion_minutos is not None and duracion_minutos.strip():
        try:
            duracion = int(duracion_minutos.strip())
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail="Query parameter 'duracion_minutos' must be an integer",
            ) from exc
        if not _DURACION_MIN <= duracion <= _DURACION_MAX:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Query parameter 'duracion_minutos' must be between "
                    f"{_DURACION_MIN} and {_DURACION_MAX}"
                ),
            )
    return fecha_date, personas, duracion


def _as_time(value):
    """Coerce a TIME column value to ``datetime.time`` (accepts 'HH:MM[:SS]')."""
    if isinstance(value, time):
        return value
    return time.fromisoformat(str(value))


def _as_naive_wall_clock(value):
    """Coerce a timestamptz value to a naive wall-clock datetime.

    ``fecha_hora_inicio`` and the bloqueo bounds are ``timestamptz``:
    psycopg returns timezone-aware datetimes whose *wall-clock* fields
    are the stored local time. Availability is computed on those
    wall-clock values (the API contract speaks plain local times), so
    the offset is dropped instead of converting to another zone.
    """
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value.replace(tzinfo=None)
    return value


def _intervals_overlap(start_a, end_a, start_b, end_b):
    """True when the half-open intervals [start_a, end_a) and [start_b, end_b) intersect."""
    return start_a < end_b and start_b < end_a


@app.get("/api/v1/disponibilidad")
def check_availability(
    fecha: str | None = None,
    cantidad_personas: str | None = None,
    duracion_minutos: str | None = None,
):
    """Return the reservable time slots of a date (public, read-only).

    Query parameters:
        * ``fecha`` (required, ``YYYY-MM-DD``) - day to consult.
        * ``cantidad_personas`` (optional, default 1) - party size used
          to filter candidate mesas by capacity.
        * ``duracion_minutos`` (optional, default 120, between 15 and
          720) - length of each candidate reservation.

    Missing or invalid parameters answer ``400 Bad Request`` (parsed
    manually, never FastAPI's 422).

    The day's slots come from the active ``horarios`` rows of its
    weekday (``dia_semana``: 1 = Monday .. 7 = Sunday). A slot is
    offered only while the whole reservation fits inside the business
    hours, and counts the candidate mesas (``activa``,
    ``estado='disponible'``, ``capacidad >= cantidad_personas``) that
    are neither held by an active reservation
    (``pendiente``/``aprobada``/``confirmada`` overlapping
    ``[slot, slot + duracion)``) nor covered by a ``bloqueos_horario``
    entry (``id_mesa IS NULL`` blocks every mesa). A weekday without
    active ``horarios`` answers 200 with empty ``horarios``/``slots``
    (the establishment is closed).

    F-01 note: availability needs ``horarios``, ``bloqueos_horario``,
    ``mesas`` and ``reservas`` together, so the four reads run in one
    self-contained query block inside this service (Sprint 4
    requirement) instead of fanning out over HTTP. The block is
    strictly read-only.
    """
    fecha_date, personas, duracion = _parse_disponibilidad_params(
        fecha, cantidad_personas, duracion_minutos
    )
    fecha_iso = fecha_date.isoformat()
    dia_semana = fecha_date.isoweekday()

    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                # 1) Active business hours of that weekday.
                cur.execute(
                    """
                    SELECT hora_apertura, hora_cierre, intervalo_minutos
                    FROM horarios
                    WHERE dia_semana = %s
                      AND activo = TRUE
                    ORDER BY hora_apertura;
                    """,
                    (dia_semana,),
                )
                horarios_rows = cur.fetchall()

                # 2) Candidate mesas for the requested party size.
                cur.execute(
                    """
                    SELECT id_mesa, numero_mesa, capacidad
                    FROM mesas
                    WHERE activa = TRUE
                      AND estado = 'disponible'
                      AND capacidad >= %s
                    ORDER BY id_mesa;
                    """,
                    (personas,),
                )
                mesas_rows = cur.fetchall()

                # 3) Reservations that may overlap the day. Only the
                #    states that still hold a mesa are considered
                #    (``rechazada``, ``cancelada`` and ``completada``
                #    have released it). The window around the day is
                #    deliberately loose (the columns are timestamptz
                #    and session-timezone offsets must not drop a
                #    boundary reservation); the exact filtering happens
                #    in Python below.
                cur.execute(
                    """
                    SELECT id_mesa, fecha_hora_inicio, duracion_minutos
                    FROM reservas
                    WHERE estado IN ('pendiente', 'aprobada', 'confirmada')
                      AND id_mesa IS NOT NULL
                      AND fecha_hora_inicio < (%s::date + INTERVAL '2 days')
                      AND fecha_hora_inicio
                          + duracion_minutos * INTERVAL '1 minute'
                          > (%s::date - INTERVAL '1 day')
                    ORDER BY fecha_hora_inicio;
                    """,
                    (fecha_iso, fecha_iso),
                )
                reservas_rows = cur.fetchall()

                # 4) Schedule blocks around the day (id_mesa IS NULL
                #    means a general block affecting every mesa).
                cur.execute(
                    """
                    SELECT id_mesa, inicio, fin
                    FROM bloqueos_horario
                    WHERE inicio < (%s::date + INTERVAL '2 days')
                      AND fin > (%s::date - INTERVAL '1 day')
                    ORDER BY inicio;
                    """,
                    (fecha_iso, fecha_iso),
                )
                bloqueos_rows = cur.fetchall()

        # --- Slot computation (pure Python, no database access). ---
        candidate_ids = [row["id_mesa"] for row in mesas_rows]

        reservas_intervals = []
        for row in reservas_rows:
            inicio = _as_naive_wall_clock(row["fecha_hora_inicio"])
            fin = inicio + timedelta(minutes=int(row["duracion_minutos"]))
            reservas_intervals.append((row["id_mesa"], inicio, fin))

        bloqueo_intervals = [
            (
                row["id_mesa"],
                _as_naive_wall_clock(row["inicio"]),
                _as_naive_wall_clock(row["fin"]),
            )
            for row in bloqueos_rows
        ]

        # Candidate slot windows: start -> end, per active horario row,
        # keeping only slots whose whole reservation fits before closing.
        windows = {}
        for horario in horarios_rows:
            apertura = _as_time(horario["hora_apertura"])
            cierre = _as_time(horario["hora_cierre"])
            intervalo = max(1, int(horario["intervalo_minutos"]))
            cierre_dt = datetime.combine(fecha_date, cierre)
            slot_start = datetime.combine(fecha_date, apertura)
            while True:
                slot_end = slot_start + timedelta(minutes=duracion)
                if slot_start >= cierre_dt or slot_end > cierre_dt:
                    break
                windows.setdefault(slot_start, slot_end)
                slot_start += timedelta(minutes=intervalo)

        slots = []
        for slot_start in sorted(windows):
            slot_end = windows[slot_start]
            unavailable = set()
            general_block = False
            for id_mesa_r, r_start, r_end in reservas_intervals:
                if _intervals_overlap(slot_start, slot_end, r_start, r_end):
                    unavailable.add(id_mesa_r)
            for id_mesa_b, b_start, b_end in bloqueo_intervals:
                if not _intervals_overlap(slot_start, slot_end, b_start, b_end):
                    continue
                if id_mesa_b is None:
                    general_block = True
                else:
                    unavailable.add(id_mesa_b)
            if general_block:
                available_count = 0
            else:
                available_count = sum(
                    1 for id_mesa in candidate_ids if id_mesa not in unavailable
                )
            slots.append(
                {
                    "hora": slot_start.strftime("%H:%M"),
                    "disponible": available_count > 0,
                    "mesas_disponibles": available_count,
                }
            )

        payload = {
            "fecha": fecha_iso,
            "dia_semana": dia_semana,
            "capacidad_requerida": personas,
            "duracion_minutos": duracion,
            "mesas": [
                {
                    "id_mesa": row["id_mesa"],
                    "numero_mesa": row["numero_mesa"],
                    "capacidad": int(row["capacidad"]),
                }
                for row in mesas_rows
            ],
            "horarios": [
                {
                    "hora_apertura": _as_time(h["hora_apertura"]).strftime("%H:%M"),
                    "hora_cierre": _as_time(h["hora_cierre"]).strftime("%H:%M"),
                    "intervalo_minutos": int(h["intervalo_minutos"]),
                }
                for h in horarios_rows
            ],
            "slots_disponibles": sum(1 for slot in slots if slot["disponible"]),
            "slots": slots,
        }
    except HTTPException:
        raise
    except psycopg.OperationalError:
        logger.exception(
            "Database connection failed while checking availability for %s",
            fecha_iso,
        )
        raise HTTPException(status_code=503, detail="Database connection failed")
    except Exception:
        logger.exception(
            "Unexpected error while checking availability for %s", fecha_iso
        )
        raise HTTPException(status_code=500, detail="Internal server error")
    return {"data": payload}


# ---------------------------------------------------------------------------
# Reportes (Sprint 4, gap G4): read-only reservation reporting.
# ---------------------------------------------------------------------------

# The six states of the ``reservas`` CHECK constraint. An ``estado``
# filter outside this whitelist is rejected with 400 before any SQL
# runs, so only trusted literals can ever reach the query.
_ESTADOS_RESERVA = (
    "pendiente",
    "aprobada",
    "confirmada",
    "rechazada",
    "cancelada",
    "completada",
)


def _parse_reporte_params(fecha_inicio, fecha_fin, estado, id_cliente, id_mesa):
    """Validate the query string of GET /api/v1/reportes/reservas (400 on error).

    The parameters are read as raw strings and parsed manually so that
    every invalid input answers ``400 Bad Request`` (this endpoint's
    specification) instead of FastAPI's default ``422``. Optional
    parameters sent empty are treated as absent.

    Returns ``(filters, conditions, params)``: ``filters`` is the
    normalized echo of the request, ``conditions`` are **static** SQL
    fragments joined with AND, and ``params`` holds their values in
    order. User-controlled values travel exclusively inside ``params``
    (F-07: never interpolated into the SQL text).
    """
    filters = {
        "fecha_inicio": None,
        "fecha_fin": None,
        "estado": None,
        "id_cliente": None,
        "id_mesa": None,
    }
    conditions = []
    params = []

    inicio_date = None
    if fecha_inicio is not None and fecha_inicio.strip():
        try:
            inicio_date = date.fromisoformat(fecha_inicio.strip())
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Query parameter 'fecha_inicio' must be a valid date "
                    "in YYYY-MM-DD format"
                ),
            ) from exc
        filters["fecha_inicio"] = inicio_date.isoformat()
        conditions.append("fecha_hora_inicio >= %s::date")
        params.append(inicio_date.isoformat())

    fin_date = None
    if fecha_fin is not None and fecha_fin.strip():
        try:
            fin_date = date.fromisoformat(fecha_fin.strip())
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Query parameter 'fecha_fin' must be a valid date "
                    "in YYYY-MM-DD format"
                ),
            ) from exc
        filters["fecha_fin"] = fin_date.isoformat()
        # Inclusive upper bound: everything before the next day starts.
        conditions.append(
            "fecha_hora_inicio < (%s::date + INTERVAL '1 day')"
        )
        params.append(fin_date.isoformat())

    if inicio_date is not None and fin_date is not None and inicio_date > fin_date:
        raise HTTPException(
            status_code=400,
            detail="'fecha_inicio' must be on or before 'fecha_fin'",
        )

    if estado is not None and estado.strip():
        valor = estado.strip()
        if valor not in _ESTADOS_RESERVA:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Query parameter 'estado' must be one of: "
                    + ", ".join(_ESTADOS_RESERVA)
                ),
            )
        filters["estado"] = valor
        conditions.append("estado = %s")
        params.append(valor)

    for name, value in (("id_cliente", id_cliente), ("id_mesa", id_mesa)):
        if value is None or not value.strip():
            continue
        try:
            parsed = int(value.strip())
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Query parameter '{name}' must be a positive integer",
            ) from exc
        if parsed < 1:
            raise HTTPException(
                status_code=400,
                detail=f"Query parameter '{name}' must be a positive integer",
            )
        filters[name] = parsed
        conditions.append(f"{name} = %s")
        params.append(parsed)

    return filters, conditions, params


@app.get("/api/v1/reportes/reservas")
def reservation_report(
    fecha_inicio: str | None = None,
    fecha_fin: str | None = None,
    estado: str | None = None,
    id_cliente: str | None = None,
    id_mesa: str | None = None,
    user: CurrentUser = Depends(require_roles(ROLE_ADMIN)),
):
    """Reservation report with filters (administrators only, read-only).

    Query parameters (all optional; empty values are treated as
    absent):
        * ``fecha_inicio`` / ``fecha_fin`` - inclusive ``YYYY-MM-DD``
          range on ``fecha_hora_inicio`` (``fecha_inicio`` after
          ``fecha_fin`` is rejected with 400).
        * ``estado`` - one of the six reservation states.
        * ``id_cliente`` / ``id_mesa`` - positive integers.

    Invalid filters answer ``400 Bad Request`` (parsed manually, never
    FastAPI's 422). The response carries ``filtros`` (echo of the
    normalized filters), ``resumen`` (``total_reservas`` and
    ``por_estado`` counts of the filtered set) and ``reservas`` (rows
    ordered by ``fecha_hora_inicio``).

    F-01: the report reads only this service's own ``reservas`` table
    — client and mesa ids are filter values, never joins into another
    service's tables, and the report performs no HTTP calls. The WHERE
    clause is assembled exclusively from static fragments and every
    filter value travels as a ``%s`` parameter (F-07).
    """
    filters, conditions, params = _parse_reporte_params(
        fecha_inicio, fecha_fin, estado, id_cliente, id_mesa
    )
    # ``where`` can only ever contain the static fragments appended by
    # _parse_reporte_params; user values live exclusively in params.
    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    bound = tuple(params)

    try:
        with get_connection(row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT {_RESERVA_COLUMNS}
                    FROM reservas{where}
                    ORDER BY fecha_hora_inicio, codigo_reserva;
                    """,
                    bound,
                )
                rows = cur.fetchall()

                cur.execute(
                    f"""
                    SELECT estado, COUNT(*) AS total
                    FROM reservas{where}
                    GROUP BY estado;
                    """,
                    bound,
                )
                counts = cur.fetchall()

        por_estado = {nombre: 0 for nombre in _ESTADOS_RESERVA}
        for row in counts:
            por_estado[row["estado"]] = int(row["total"])

        payload = {
            "filtros": filters,
            "resumen": {
                "total_reservas": sum(por_estado.values()),
                "por_estado": por_estado,
            },
            "reservas": rows,
        }
    except HTTPException:
        raise
    except psycopg.OperationalError:
        logger.exception("Database connection failed while running the report")
        raise HTTPException(status_code=503, detail="Database connection failed")
    except Exception:
        logger.exception("Unexpected error while running the report")
        raise HTTPException(status_code=500, detail="Internal server error")
    return {"data": payload}

