# Technical Implementation Summary — Sprint 3

## Backend changes

### New files
- `database/sprint3_core_tables.sql` — Migration SQL for `roles`, `horarios`, `bloqueos_horario` tables (BIGINT identifiers, idempotent).
- `services/clientes/app/schemas_usuarios.py` — Pydantic schemas for usuarios y roles API.
- `services/catalogo/app/schemas_horarios.py` — Pydantic schemas for horarios y bloqueos API.
- `services/reservas/app/schemas_platillos.py` — Pydantic schemas for reservation dish details API.

### Modified files
- `services/clientes/app/main.py` — Added usuarios y roles CRUD endpoints:
  - `GET/POST /api/v1/usuarios`
  - `GET/PUT/PATCH/DELETE /api/v1/usuarios/{id_usuario}`
  - `GET/POST /api/v1/roles`
  - `GET/PUT/PATCH /api/v1/roles/{id_rol}`
  - All administrator-only. Passwords hashed with bcrypt. Duplicate email → 409. Self-deactivation → 403.
- `services/catalogo/app/main.py` — Added horarios y bloqueos CRUD endpoints:
  - `GET/POST /api/v1/catalogo/horarios`
  - `GET/PUT/PATCH/DELETE /api/v1/catalogo/horarios/{id}`
  - `GET/POST /api/v1/catalogo/bloqueos`
  - `GET/PUT/PATCH/DELETE /api/v1/catalogo/bloqueos/{id}`
  - Reads public; writes administrator-only. Validation: hora_cierre > hora_apertura, intervalo > 0, bloqueo fin > inicio.
- `services/reservas/app/main.py` — Added reservation dish details CRUD endpoints:
  - `GET/POST /api/v1/reservas/{codigo}/platillos`
  - `GET/PUT/PATCH/DELETE /api/v1/reservas/{codigo}/platillos/{detalle_id}`
  - Owner or administrator access. Prices sourced from catalogo service (never from client). Duplicate dish → 409. Non-modifiable reservation state → 400.
- `gateway/app/main.py` — Added custom OpenAPI schema with BearerAuth security scheme, security declarations on protected operations, request body declarations for write operations, and service-based tagging.

### Database migrations
Prepared in `database/sprint3_core_tables.sql`. Creates `roles`, `horarios`, `bloqueos_horario` tables with BIGINT identifiers matching live database convention. Idempotent guards (CREATE TABLE IF NOT EXISTS, ON CONFLICT DO NOTHING). **Not yet applied to the live NeonDB** — must be applied before the new APIs can be used.

### Test results
- Backend test suite: 187 passed, 17 skipped (pre-existing baseline).
- No new tests added for Sprint 3 endpoints yet (pending).

## Frontend changes

### New files
- `style.css` — Common styles for all screens (consistent with Punto y Sal palette).
- `usuarios.html` + `usuarios.js` — User management screen (administrador).
- `horarios.html` + `horarios.js` — Schedule and blocked-period management screen (administrador).
- `reservar.html` + `reservar.js` — Client reservation screen with dish details (cliente).

### Modified files
- `login.js` — Fixed `datos.role` → `datos.rol` (backend returns `rol`). Fixed redirects from nonexistent `admin.html`/`cliente.html` to existing `usuarios.html`/`reservar.html`.

### CORS
- `.env.example` updated with documented CORS_ORIGINS format. Actual origin must be confirmed and set in `.env` (gitignored, not committed).

## Design deviations recorded
- Design v1.0 specifies UUID primary keys; live database uses BIGINT. New tables use BIGINT to match live convention.
- Design v1.0 defines 3 roles (cliente, recepción, administrador); live implementation has 2 (cliente, administrador). No `recepción` role added.
- Design v1.0 reservation states: SOLICITADA, CONFIRMADA, etc.; live implementation: pendiente, aprobada, confirmada, etc.

## API counting
- 4 existing CRUD resources (clientes, reservas, mesas, platillos) — implemented in Sprint 2 (ahead of schedule).
- 1 auth operation (login) — not a business CRUD resource.
- 3 required resources missing before Sprint 3: usuarios y roles, horarios y bloqueos, detalle de platillos de reserva.
- After Sprint 3: 6 business CRUD resources (4 existing + horarios y bloqueos + detalle platillos).
- Counting ambiguity with lineamientos' "4 APIs acumuladas" target requires instructor confirmation.
