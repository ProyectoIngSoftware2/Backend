-- =====================================================================
-- Read-only schema verification for Punto y Sal (NeonDB).
--
-- This script only runs SELECT queries. It is safe to execute at any
-- time and does not modify the database in any way.
-- Verified against the live database on 2026-11-01.
-- =====================================================================

-- 1. The eight approved tables must all exist.
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN (
    'administradores', 'clientes', 'mesas', 'platillos',
    'reservas', 'reserva_platillos', 'historial_estados', 'notificaciones'
  )
ORDER BY table_name;

-- 2. Columns of every table (name, type, nullability, default).
SELECT table_name, ordinal_position, column_name, data_type,
       is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name IN (
    'administradores', 'clientes', 'mesas', 'platillos',
    'reservas', 'reserva_platillos', 'historial_estados', 'notificaciones'
  )
ORDER BY table_name, ordinal_position;

-- 3. Primary keys.
SELECT tc.table_name, kcu.column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name
 AND tc.table_schema = kcu.table_schema
WHERE tc.table_schema = 'public'
  AND tc.constraint_type = 'PRIMARY KEY'
ORDER BY tc.table_name, kcu.ordinal_position;

-- 4. Foreign keys with their delete rules.
SELECT tc.table_name, kcu.column_name,
       ccu.table_name AS ref_table, ccu.column_name AS ref_column,
       rc.delete_rule
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name
 AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage ccu
  ON ccu.constraint_name = tc.constraint_name
 AND ccu.table_schema = tc.table_schema
JOIN information_schema.referential_constraints rc
  ON rc.constraint_name = tc.constraint_name
 AND rc.constraint_schema = tc.table_schema
WHERE tc.table_schema = 'public'
  AND tc.constraint_type = 'FOREIGN KEY'
ORDER BY tc.table_name, kcu.column_name;

-- 5. Unique constraints.
SELECT tc.table_name,
       string_agg(kcu.column_name, ', ' ORDER BY kcu.ordinal_position) AS columns
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name
 AND tc.table_schema = kcu.table_schema
WHERE tc.table_schema = 'public'
  AND tc.constraint_type = 'UNIQUE'
GROUP BY tc.table_name, tc.constraint_name
ORDER BY tc.table_name;

-- 6. Check constraints (status enums, duration range, prices...).
SELECT conrelid::regclass::text AS table_name, conname,
       pg_get_constraintdef(oid) AS definition
FROM pg_constraint
WHERE connamespace = 'public'::regnamespace
  AND contype = 'c'
ORDER BY conrelid::regclass::text, conname;

-- 7. The approved reservation code function must exist.
SELECT p.proname,
       pg_get_function_result(p.oid) AS result_type,
       pg_get_function_arguments(p.oid) AS arguments
FROM pg_proc p
JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE n.nspname = 'public'
  AND p.proname = 'generar_codigo_reserva';

-- 8. Business-logic triggers on reservations and notifications.
SELECT tgname, tgrelid::regclass::text AS table_name
FROM pg_trigger
WHERE NOT tgisinternal
ORDER BY tgrelid::regclass::text, tgname;

-- 9. Indexes used for reservation searches.
SELECT tablename, indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;

-- 10. Current row counts (test-data status).
SELECT 'administradores' AS table_name, count(*) AS rows FROM administradores
UNION ALL SELECT 'clientes', count(*) FROM clientes
UNION ALL SELECT 'mesas', count(*) FROM mesas
UNION ALL SELECT 'platillos', count(*) FROM platillos
UNION ALL SELECT 'reservas', count(*) FROM reservas
UNION ALL SELECT 'reserva_platillos', count(*) FROM reserva_platillos
UNION ALL SELECT 'historial_estados', count(*) FROM historial_estados
UNION ALL SELECT 'notificaciones', count(*) FROM notificaciones;
