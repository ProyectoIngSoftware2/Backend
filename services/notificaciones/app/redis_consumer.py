"""Redis Streams consumer for the notificaciones microservice (Sprint 5).

Consumes events from the ``reservas.events`` stream and creates
notifications in the database. Uses consumer groups for idempotent
processing and at-least-once delivery.
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

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
RESERVAS_STREAM = "reservas.events"
CONSUMER_GROUP = "notificaciones"
CONSUMER_NAME = "notificaciones-1"
POLL_INTERVAL = 2.0
MAX_RETRIES = 5


class NotificationConsumer:
    """Background consumer that reads events from Redis Streams and
    creates notifications in the database.

    Uses consumer groups for idempotent processing. Each event is
    processed exactly once (at-least-once delivery with idempotent
    consumers).
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

    def _ensure_consumer_group(self, redis_client: redis.Redis) -> None:
        """Create the consumer group if it doesn't exist."""
        try:
            redis_client.xgroup_create(
                RESERVAS_STREAM, CONSUMER_GROUP, id="0", mkstream=True
            )
        except redis.exceptions.ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    def _process_event(self, event_id: str, event_type: str, payload: dict) -> bool:
        """Process a single event. Returns True on success."""
        try:
            if event_type == "reserva.creada":
                return self._handle_reserva_creada(payload)
            elif event_type == "reserva.estado_cambiado":
                return self._handle_reserva_estado_cambiado(payload)
            else:
                logger.warning("Unknown event type: %s", event_type)
                return True
        except Exception:
            logger.exception("Error processing event %s (%s)", event_id, event_type)
            return False

    def _handle_reserva_creada(self, payload: dict) -> bool:
        """Create a notification when a reservation is created."""
        id_reserva = payload.get("id_reserva")
        codigo = payload.get("codigo_reserva", "")
        try:
            with get_connection(row_factory=None) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT 1 FROM notificaciones WHERE id_reserva = %s AND tipo = 'reserva_recibida';",
                        (id_reserva,),
                    )
                    if cur.fetchone() is not None:
                        return True
                    cur.execute(
                        "INSERT INTO notificaciones (id_reserva, destinatario, tipo, mensaje) VALUES (%s, %s, %s, %s);",
                        (id_reserva, "administrador", "reserva_recibida",
                         f"Se recibió una nueva solicitud de reserva: {codigo}"),
                    )
                conn.commit()
            return True
        except Exception:
            logger.exception("Error creating notification for reservation %s", id_reserva)
            return False

    def _handle_reserva_estado_cambiado(self, payload: dict) -> bool:
        """Create a notification when a reservation status changes."""
        id_reserva = payload.get("id_reserva")
        codigo = payload.get("codigo_reserva", "")
        estado_nuevo = payload.get("estado_nuevo", "")

        tipo_map = {
            "aprobada": "reserva_aprobada",
            "confirmada": "reserva_confirmada",
            "rechazada": "reserva_rechazada",
            "cancelada": "reserva_cancelada",
        }
        tipo = tipo_map.get(estado_nuevo)
        if tipo is None:
            return True

        try:
            with get_connection(row_factory=None) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT 1 FROM notificaciones WHERE id_reserva = %s AND tipo = %s;",
                        (id_reserva, tipo),
                    )
                    if cur.fetchone() is not None:
                        return True
                    cur.execute(
                        "INSERT INTO notificaciones (id_reserva, destinatario, tipo, mensaje) VALUES (%s, %s, %s, %s);",
                        (id_reserva, "cliente", tipo,
                         f"La reserva {codigo} cambió al estado: {estado_nuevo}."),
                    )
                conn.commit()
            return True
        except Exception:
            logger.exception("Error creating notification for reservation %s", id_reserva)
            return False

    def _process_pending_messages(self, redis_client: redis.Redis) -> int:
        """Process pending messages. Returns count processed."""
        processed = 0
        try:
            messages = redis_client.xreadgroup(
                CONSUMER_GROUP,
                CONSUMER_NAME,
                {RESERVAS_STREAM: "0"},
                count=10,
                block=1000,
            )
            if messages:
                for stream_name, message_list in messages:
                    for message_id, data in message_list:
                        event_type = data.get("event_type", "")
                        payload_str = data.get("payload", "{}")
                        try:
                            payload = json.loads(payload_str)
                        except json.JSONDecodeError:
                            payload = {}
                        success = self._process_event(message_id, event_type, payload)
                        if success:
                            redis_client.xack(RESERVAS_STREAM, CONSUMER_GROUP, message_id)
                            processed += 1
                        else:
                            logger.warning("Failed to process event %s, will retry", message_id)
        except Exception:
            logger.exception("Error reading from Redis Stream")
        return processed

    def _run(self) -> None:
        """Main consumption loop."""
        logger.info("NotificationConsumer started (polling every %.1fs)", POLL_INTERVAL)
        while self._running:
            redis_client = self._connect_redis()
            if redis_client is None:
                time.sleep(POLL_INTERVAL)
                continue
            try:
                self._ensure_consumer_group(redis_client)
            except Exception:
                logger.exception("Failed to create consumer group")
                time.sleep(POLL_INTERVAL)
                continue
            try:
                count = self._process_pending_messages(redis_client)
                if count > 0:
                    logger.info("Processed %d events", count)
            except Exception:
                logger.exception("Error in consumer loop")
            time.sleep(POLL_INTERVAL)
        logger.info("NotificationConsumer stopped")

    def start(self) -> None:
        """Start the consumer in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the consumer."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=10.0)
            self._thread = None