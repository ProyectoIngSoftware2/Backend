# Sprint 5 — Migraciones

## 1. Migraciones aplicadas

### 1.1 Outbox Events

**Archivo:** `database/sprint5_outbox_events.sql`
**Estado:** ✅ Aplicada en NeonDB

```sql
CREATE TABLE IF NOT EXISTS outbox_events (
    id_evento SERIAL PRIMARY KEY,
    tipo_evento VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    procesado BOOLEAN NOT NULL DEFAULT false,
    intentos INTEGER NOT NULL DEFAULT 0,
    fecha_creacion TIMESTAMP NOT NULL DEFAULT now(),
    fecha_procesado TIMESTAMP,
    error TEXT
);

CREATE INDEX IF NOT EXISTS idx_outbox_events_pendientes
ON outbox_events (fecha_creacion)
WHERE procesado = false;
```

### 1.2 Triggers G1/G2

**Archivo:** `database/sprint5_g1_g2_validation_triggers.sql`
**Estado:** ✅ Aplicada en NeonDB

```sql
-- G1: Validación de solapamiento de horarios
CREATE OR REPLACE FUNCTION validar_solapamiento_horarios()
RETURNS TRIGGER AS $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM horarios
        WHERE dia_semana = NEW.dia_semana
        AND id_horario != COALESCE(NEW.id_horario, 0)
        AND (NEW.hora_apertura < hora_cierre AND NEW.hora_cierre > hora_apertura)
    ) THEN
        RAISE EXCEPTION 'Horario solapado para el día %', NEW.dia_semana;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_horarios_validar_solapamiento
BEFORE INSERT OR UPDATE ON horarios
FOR EACH ROW
EXECUTE FUNCTION validar_solapamiento_horarios();

-- G2: Validación de solapamiento de bloqueos
CREATE OR REPLACE FUNCTION validar_solapamiento_bloqueos()
RETURNS TRIGGER AS $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM bloqueos_horario
        WHERE id_mesa = NEW.id_mesa
        AND id_bloqueo != COALESCE(NEW.id_bloqueo, 0)
        AND (NEW.fecha_hora_inicio < fecha_hora_fin AND NEW.fecha_hora_fin > fecha_hora_inicio)
    ) THEN
        RAISE EXCEPTION 'Bloqueo solapado para la mesa %', NEW.id_mesa;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_bloqueos_validar_solapamiento
BEFORE INSERT OR UPDATE ON bloqueos_horario
FOR EACH ROW
EXECUTE FUNCTION validar_solapamiento_bloqueos();
```

### 1.3 Idempotencia de Notificaciones

**Archivo:** `database/sprint5_notifications_idempotency.sql`
**Estado:** ✅ Aplicada en NeonDB

```sql
ALTER TABLE notificaciones
ADD CONSTRAINT uq_notificacion_reserva_tipo_destinatario
UNIQUE (id_reserva, tipo, destinatario);
```

## 2. Orden de aplicación

1. `sprint5_outbox_events.sql` (tabla + índice)
2. `sprint5_g1_g2_validation_triggers.sql` (funciones + triggers)
3. `sprint5_notifications_idempotency.sql` (constraint)

## 3. Verificación post-migración

```sql
-- Verificar tabla outbox_events
SELECT count(*) FROM outbox_events;

-- Verificar triggers
SELECT tgname FROM pg_trigger
WHERE tgname IN ('trg_horarios_validar_solapamiento', 'trg_bloqueos_validar_solapamiento');

-- Verificar constraint
SELECT conname FROM pg_constraint
WHERE conname = 'uq_notificacion_reserva_tipo_destinatario';
```

## 4. Reversión (rollback)

Las migraciones son idempotentes (`IF NOT EXISTS`, `CREATE OR REPLACE`). Para revertir:

```sql
-- Revertir idempotencia
ALTER TABLE notificaciones DROP CONSTRAINT IF EXISTS uq_notificacion_reserva_tipo_destinatario;

-- Revertir triggers
DROP TRIGGER IF EXISTS trg_horarios_validar_solapamiento ON horarios;
DROP TRIGGER IF EXISTS trg_bloqueos_validar_solapamiento ON bloqueos_horario;
DROP FUNCTION IF EXISTS validar_solapamiento_horarios();
DROP FUNCTION IF EXISTS validar_solapamiento_bloqueos();

-- Revertir outbox (CUIDADO: pierde datos)
-- DROP TABLE IF EXISTS outbox_events;
```

**Nota:** No se recomienda revertir en producción. Las migraciones son aditivas y no destruyen datos.
