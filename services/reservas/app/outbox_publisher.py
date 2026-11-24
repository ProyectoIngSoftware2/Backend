"""Transactional Outbox publisher for the reservas microservice (Sprint 5).

Reads unprocessed events from the ``outbox_events`` table and publishes
them to Redis Streams. Runs as a background task in the reservas service.

The publisher uses a consumer group pattern for idempotent processing:
each event is published exactly once (at-least-once delivery with
idempotent consumers).
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any

import psycopg
import redis

from shared.database import get_connection

logger = logging.getLogger(__name__)

# Redis connection URL (from environment or default).
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Polling interval in seconds.
POLL_INTERVAL = 5.0

# Stream name for reservation events.
RESERVAS_STREAM = "reservas.events"

# Consumer group name.
CONSUMER_GROUP = "notificaciones"

# Maximum number of retry attempts before marking an event as failed.
MAX_RETRIES = 5


class OutboxPublisher:
    """Background publisher that reads outbox_events and publishes to Redis.

    Runs in a separate thread. Polls the outbox_events table for
    unprocessed events and publishes them to Redis Streams.
    """

    def __init__(self):
        self._redis = None
        self._running = False
        self._thread = None

    def _connect_redis(self) -> redis.Redis | None:
        """Connect to Redis. Returns None if unavailable."""
        try:
            r = redis.from_url(REDIS_URL, decode_responses=True)
            r.ping()
            return r
        except Exception:
            logger.warning("Redis unavailable: %s", REDIS_URL)
            return None

    def _publish_event(self, redis_client: redis.Redis, event_id: int,
                       event_type: str, payload: dict) -> bool:
        """Publish a single event to Redis Streams. Returns True on success."""
        try:
            redis_client.xadd(
                RESERVAS_STREAM,
                {
                    "event_id": str(event_id),
                    "event_type": event_type,
                    "payload": json.dumps(payload, default=str),
                },
            )
            return True
        except Exception:
            logger.exception("Failed to publish event %s to Redis", event_id)
            return False

    def _mark_processed(self, conn: psycopg.Connection, event_id: int) -> None:
        """Mark an event as processed in the outbox_events table."""
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE outbox_events
                   SET procesado = TRUE,
                       fecha_procesado = now()
                 WHERE id_evento = %s;
                """,
                (event_id,),
            )

    def _increment_attempts(self, conn: psycopg.Connection, event_id: int,
                            error: str) -> None:
        """Increment retry counter and record error."""
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE outbox_events
                   SET intentos = intentos + 1,
                       error = %s
                 WHERE id_evento = %s;
                """,
                (error, event_id),
            )

    def _process_pending_events(self) -> int:
        """Process all unprocessed events. Returns count of processed events."""
        processed = 0
        redis_client = self._connect_redis()
        if redis_client is None:
            return 0

        try:
            with get_connection(row_factory=None) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id_evento, tipo_evento, payload
                        FROM outbox_events
                        WHERE procesado = FALSE
                          AND intentos < %s
                        ORDER BY fecha_creacion
                        LIMIT 100;
                        """,
                        (MAX_RETRIES,),
                    )
                    events = cur.fetchall()

                for event_id, event_type, payload in events:
                    if isinstance(payload, str):
                        payload = json.loads(payload)
                    success = self._publish_event(
                        redis_client, event_id, event_type, payload
                    )
                    with get_connection(row_factory=None) as conn2:
                        if success:
                            self._mark_processed(conn2, event_id)
                            processed += 1
                        else:
                            self._increment_attempts(
                                conn2, event_id, "Failed to publish to Redis"
                            )
                    conn2.commit()
        except Exception:
            logger.exception("Error processing outbox events")

        return processed

    def _run(self) -> None:
        """Main polling loop."""
        logger.info("OutboxPublisher started (polling every %.1fs)", POLL_INTERVAL)
        while self._running:
            try:
                count = self._process_pending_events()
                if count > 0:
                    logger.info("Published %d outbox events", count)
            except Exception:
                logger.exception("Error in outbox publisher loop")
            time.sleep(POLL_INTERVAL)
        logger.info("OutboxPublisher stopped")

    def start(self) -> None:
        """Start the publisher in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the publisher."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=10.0)
            self._thread = None
