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

    Args:
        conn: Active database connection (within a transaction).
        event_type: Event type (e.g. 'reserva.creada', 'reserva.estado_cambiado').
        payload: Event payload as a dictionary (will be stored as JSONB).
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO outbox_events (tipo_evento, payload)
            VALUES (%s, %s::jsonb);
            """,
            (event_type, json.dumps(payload, default=str)),
        )
