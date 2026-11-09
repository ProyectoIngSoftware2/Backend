# Backend - ReservasPyS

Backend for **Punto y Sal**, a restaurant reservation and table management
system. Built with FastAPI and PostgreSQL (hosted on NeonDB).

> **Status: Sprint 1 implemented, verified and integrated (accepted by the
> team on 2026-11-03); Sprint 2 (authentication, authorization and CRUD)
> implemented on this branch.** Sprint 1 delivered via commit `1c6e0f3`
> and **PR #1 merged into `development` on 2026-11-03**. Sprint 2 adds
> JWT login (PyJWT + bcrypt), role-based access control for the two
> existing roles (`administrador`, `cliente`), client data isolation
> (IDOR-proof ownership in SQL), CRUD for clientes/reservas/catalogo and
> full gateway method support — verified with **125 unit tests + 17
> live integration tests** and a Docker Compose smoke test (4/4
> containers healthy; login/401/403/200 matrix passing). See
> [docs/api-integration.md](docs/api-integration.md) for the frontend
> integration guide and [Known limitations](#known-limitations-and-pending-tasks).

## Architecture

```
Frontend ──► API Gateway :8000 ──HTTP──► clientes  :8001  (tables: clientes,
                    │       │                                usuarios)
                    │       └──HTTP──► reservas  :8002  (tables: reservas,
                    │       │                                reserva_platillos,
                    │       │                                historial_estados,
                    │       │                                notificaciones)
                    │       └──HTTP──► catalogo  :8003  (tables: mesas,
                    │                                     platillos)
                    └── uses shared/ (config + DB connection + JWT auth)
                                  │
                                  ▼
                        NeonDB PostgreSQL (external, port 5432)
```

| Component  | Responsibility                                                            |
|------------|---------------------------------------------------------------------------|
| `gateway/` | Single public entry point; HTTP routing to the three microservices (all methods) |
| `services/clientes` | Customer management (`clientes`) + `usuarios` accounts and `POST /api/v1/auth/login` |
| `services/reservas` | Reservations, dishes, status history, notifications              |
| `services/catalogo` | Restaurant tables and menu items (`mesas`, `platillos`)           |
| `shared/`  | Reusable configuration, database connection (`psycopg` 3) and **JWT/bcrypt auth layer** (`shared/auth.py`) |
| `app/`     | Original root FastAPI app — **preserved for compatibility** (see below)  |
| `database/`| Read-only verification script + idempotent test-data script (executed 2026-11-01) |
| `docs/`    | Sprint documentation + [frontend API integration guide](docs/api-integration.md) |

Each microservice is an independent FastAPI application with its own entry
point, OpenAPI documentation and `/health` endpoint. Services never import
each other's code and only touch their own tables; the gateway proxies over
real HTTP — it does not import service routers. Per the **approved F-01
decision (2026-11-01)**, the reservations service
resolves dish names by calling the catalogo microservice over HTTP
(`GET /api/v1/catalogo/platillos/{id}`) instead of reading the `platillos`
table directly — see the [design change log](docs/sprint-1/design-change-log.md).

> **Root `app/` note (decision 2026-11-01):** the original application is
> **preserved unchanged** as the legacy/compatibility entry point and stays
> tested. The three services under `services/` are the **official Sprint 1
> microservices**; Docker Compose and the Gateway route traffic only to
> them. No business logic was migrated, duplicated or refactored.

## Ports and URLs

| Component  | Port | Local URL                     | Swagger            |
|------------|------|-------------------------------|--------------------|
| Gateway    | 8000 | http://localhost:8000         | /docs              |
| Clientes   | 8001 | http://localhost:8001         | /docs              |
| Reservas   | 8002 | http://localhost:8002         | /docs              |
| Catalogo   | 8003 | http://localhost:8003         | /docs              |
| Root `app/`| 8010 | http://localhost:8010         | /docs              |

Health checks: `GET /health` on every component, plus
`GET http://localhost:8000/health/services` on the gateway to see the three
microservices' status in one call.

## API Gateway routing map (v1)

| Gateway route                       | Forwards to                          | Methods (Sprint 2)     | Access                |
|-------------------------------------|--------------------------------------|------------------------|-----------------------|
| `/api/v1/auth`, `/api/v1/auth/{…}`  | `clientes` service, same path        | POST                   | public (login)        |
| `/api/v1/clientes`                  | `clientes` service, same path        | GET/POST/PUT/PATCH/DELETE | GET/DELETE: admin · POST: public |
| `/api/v1/clientes/{id}`             | `clientes` service                   | GET/PUT/PATCH/DELETE   | GET/PUT/PATCH: admin or owner · DELETE: admin |
| `/api/v1/reservas`                  | `reservas` service, same path        | GET/POST/PUT/PATCH/DELETE | GET: admin · POST: authenticated |
| `/api/v1/reservas/{codigo_reserva}` | `reservas` service                   | GET/PUT/PATCH/DELETE    | admin or owner (clients: cancellation only) |
| `/api/v1/catalogo/mesas[/{id}]`     | `catalogo` service                   | GET/POST/PUT/PATCH/DELETE | GET: public · writes: admin |
| `/api/v1/catalogo/platillos[/{id}]` | `catalogo` service                   | GET/POST/PUT/PATCH/DELETE | GET: public · writes: admin |
| `/health`                           | gateway's own health                 | GET                    | public                |
| `/health/services`                  | aggregated health of the 3 services  | GET                    | public                |

The gateway only forwards requests (including the `Authorization`
header) and performs **no authentication** of its own: every protected
microservice validates the JWT and its roles independently, so routing
through the gateway can never bypass authorization. Unavailable
services return a controlled JSON `503` (`{"detail": ..., "service":
...}`); timeouts return `504`. Internal URLs are never exposed. Full
endpoint contracts (bodies, responses, errors, examples):
**[docs/api-integration.md](docs/api-integration.md)**.

## Environment setup

1. Python 3.15 with a virtual environment (`.venv/`):
   `python -m venv .venv && .venv\Scripts\activate && pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and set `DATABASE_URL` with the NeonDB
   connection string. **Never commit `.env`** (it is gitignored).
3. **`JWT_SECRET` (required):** the signing secret for access tokens.
   Generate a long random value and provide it via environment (shell or
   `.env` — never in source):
   `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
   Services fail closed (no default secret) when it is missing or < 32
   characters. Optional: `JWT_EXPIRE_MINUTES` (default `60`) and
   `CORS_ORIGINS` (comma-separated frontend origins for the gateway;
   empty = no CORS allowed).
4. Optional local gateway URLs are already defaulted in code; the placeholders
   in `.env.example` document them.

## Running locally

```bash
# Original root app (kept for compatibility):
uvicorn app.main:app --port 8010

# Each microservice independently (from the repository root):
uvicorn app.main:app --app-dir services/clientes --port 8001
uvicorn app.main:app --app-dir services/reservas --port 8002
uvicorn app.main:app --app-dir services/catalogo --port 8003

# Gateway (routes to localhost:8001-8003 by default):
uvicorn gateway.app.main:app --port 8000
```

## Running with Docker Compose

Requires Docker Desktop with the Compose plugin and a local `.env`
containing `DATABASE_URL` plus a `JWT_SECRET` for the auth layer (the
database stays external on NeonDB — there is no local PostgreSQL
container). Compose refuses to start when either variable is missing
(`:?` interpolation), so a forgotten secret can never silently fall back
to a default.

```bash
# JWT_SECRET must be visible to Compose (shell export or .env):
export JWT_SECRET="<long-random-value>"   # see .env.example
docker compose up --build
# Gateway: http://localhost:8000/docs
docker compose down                        # needs the same JWT_SECRET exported
```

> **Sprint 2 verified (local):** `docker compose config --quiet`
> passed; all images built; 4/4 containers healthy; and an end-to-end
> smoke test through the gateway returned: health `200`, aggregated
> health `ok/ok/ok`, admin login `200` + token, client login `200` +
> token, wrong password `401`, protected list without token `401` +
> `WWW-Authenticate: Bearer`, client token on admin list `403`, admin
> token `200`, catalog reads `200` without token, catalog write without
> token `401` and with client token `403`, reservation list with admin
> `200`, garbage token `401`. Sprint 1 verification (2026-11-01):
> [test-results.md](docs/sprint-1/test-results.md) §4.

## Database

Eight tables exist in NeonDB and were verified read-only on 2026-11-01:
`clientes`, `administradores`, `mesas`, `platillos`, `reservas`,
`reserva_platillos`, `historial_estados`, `notificaciones` — including
primary/foreign/unique/check constraints, indexes, the
`generar_codigo_reserva()` function and 8 business-logic triggers. All tables
were empty (0 rows). Full report: [docs/sprint-1/database-verification.md](docs/sprint-1/database-verification.md).

Safety rules: no schema changes are executed; `database/schema_verification.sql`
is read-only; `database/test_data.sql` seeds idempotent test data and was
**executed on 2026-11-01 with explicit team approval** (22 rows; an
immediate re-run inserted 0 rows, confirming idempotency).

## Testing

```bash
# Unit tests (no network, no database, no writes):
.venv\Scripts\python -m pytest -q

# Live integration tests (read-only against NeonDB: /health SELECT 1,
# logins via bcrypt and SELECT-only list endpoints). The test-account
# credentials are read from the environment ONLY (never stored in Git):
TEST_ADMIN_CORREO=... TEST_ADMIN_PASSWORD=... \
TEST_CLIENT_CORREO=... TEST_CLIENT_PASSWORD=... \
RUN_DB_TESTS=1 .venv\Scripts\python -m pytest -q -m integration
```

Last run (Sprint 2): **125 passed, 17 skipped** (unit — the 17 skips
are the opt-in integration tests) and **17 passed** (live integration,
opt-in, read-only). The suite covers authentication (login success/
failure, missing/invalid/expired/forged/wrong-algorithm tokens,
unknown-role tokens), RBAC (401 vs 403 vs 404 per role), ownership
isolation (no IDOR on profiles or reservations), mass-assignment
rejection, CRUD contracts with parameterization/logical-delete
assertions, trigger-error mapping (400), gateway routing (all methods,
auth forwarding, no-bypass) and regression of the Sprint 1 endpoints.

## Known limitations and pending tasks

- **Frontend** remains the Sprint 2 team commitment (Marina Valladares,
  Sebastián Rivera); this backend deliverable gives it the complete
  [API integration guide](docs/api-integration.md).
- **No client "my reservations" list endpoint:** the specification has
  no `GET /api/v1/reservas?cliente=` listing; clients fetch their
  reservations by `codigo_reserva` (detail is owner-scoped). Adding a
  filtered list would be a team decision, not an assumption.
- **Roles:** the database CHECK (`usuarios_rol_check`) allows exactly
  `administrador` and `cliente`. A `recepción` role does **not** exist
  anywhere (schema, code, docs or git history) — nothing was removed;
  introducing it would require an approved schema change.
- **Refresh tokens:** none (not justified by requirements); re-login
  after `expires_in`.
- **Branch naming:** the official course guideline specifies `develop`;
  the team authorized the existing **`development`** branch as its
  integration branch (2026-11-01). No branches were renamed or created.

## Git workflow

- `main`: stable branch · **`development`: team integration branch
  (authorized 2026-11-01; the official guideline's name is `develop`, the
  team keeps `development` as-is)** ·
  `Dev/Noe-Mejia`, `Dev/David-Avila`: personal branches.
- Changes reach `development`/`main` through pull requests only.
- Sprint 1 followed this flow: commit `1c6e0f3` pushed to
  `Dev/Noe-Mejia` (2026-11-02) and **PR #1 merged into `development`
  (2026-11-03)** — evidence:
  [docs/sprint-1/github-evidence.md](docs/sprint-1/github-evidence.md).

## Documentation

- Sprint 1 deliverables: [docs/sprint-1/](docs/sprint-1/README.md).
- Project management (team, agreements, communication):
  [docs/gestion-del-proyecto/](docs/gestion-del-proyecto/equipo-scrum.md).
