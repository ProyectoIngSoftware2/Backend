# Database Verification Report (NeonDB)

- **Date:** 2026-11-01
- **Method:** read-only queries against `information_schema` / `pg_catalog`
  (script: `database/schema_verification.sql`)
- **Credentials:** never displayed; connection read from the local `.env`
- **Writes executed:** none (only `SELECT`)

## 1. Tables

All **8 approved tables exist** in schema `public`; none missing:

`administradores`, `clientes`, `historial_estados`, `mesas`,
`notificaciones`, `platillos`, `reserva_platillos`, `reservas`

## 2. Columns (summary)

| Table | Columns verified |
|-------|------------------|
| administradores | id_administrador (PK), nombre_completo, correo, password_hash, activo (default true), fecha_creacion (default now) |
| clientes | id_cliente (PK), nombre_completo, numero_identidad, telefono, correo, fecha_registro, activo |
| mesas | id_mesa (PK), numero_mesa, capacidad, ubicacion, estado (default 'disponible'), activa |
| platillos | id_platillo (PK), nombre, descripcion, precio, disponible, fecha_creacion |
| reservas | id_reserva (PK), codigo_reserva (default `generar_codigo_reserva()`), id_cliente (FK), id_mesa (FK, nullable), fecha_hora_inicio, duracion_minutos (default 120), cantidad_personas, estado (default 'pendiente'), observaciones, fecha_creacion, fecha_actualizacion, id_administrador (FK, nullable) |
| reserva_platillos | id_reserva_platillo (PK), id_reserva (FK), id_platillo (FK), cantidad, precio_unitario, observaciones |
| historial_estados | id_historial (PK), id_reserva (FK), estado_anterior, estado_nuevo, id_administrador (FK), comentario, fecha_cambio |
| notificaciones | id_notificacion (PK), id_reserva (FK), destinatario, tipo, mensaje, leida, fecha_creacion, fecha_lectura |

Types match the approved design: `bigint` identifiers, `varchar` for codes
and enums-as-strings, `numeric` for prices, `timestamptz` for timestamps,
`boolean` flags.

## 3. Keys and constraints

- **Primary keys:** one per table (8/8) ✔
- **Foreign keys (8):**
  - `reservas.id_cliente → clientes.id_cliente`
  - `reservas.id_mesa → mesas.id_mesa`
  - `reservas.id_administrador → administradores.id_administrador`
  - `reserva_platillos.id_reserva → reservas.id_reserva` (**ON DELETE CASCADE**)
  - `reserva_platillos.id_platillo → platillos.id_platillo`
  - `historial_estados.id_reserva → reservas.id_reserva` (CASCADE)
  - `historial_estados.id_administrador → administradores.id_administrador`
  - `notificaciones.id_reserva → reservas.id_reserva` (CASCADE)
- **Unique constraints:** `administradores.correo`,
  `clientes.numero_identidad`, `mesas.numero_mesa`,
  `reservas.codigo_reserva` (two indexes: `reservas_codigo_reserva_key`,
  `uq_reservas_codigo_reserva`), `reserva_platillos (id_reserva, id_platillo)`
  (`uq_reserva_platillo`)
- **Check constraints (12):** reservation status enum (6 values), duration
  15–720, guests > 0, table status enum, capacity > 0, price ≥ 0,
  notification recipient enum, notification type enum (7 values),
  `leida`/`fecha_lectura` consistency, `fecha_lectura ≥ fecha_creacion`

## 4. Approved function and triggers

- `generar_codigo_reserva()` → `character varying` (no args) ✔ **exists**
- Other project functions present: `actualizar_fecha_modificacion_reserva`,
  `crear_notificacion_reserva`, `registrar_historial_estado_reserva`,
  `sincronizar_fecha_lectura_notificacion`, `validar_reserva_mesa`,
  `validar_transicion_estado_reserva`
- **8 triggers:** on `reservas` — `trg_reservas_fecha_actualizacion`,
  `trg_reservas_historial_insert`, `trg_reservas_historial_update`,
  `trg_reservas_notificacion_insert`, `trg_reservas_notificacion_update`,
  `trg_reservas_validar_estado`, `trg_reservas_validar_mesa`; on
  `notificaciones` — `trg_notificaciones_fecha_lectura`

Conclusion: status history, notifications, status-transition validation,
table-overlap validation and modification timestamps are already implemented
**in the database** — the application must not duplicate these rules.

## 5. Indexes (reservation search)

`idx_reservas_cliente`, `idx_reservas_estado`, `idx_reservas_fecha_hora`,
`idx_reservas_mesa_fecha`, `idx_reserva_platillos_reserva`,
`idx_historial_reserva_fecha`, `idx_notificaciones_reserva`,
`idx_notificaciones_pendientes`, `idx_clientes_telefono` + unique indexes
✔

## 6. Test data status

| Table | Rows at verification (2026-11-01, read-only) |
|-------|------|
| all eight tables | **0** |

At the time of this report the tables were empty. The idempotent script at
`database/test_data.sql` (INSERT-only, FK-ordered, duplicate-safe, relies on
triggers for `codigo_reserva`/history/notifications) was **subsequently
executed on 2026-11-01 with explicit team approval** — 22 rows total
(1 administrador, 3 clientes, 4 mesas, 5 platillos, 2 reservas,
3 reserva_platillos, 2 historial_estados, 2 notificaciones). Counts were
0 for every table beforehand, so all rows are newly inserted. Current
counts and execution evidence: [test-results.md](test-results.md) §5.

## 7. Actions taken

- No `DROP`/`TRUNCATE`/`ALTER`/migration executed (at any point).
- No rows inserted, updated or deleted — except the team-authorized
  `database/test_data.sql` execution of 2026-11-01 (INSERT-only, 22 rows).
- Verification script is re-runnable at any time:
  `psql "$DATABASE_URL" -f database/schema_verification.sql`
