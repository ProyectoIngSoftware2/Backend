# Database Verification (Sprint 2 — auth schema and seed)

- **Date executed:** 2026-11-03 (team-executed against the configured
  NeonDB connection; confirmation provided for this record)
- **Scripts executed (exactly these two, nothing else):**
  1. `database/sprint2_auth_schema.sql` — schema (Option B)
  2. `database/sprint2_auth_seed.sql` — idempotent test-admin seed
- **Method:** scripts reviewed before execution; both are idempotent by
  construction and were run once, in order, on the same connection the
  services use
- **Credentials:** never displayed; connection read from the local `.env`
- **Sprint 1 baseline:** the eight approved tables were verified
  read-only on 2026-11-01 ([Sprint 1 report](../sprint-1/database-verification.md))
  and are structurally untouched by Sprint 2

## 1. New table: `public.usuarios`

Created by `sprint2_auth_schema.sql` (`CREATE TABLE IF NOT EXISTS`):

| Column | Type | Null | Default / constraint |
|--------|------|------|----------------------|
| `id_usuario` | `bigint` (identity) | NO | **primary key** |
| `correo` | `varchar(255)` | NO | **UNIQUE** (`usuarios_correo_key`) — login key |
| `password_hash` | `varchar(255)` | NO | bcrypt hash (cost 12, `$2b$12$…`) |
| `rol` | `varchar(20)` | NO | **CHECK** `IN ('administrador','cliente')` |
| `activo` | `boolean` | NO | default `true` |
| `fecha_creacion` | `timestamptz` | NO | default `now()` |

Result: **`usuarios` exists** — the database now holds **9 tables**
(the 8 approved Sprint 1 tables + `usuarios`).

## 2. 1:1 links to the profile tables

| Table | Added column | Constraint | Nullable |
|-------|--------------|------------|----------|
| `administradores` | `id_usuario bigint` | `UNIQUE` + **FK → `usuarios(id_usuario)`** | yes |
| `clientes` | `id_usuario bigint` | `UNIQUE` + **FK → `usuarios(id_usuario)`** | yes |

- Direction is **profile → `usuarios`** (no circular FK: `usuarios`
  references nothing).
- `UNIQUE` enforces the **1:1** cardinality (one login per profile, at
  most one profile per login).
- Both statements use `ADD COLUMN IF NOT EXISTS` → re-running the
  script changes nothing.

## 3. Test-admin seed (idempotent)

Executed from `database/sprint2_auth_seed.sql`:

| Step | Statement guard | Effect (2026-11-03) |
|------|-----------------|----------------------|
| 1. Insert `usuarios` row for `admin.prueba@puntoysal.test` (`rol = 'administrador'`, `activo = true`) | `WHERE NOT EXISTS (… correo …)` | 1 row created |
| 2. Repair a non-bcrypt placeholder in `usuarios.password_hash` if present | `password_hash NOT LIKE '$2%'` | no-op once the real hash is stored |
| 3. Replace the Sprint 1 placeholder in legacy `administradores.password_hash` with the same bcrypt hash | `= 'PLACEHOLDER_SPRINT2_WILL_HASH_THIS'` | legacy column now stores a bcrypt cost-12 hash |
| 4. Link `administradores.id_usuario` → the `usuarios` row | `a.id_usuario IS NULL` | 1:1 link established |

- The stored hash is a **real bcrypt hash at cost 12** generated with
  the repository's `bcrypt` library (`$2b$12$…` prefix). The plaintext
  test password is documented **only** in the header comment of
  `database/sprint2_auth_seed.sql` — it is a test credential, never
  reproduced in this documentation folder.
- Idempotency: every step is a guarded no-op on re-run (`WHERE NOT
  EXISTS` / `NOT LIKE '$2%'` / `IS NULL`); no `ON CONFLICT`, no
  `DROP`/`TRUNCATE`/`DELETE`.

## 4. Post-execution state

| Object | State after execution (2026-11-03) |
|--------|------------------------------------|
| `public.usuarios` | exists; **1 row** (test administrator) |
| `administradores.id_usuario` | column present; test admin **linked 1:1** |
| `clientes.id_usuario` | column present; **0 links** (customers have no login accounts yet — expected) |
| `administradores.password_hash` (legacy) | placeholder replaced with bcrypt hash |
| Sprint 1 data | untouched: administradores 1, clientes 3, mesas 4, platillos 5, reservas 2, reserva_platillos 3, historial_estados 2, notificaciones 2 |
| Triggers / function / indexes | untouched (`generar_codigo_reserva()`, 8 triggers, indexes intact) |

## 5. Safety properties

- **Exactly two scripts** were executed for Sprint 2 — both reviewed,
  both idempotent, both team-approved. No other DDL/DML was run.
- No destructive statements anywhere in the scripts: no `DROP`,
  `TRUNCATE`, `DELETE`, `GRANT` or `REVOKE`; the only data change is the
  guarded seed of one test account (plus the placeholder replacement).
- The verification script from Sprint 1
  (`database/schema_verification.sql`) remains fully read-only and now
  also lists `usuarios` in its table/column probes if extended — it was
  not modified.

## 6. Read-only re-verification (any time)

```bash
# Schema (read-only, safe to re-run):
psql "$DATABASE_URL" -f database/schema_verification.sql

# Focused checks for the Sprint 2 objects:
#   SELECT table_name FROM information_schema.tables
#    WHERE table_schema='public' AND table_name='usuarios';
#   SELECT column_name, is_nullable FROM information_schema.columns
#    WHERE table_name='usuarios' ORDER BY ordinal_position;
#   SELECT tc.constraint_type, kcu.column_name
#    FROM information_schema.table_constraints tc
#    JOIN information_schema.key_column_usage kcu USING (constraint_name)
#    WHERE tc.table_name IN ('administradores','clientes')
#      AND kcu.column_name='id_usuario';
#   SELECT rol, activo, (password_hash LIKE '$2%') AS has_bcrypt
#    FROM usuarios;
```

Expected: `usuarios` present with the six columns of §1; both profile
tables expose a unique `id_usuario` FK; the single usuario row shows
`rol='administrador'`, `activo=true`, `has_bcrypt=true`.
