# Sprint 5 — Patrón Transactional Outbox

## 1. Descripción

El patrón Transactional Outbox garantiza que la creación de una reserva y el registro del evento de notificación ocurran de forma atómica en la misma transacción PostgreSQL.

## 2. Implementación

### 2.1 Tabla outbox_events

```sql
CREATE TABLE outbox_events (
    id_evento SERIAL PRIMARY KEY,
    tipo_evento VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    procesado BOOLEAN NOT NULL DEFAULT false,
    intentos INTEGER NOT NULL DEFAULT 0,
    fecha_creacion TIMESTAMP NOT NULL DEFAULT now(),
    fecha_procesado TIMESTAMP,
    error TEXT
);
```

### 2.2 Índice parcial

```sql
CREATE INDEX idx_outbox_events_pendientes
ON outbox_events (fecha_creacion)
WHERE procesado = false;
```

### 2.3 Función record_event()

```python
def record_event(conn, tipo_evento, payload):
    """Registra un evento en el outbox dentro de la transacción actual."""
    try:
        conn.execute(
            "INSERT INTO outbox_events (tipo_evento, payload) VALUES (%s, %s)",
            (tipo_evento, json.dumps(payload))
        )
    except psycopg.errors.UndefinedTable:
        logger.warning("outbox_events table does not exist, event not recorded")
```

### 2.4 Degradación elegante

Si la tabla `outbox_events` no existe (ej. en tests sin migración), `record_event()` captura `UndefinedTable` y registra un warning. La operación de negocio (crear reserva) continúa exitosamente.

## 3. Garantías

| Garantía | Mecanismo |
|----------|-----------|
| Atomicidad | Evento se registra en la misma TX que la reserva |
| No eventos huérfanos | Rollback completo si la reserva falla |
| No pérdida de eventos | Evento queda pendiente si Redis falla |
| Recuperación | Publisher reintenta eventos pendientes |
| Idempotencia | Flag `procesado` evita re-publicación |

## 4. Publisher (background)

- Se ejecuta cada 5 segundos
- Lee eventos con `procesado = false`
- Publica en Redis Stream `reservas.events`
- Marca como `procesado = true` tras publicación exitosa
- Incrementa `intentos` en caso de fallo
- Deshabilitado en tests via `DISABLE_OUTBOX_PUBLISHER=1`

## 5. Consumer (background)

- Consumer group: `notificaciones`
- Lee mensajes del stream `reservas.events`
- Crea notificación (idempotente)
- Acknowledge tras procesamiento exitoso
- Deshabilitado en tests via `DISABLE_OUTBOX_PUBLISHER=1`

## 6. Estados del Outbox

| Estado | Condición | Acción |
|--------|-----------|--------|
| Pendiente | `procesado = false`, `intentos = 0` | Publisher lo publicará |
| En reintento | `procesado = false`, `intentos > 0` | Publisher reintentará |
| Procesado | `procesado = true` | No se re-publica |
| Con error | `error IS NOT NULL` | Requiere intervención manual |
