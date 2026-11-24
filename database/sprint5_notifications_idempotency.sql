-- =====================================================================
-- Sprint 5 - Idempotency constraint for notificaciones table.
--
-- Adds a unique constraint on (id_reserva, tipo, destinatario) to
-- prevent duplicate notifications from concurrent consumers or retries.
--
-- SAFETY / IDEMPOTENCY:
--   * ADD CONSTRAINT IF NOT EXISTS is not supported in PostgreSQL,
--     so we use a DO block to check existence first.
--   * No existing data is modified.
--   * Only adds a constraint, does not delete or modify rows.
--
-- PREREQUISITES:
--   * Verify no duplicate (id_reserva, tipo, destinatario) rows exist.
--   * Approval from the team (DDL change to NeonDB).
--   * Run in a transaction; ROLLBACK if any step fails.
--
-- NOTE: This migration has NOT been applied to the live database.
--       It is provided as a prepared solution for team review.
-- =====================================================================

-- Check for existing duplicates before adding constraint:
-- SELECT id_reserva, tipo, destinatario, count(*) 
-- FROM notificaciones 
-- GROUP BY id_reserva, tipo, destinatario 
-- HAVING count(*) > 1;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'uq_notificacion_reserva_tipo_destinatario'
    ) THEN
        ALTER TABLE public.notificaciones
        ADD CONSTRAINT uq_notificacion_reserva_tipo_destinatario
        UNIQUE (id_reserva, tipo, destinatario);
    END IF;
END $$;

-- Verification (read-only, safe to run at any time):
--   SELECT conname, contype 
--     FROM pg_constraint 
--     WHERE conname = 'uq_notificacion_reserva_tipo_destinatario';
