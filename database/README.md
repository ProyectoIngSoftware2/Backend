# Database Scripts

This directory contains SQL scripts for the existing NeonDB PostgreSQL
database used by Punto y Sal.

## Important safety rules

- The database already exists and its schema was **verified on 2026-11-01**
  (see [database verification report](../sprint-1/database-verification.md)).
  **Do not re-run any CREATE TABLE / CREATE FUNCTION script against it.**
- All scripts here are **read-only or additive only**: there is no DROP,
  TRUNCATE, ALTER or destructive migration anywhere in this directory.
- The test-data script was **executed on 2026-11-01 with explicit team
  approval** (22 rows inserted; an immediate re-run inserted 0, confirming
  it is safe to re-run). No other write has ever been executed.

## Files

| File                       | Purpose                                                                 | Executed? |
|----------------------------|-------------------------------------------------------------------------|-----------|
| `schema_verification.sql`  | Read-only SELECT queries that re-verify the eight tables, keys, constraints, function and triggers. Safe to run at any time. | Yes (2026-11-01, results in the verification report) |
| `test_data.sql`            | Idempotent INSERT script that seeds test customers, tables, dishes and reservations. Respects foreign keys and avoids duplicates. | **Yes — 2026-11-01, team-authorized** (re-run verified idempotent) |

## How to run (with approval)

Using the `psql` CLI with the connection string kept in an environment
variable (never paste the real string into documents or chat):

```bash
# Read-only verification (safe):
psql "$DATABASE_URL" -f database/schema_verification.sql

# Test data (ONLY with explicit team approval):
psql "$DATABASE_URL" -f database/test_data.sql
```

## Notes on automatic behaviors

The live schema contains triggers that the test-data script relies on:

- `reservas.codigo_reserva` is generated automatically by
  `generar_codigo_reserva()`.
- `reservas.fecha_actualizacion` is maintained by
  `trg_reservas_fecha_actualizacion`.
- Status history rows are inserted automatically by
  `trg_reservas_historial_insert` / `trg_reservas_historial_update`.
- Notifications are inserted automatically by
  `trg_reservas_notificacion_insert` / `trg_reservas_notificacion_update`.
- Table assignment and status transitions are validated by
  `trg_reservas_validar_mesa` / `trg_reservas_validar_estado`.

Therefore the test-data script does **not** insert `historial_estados` or
`notificaciones` rows manually — the triggers create them.
