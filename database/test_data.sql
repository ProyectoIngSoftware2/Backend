-- =====================================================================
-- Idempotent test data for Punto y Sal (NeonDB).
--
-- STATUS: EXECUTED on 2026-11-01 with explicit team approval
-- (22 rows inserted; an immediate re-run inserted 0 rows, confirming the
-- WHERE NOT EXISTS guards keep it safe to re-run; see database/README.md).
--
-- Safety properties:
--   * INSERT only: no DROP, TRUNCATE, ALTER, UPDATE or DELETE of any
--     existing row.
--   * Every INSERT is guarded by a per-row WHERE NOT EXISTS predicate
--     that matches the business identity of the row being inserted
--     (natural keys such as correo, numero_identidad, numero_mesa and
--     nombre, and the full business fingerprint of each test
--     reservation). No ON CONFLICT clauses are used; the WHERE NOT
--     EXISTS guards are what make sequential re-runs insert nothing
--     and never duplicate rows.
--   * Foreign-key order respected: administradores -> clientes -> mesas
--     -> platillos -> reservas -> reserva_platillos.
--   * codigo_reserva, historial_estados and notificaciones rows are
--     created automatically by the existing database triggers; this
--     script does not insert them manually.
--   * Reservations use fixed future dates, different tables and
--     capacity-appropriate guest counts to satisfy validar_reserva_mesa.
--   * reserva_platillos rows are attached only to the reservation whose
--     full business fingerprint matches (customer, table, date/time,
--     duration, guests, status and note) — never to a reservation that
--     merely shares the timestamp.
-- =====================================================================

-- 1) Test administrator (password is a PLACEHOLDER, not a real secret).
--    Sprint 2 will replace it with a properly hashed password.
INSERT INTO administradores (nombre_completo, correo, password_hash, activo)
SELECT 'Administrador de Prueba', 'admin.prueba@puntoysal.test',
       'PLACEHOLDER_SPRINT2_WILL_HASH_THIS', true
WHERE NOT EXISTS (
    SELECT 1 FROM administradores WHERE correo = 'admin.prueba@puntoysal.test'
);

-- 2) Test customers (unique numero_identidad).
INSERT INTO clientes (nombre_completo, numero_identidad, telefono, correo, activo)
SELECT * FROM (VALUES
    ('Ana Lopez',      '0801199000123', '+504 9999-0001', 'ana.lopez@example.com',   true),
    ('Carlos Mejia',   '0801199100456', '+504 9999-0002', 'carlos.mejia@example.com', true),
    ('Maria Fernandez','0801199200789', '+504 9999-0003', 'maria.fernandez@example.com', true)
) AS v(nombre_completo, numero_identidad, telefono, correo, activo)
WHERE NOT EXISTS (
    SELECT 1 FROM clientes c
    WHERE c.numero_identidad = v.numero_identidad
);

-- 3) Restaurant tables (unique numero_mesa).
INSERT INTO mesas (numero_mesa, capacidad, ubicacion, estado, activa)
SELECT * FROM (VALUES
    ('1', 2, 'Salon principal',   'disponible',    true),
    ('2', 4, 'Salon principal',   'disponible',    true),
    ('3', 6, 'Terraza',           'disponible',    true),
    ('4', 4, 'Terraza',           'mantenimiento', true)
) AS v(numero_mesa, capacidad, ubicacion, estado, activa)
WHERE NOT EXISTS (
    SELECT 1 FROM mesas m WHERE m.numero_mesa = v.numero_mesa
);

-- 4) Menu items (no unique constraint on nombre, so guard with NOT EXISTS).
INSERT INTO platillos (nombre, descripcion, precio, disponible)
SELECT * FROM (VALUES
    ('Filete de pescado a la plancha', 'Pescado fresco con arroz y ensalada',       180.00, true),
    ('Baleada tradicional',            'Tortilla, frijoles, queso y crema',          45.00, true),
    ('Pollo a la parrilla',            'Pollo con papa frita y ensalada',           150.00, true),
    ('Ensalada Cesar',                 'Lechuga, pollo y aderezo Cesar',             95.00, true),
    ('Refresco natural de maracuya',   'Bebida natural 500ml',                       35.00, false)
) AS v(nombre, descripcion, precio, disponible)
WHERE NOT EXISTS (
    SELECT 1 FROM platillos p WHERE p.nombre = v.nombre
);

-- 5) Reservations (fixed future dates, different tables, guest count
--    within table capacity). Estado starts at 'pendiente'; the triggers
--    generate codigo_reserva, fecha_actualizacion, historial and
--    notificaciones automatically. The idempotency guard matches the
--    customer, the table AND the date/time, so an unrelated reservation
--    that merely shares the timestamp never blocks (or duplicates) ours.
INSERT INTO reservas (
    id_cliente, id_mesa, fecha_hora_inicio, duracion_minutos,
    cantidad_personas, estado, observaciones
)
SELECT c.id_cliente, m.id_mesa, v.fecha_hora_inicio, v.duracion_minutos,
       v.cantidad_personas, v.estado, v.observaciones
FROM (VALUES
    ('0801199000123', '1', '2027-03-15 19:00:00-06'::timestamptz, 120, 2,
     'pendiente', 'Reserva de prueba Sprint 1'),
    ('0801199100456', '2', '2027-03-16 20:00:00-06'::timestamptz, 90,  4,
     'pendiente', 'Reserva de prueba Sprint 1')
) AS v(numero_identidad, numero_mesa, fecha_hora_inicio, duracion_minutos,
       cantidad_personas, estado, observaciones)
JOIN clientes c ON c.numero_identidad = v.numero_identidad
JOIN mesas m    ON m.numero_mesa = v.numero_mesa
WHERE NOT EXISTS (
    SELECT 1 FROM reservas r
    WHERE r.id_cliente = c.id_cliente
      AND r.id_mesa = m.id_mesa
      AND r.fecha_hora_inicio = v.fecha_hora_inicio
);

-- 6) Dishes attached to the reservations. precio_unitario snapshots the
--    current menu price. Each target reservation is identified by its
--    FULL business fingerprint (customer + table + date/time + duration
--    + guests + status + note), so a dish can never attach to a
--    different reservation that merely shares the timestamp. The
--    per-row NOT EXISTS guard on (id_reserva, id_platillo) makes
--    sequential re-runs insert nothing.
INSERT INTO reserva_platillos (
    id_reserva, id_platillo, cantidad, precio_unitario, observaciones
)
SELECT objetivo.id_reserva, p.id_platillo, 2, p.precio, NULL
FROM (
    SELECT r.id_reserva
    FROM reservas r
    JOIN clientes c ON c.id_cliente = r.id_cliente
    JOIN mesas m    ON m.id_mesa = r.id_mesa
    WHERE c.numero_identidad = '0801199000123'
      AND m.numero_mesa = '1'
      AND r.fecha_hora_inicio = '2027-03-15 19:00:00-06'::timestamptz
      AND r.duracion_minutos = 120
      AND r.cantidad_personas = 2
      AND r.estado = 'pendiente'
      AND r.observaciones = 'Reserva de prueba Sprint 1'
) AS objetivo
JOIN platillos p ON p.nombre IN ('Filete de pescado a la plancha', 'Baleada tradicional')
WHERE NOT EXISTS (
    SELECT 1 FROM reserva_platillos rp
    WHERE rp.id_reserva = objetivo.id_reserva
      AND rp.id_platillo = p.id_platillo
);

INSERT INTO reserva_platillos (
    id_reserva, id_platillo, cantidad, precio_unitario, observaciones
)
SELECT objetivo.id_reserva, p.id_platillo, 1, p.precio, 'Sin cebolla'
FROM (
    SELECT r.id_reserva
    FROM reservas r
    JOIN clientes c ON c.id_cliente = r.id_cliente
    JOIN mesas m    ON m.id_mesa = r.id_mesa
    WHERE c.numero_identidad = '0801199100456'
      AND m.numero_mesa = '2'
      AND r.fecha_hora_inicio = '2027-03-16 20:00:00-06'::timestamptz
      AND r.duracion_minutos = 90
      AND r.cantidad_personas = 4
      AND r.estado = 'pendiente'
      AND r.observaciones = 'Reserva de prueba Sprint 1'
) AS objetivo
JOIN platillos p ON p.nombre = 'Pollo a la parrilla'
WHERE NOT EXISTS (
    SELECT 1 FROM reserva_platillos rp
    WHERE rp.id_reserva = objetivo.id_reserva
      AND rp.id_platillo = p.id_platillo
);

-- =====================================================================
-- Post-verification queries (read-only): expect non-zero counts for
-- clientes, mesas, platillos, reservas and reserva_platillos, plus the
-- automatic historial_estados / notificaciones rows created by triggers.
-- =====================================================================
SELECT 'administradores' AS table_name, count(*) AS rows FROM administradores
UNION ALL SELECT 'clientes', count(*) FROM clientes
UNION ALL SELECT 'mesas', count(*) FROM mesas
UNION ALL SELECT 'platillos', count(*) FROM platillos
UNION ALL SELECT 'reservas', count(*) FROM reservas
UNION ALL SELECT 'reserva_platillos', count(*) FROM reserva_platillos
UNION ALL SELECT 'historial_estados', count(*) FROM historial_estados
UNION ALL SELECT 'notificaciones', count(*) FROM notificaciones;
