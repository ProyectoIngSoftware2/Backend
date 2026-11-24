-- =====================================================================
-- Sprint 5 - Database-level validation triggers for horarios and bloqueos.
--
-- Closes gaps G1 and G2 from the Sprint 4 audit:
--   G1: Schedule overlap validation at DB level (horarios table).
--   G2: Blocking period overlap validation at DB level (bloqueos_horario).
--
-- SAFETY / IDEMPOTENCY:
--   * CREATE OR REPLACE FUNCTION so re-running updates the function.
--   * DROP TRIGGER IF EXISTS + CREATE TRIGGER so re-running is safe.
--   * No existing tables or columns are modified.
--   * No existing triggers are removed.
--   * Uses BIGINT identifiers to match the live database convention.
--
-- PREREQUISITES:
--   * Approval from the team (DDL changes to NeonDB).
--   * Database backup before applying.
--   * Run in a transaction; ROLLBACK if any step fails.
--
-- NOTE: This migration has NOT been applied to the live database.
--       It is provided as a prepared solution for team review.
-- =====================================================================

-- =====================================================================
-- G1: Schedule overlap validation (horarios table).
--     Prevents two active horarios for the same dia_semana that
--     overlap in time.
-- =====================================================================

CREATE OR REPLACE FUNCTION public.validar_horario_solapamiento()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.activo = TRUE THEN
        IF EXISTS (
            SELECT 1
              FROM horarios h
             WHERE h.dia_semana = NEW.dia_semana
               AND h.activo = TRUE
               AND h.id_horario <> COALESCE(NEW.id_horario, -1)
               AND tstzrange(
                    make_timestamp(
                        2000, 1, 1,
                        EXTRACT(HOUR FROM h.hora_apertura)::int,
                        EXTRACT(MINUTE FROM h.hora_apertura)::int,
                        EXTRACT(SECOND FROM h.hora_apertura)::int
                    )::timestamptz,
                    make_timestamp(
                        2000, 1, 1,
                        EXTRACT(HOUR FROM h.hora_cierre)::int,
                        EXTRACT(MINUTE FROM h.hora_cierre)::int,
                        EXTRACT(SECOND FROM h.hora_cierre)::int
                    )::timestamptz,
                    '[)'
               )
               &&
               tstzrange(
                    make_timestamp(
                        2000, 1, 1,
                        EXTRACT(HOUR FROM NEW.hora_apertura)::int,
                        EXTRACT(MINUTE FROM NEW.hora_apertura)::int,
                        EXTRACT(SECOND FROM NEW.hora_apertura)::int
                    )::timestamptz,
                    make_timestamp(
                        2000, 1, 1,
                        EXTRACT(HOUR FROM NEW.hora_cierre)::int,
                        EXTRACT(MINUTE FROM NEW.hora_cierre)::int,
                        EXTRACT(SECOND FROM NEW.hora_cierre)::int
                    )::timestamptz,
                    '[)'
               )
        ) THEN
            RAISE EXCEPTION 'Ya existe un horario activo para el dia % que se solapa con el nuevo horario.',
                NEW.dia_semana;
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_horarios_validar_solapamiento ON public.horarios;

CREATE TRIGGER trg_horarios_validar_solapamiento
    BEFORE INSERT OR UPDATE ON public.horarios
    FOR EACH ROW
    EXECUTE FUNCTION public.validar_horario_solapamiento();

-- =====================================================================
-- G2: Blocking period overlap validation (bloqueos_horario table).
--     Prevents two overlapping bloqueos for the same mesa (or general
--     blockade, id_mesa IS NULL).
-- =====================================================================

CREATE OR REPLACE FUNCTION public.validar_bloqueo_solapamiento()
RETURNS TRIGGER AS $$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM bloqueos_horario b
         WHERE b.id_bloqueo <> COALESCE(NEW.id_bloqueo, -1)
           AND (
               (NEW.id_mesa IS NULL AND b.id_mesa IS NULL)
               OR (NEW.id_mesa IS NOT NULL AND b.id_mesa = NEW.id_mesa)
               OR (NEW.id_mesa IS NULL AND b.id_mesa IS NOT NULL)
               OR (b.id_mesa IS NULL AND NEW.id_mesa IS NOT NULL)
           )
           AND tstzrange(b.inicio, b.fin, '[)')
               &&
               tstzrange(NEW.inicio, NEW.fin, '[)')
    ) THEN
        RAISE EXCEPTION 'Ya existe un bloqueo que se solapa con el nuevo bloqueo para la mesa %.',
            COALESCE(NEW.id_mesa, 'todas (general)');
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_bloqueos_validar_solapamiento ON public.bloqueos_horario;

CREATE TRIGGER trg_bloqueos_validar_solapamiento
    BEFORE INSERT OR UPDATE ON public.bloqueos_horario
    FOR EACH ROW
    EXECUTE FUNCTION public.validar_bloqueo_solapamiento();

-- =====================================================================
-- Verification (read-only, safe to run at any time):
--   SELECT trigger_name, event_object_table
--     FROM information_schema.triggers
--     WHERE trigger_schema = 'public'
--       AND trigger_name IN ('trg_horarios_validar_solapamiento',
--                            'trg_bloqueos_validar_solapamiento')
--     ORDER BY trigger_name;
-- =====================================================================
