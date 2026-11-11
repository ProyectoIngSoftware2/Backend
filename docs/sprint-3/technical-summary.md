# Technical Implementation Summary — Sprint 3

## Backend changes

### New files
- `database/sprint3_core_tables.sql` — Migration SQL for `roles`, `horarios`, `bloqueos_horario` tables (BIGINT identifiers, idempotent).
- `services/clientes/app/schemas_usuarios.py` — Pydantic schemas for usuarios y roles API.
- `services/catalogo/app/schemas_horarios.py` — Pydantic schemas for horarios y bloqueos API.
- `services/reservas/app/schemas_platillos.py` — Pydantic schemas for reservation dish details API.
- `tests/test_sprint3.py` — 43 automated tests for Sprint 3 APIs (usuarios, roles, horarios, bloqueos, reserva platillos).

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
- `gateway/app/main.py` — Added custom OpenAPI schema with BearerAuth security scheme, security declarations on protected operations, request body declarations for write operations, service-based tagging. Added proxy routes for `/api/v1/usuarios` and `/api/v1/roles`.

### Database migrations
Prepared in `database/sprint3_core_tables.sql`. Creates `roles`, `horarios`, `bloqueos_horario` tables with BIGINT identifiers matching live database convention. Idempotent guards (CREATE TABLE IF NOT EXISTS, ON CONFLICT DO NOTHING). **Not yet applied to the live NeonDB** — must be applied before the new APIs can be used.

### Test results
- Backend test suite: **230 passed, 17 skipped** (187 pre-existing + 43 new Sprint 3 tests).
- `pip check`: No broken requirements.

## Design decisions recorded

- Design v1.0 specifies UUID primary keys; live database uses BIGINT. New tables use BIGINT to match live convention.
- Design v1.0 defines 3 roles (cliente, recepción, administrador); live implementation has 2 (cliente, administrador). No `recepción` role added without an approved requirement.
- Design v1.0 reservation states: SOLICITADA, CONFIRMADA, RECHAZADA, CANCELADA, COMPLETADA, NO_ASISTIDO; live implementation: pendiente, aprobada, confirmada, rechazada, cancelada, completada.

## API counting

- **Before Sprint 3:** 4 business CRUD resources (clientes, reservas, mesas, platillos) + 1 auth operation (login).
- **After Sprint 3:** 7 business CRUD resources (4 existing + 3 new: usuarios y roles, horarios y bloqueos, detalle platillos de reserva) + 1 auth operation.
- Note: lineamientos specifies "4 APIs acumuladas" for Sprint 3 and "5 APIs acumuladas" for Sprint 4. Two counting ambiguities require instructor confirmation:
  1. Whether the 4 existing CRUD resources count toward the cumulative total.
  2. Whether "usuarios y roles" counts as one API resource or two (usuarios + roles).

## Frontend integration

The frontend (React/Vite) is developed in the `ProyectoIngSoftware2/Frontend` repository by Marina Valladares and Sebastián Rivera. No frontend changes are part of this backend PR. The backend contract is documented in `api-inventory.md` and the gateway OpenAPI at `/docs`. CORS configuration (`CORS_ORIGINS`) requires the frontend development origin to be confirmed by the frontend team before browser integration can work.
