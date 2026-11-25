"""Transactional Outbox helper for the reservas microservice (Sprint 5).

Writes events to the ``outbox_events`` table within the same database
transaction as the business operation, so that events are never lost even
if Redis is temporarily unavailable. A separate publisher process (or
background task) reads unprocessed events and publishes them to Redis
Streams.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import psycopg

logger = logging.getLogger(__name__)


def record_event(
    conn: psycopg.Connection,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    """Record an event in the outbox_events table.

    Must be called within an existing database transaction so that the
    event is committed (or rolled back) together with the business
    operation. The publisher process reads unprocessed events and
    publishes them to Redis Streams.

    If the outbox_events table does not exist (migration not yet applied),
    logs a warning and returns without raising, so that the business
    operation is not blocked. This is a graceful degradation: the
    reservation is still created, but the notification event is lost.
    Once the migration is applied, events will be recorded atomically.

    Args:
        conn: Active database connection (within a transaction).
        event_type: Event type (e.g. 'reserva.creada', 'reserva.estado_cambiado').
        payload: Event payload as a dictionary (will be stored as JSONB).
    """
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO outbox_events (tipo_evento, payload)
                VALUES (%s, %s::jsonb);
                """,
                (event_type, json.dumps(payload, default=str)),
            )
    except psycopg.errors.UndefinedTable:
        # The outbox_events table has not been created yet (migration not
        # applied to this database). Log a warning and continue so the
        # business operation is not blocked. This is a known limitation
        # until the migration is applied.
        logger.warning(
            "outbox_events table does not exist; event '%s' not recorded. "
            "Apply migration database/sprint5_outbox_events.sql to enable "
            "the Transactional Outbox pattern.",
            event_type,
        )
    except Exception:
        logger.exception("Failed to record outbox event %s", event_type)
        raise
