# Sprint 5 — Recuperación ante Errores

## 1. Escenarios de fallo y recuperación

### 1.1 Redis caído

**Síntoma:** Publisher no puede publicar eventos. Consumer no puede leer.

**Comportamiento:**
- Publisher reintenta en siguiente ciclo (5s)
- Eventos quedan pendientes en `outbox_events` (procesado=false)
- No se pierden eventos

**Recuperación:**
1. Levantar Redis: `docker compose up -d redis`
2. Publisher publica eventos pendientes automáticamente
3. Consumer procesa mensajes pendientes

### 1.2 Consumer caído

**Síntoma:** Mensajes acumulados en stream, no se crean notificaciones.

**Comportamiento:**
- Mensajes quedan en consumer group como pending
- Al reiniciar consumer, procesa mensajes pendientes
- Idempotencia evita duplicados

**Recuperación:**
1. Reiniciar microservicio notificaciones
2. Consumer lee mensajes pendientes del grupo
3. Notificaciones se crean (idempotentes)

### 1.3 Fallo al crear reserva

**Síntoma:** Error en API de reservas.

**Comportamiento:**
- Transacción completa se revierte (ROLLBACK)
- No se crea evento en outbox
- No se publica en Redis
- No se crea notificación

**Recuperación:** Automática (transacción atómica)

### 1.4 Mensaje duplicado en Redis

**Síntoma:** Mismo evento publicado dos veces.

**Comportamiento:**
- Consumer intenta crear notificación duplicada
- Constraint `uq_notificacion_reserva_tipo_destinatario` rechaza
- Código maneja `UniqueViolation` como éxito
- No se crea duplicado

**Recuperación:** Automática (idempotencia)

### 1.5 Tabla outbox_events no existe

**Síntoma:** Error al crear reserva (en entorno sin migración).

**Comportamiento:**
- `record_event()` captura `UndefinedTable`
- Registra warning en logs
- Operación de negocio continúa (reserva se crea)
- Evento no se registra

**Recuperación:** Aplicar migración `sprint5_outbox_events.sql`

## 2. Procedimientos de diagnóstico

### 2.1 Verificar eventos pendientes

```sql
SELECT id_evento, tipo_evento, procesado, intentos, error
FROM outbox_events
WHERE procesado = false
ORDER BY fecha_creacion;
```

### 2.2 Verificar mensajes pendientes en Redis

```bash
redis-cli XPENDING reservas.events notificaciones
```

### 2.3 Verificar notificaciones duplicadas

```sql
SELECT id_reserva, tipo, destinatario, count(*)
FROM notificaciones
GROUP BY id_reserva, tipo, destinatario
HAVING count(*) > 1;
```

### 2.4 Verificar health de servicios

```bash
curl http://localhost:8000/health  # Gateway
curl http://localhost:8005/health  # Notificaciones
redis-cli ping                      # Redis
```

## 3. Logs importantes

| Servicio | Log | Significado |
|----------|-----|-------------|
| Reservas | "Unexpected error while creating a reservation" | Error al crear reserva |
| Publisher | "Event published to Redis" | Evento publicado exitosamente |
| Publisher | "Failed to publish event" | Error al publicar (se reintentará) |
| Consumer | "Notification created" | Notificación creada |
| Consumer | "Duplicate notification, skipping" | Idempotencia activada |

## 4. Contacto de emergencia

En caso de fallo crítico:
1. Verificar logs de Docker: `docker compose logs`
2. Verificar conexión a NeonDB: `SELECT 1`
3. Verificar Redis: `redis-cli ping`
4. Restaurar desde backup si es necesario (ver ESTADO_RESPALDO_Y_RESTAURACION_NEONDB.md)
