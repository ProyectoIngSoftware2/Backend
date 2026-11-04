# Backend - ReservasPyS

Backend for **Punto y Sal**, a restaurant reservation and table management
system. Built with FastAPI and PostgreSQL (hosted on NeonDB).

> **Status: Sprint 1 implemented, verified and integrated (accepted by the
> team on 2026-11-03). Sprint 2 security layer (Option B) implemented and
> verified on 2026-11-03** — unified `usuarios` table + 1:1 links (scripts
> executed on NeonDB), bcrypt (cost 12), JWT via PyJWT, new auth
> microservice (:8004) and `POST /api/v1/auth/login` through the gateway;
> **73 tests passing**, Docker Compose **5/5 containers healthy**. Sprint 2
> changes are on `Dev/David-Avila`, ready for PR into `development` — see
> [Sprint 2 documentation](docs/sprint-2/README.md) and
> [Sprint 1 documentation](docs/sprint-1/README.md).

## Architecture

```
Frontend ──► API Gateway :8000 ──HTTP──► clientes  :8001  (table: clientes)
                    │       └──HTTP──► reservas  :8002  (tables: reservas,
                    │       │                                reserva_platillos,
                    │       │                                historial_estados,
                    │       │                                notificaciones)
                    │       └──HTTP──► catalogo  :8003  (tables: mesas,
                    │       │                                platillos)
                    │       └──HTTP──► auth      :8004  (table: usuarios)
                    │                                login → signed JWT
                    │
                    └── uses shared/ (config + DB connection + security)
                                  │
                                  ▼
                        NeonDB PostgreSQL (external, port 5432)
```

| Component  | Responsibility                                                            |
|------------|---------------------------------------------------------------------------|
| `gateway/` | Single public entry point; HTTP routing to the three microservices + `POST /api/v1/auth/login` → auth |
| `services/clientes` | Customer management (`clientes`)                                 |
| `services/reservas` | Reservations, dishes, status history, notifications              |
| `services/catalogo` | Restaurant tables and menu items (`mesas`, `platillos`)           |
| `services/auth` | **Sprint 2:** authentication (`usuarios` table); validates credentials and issues JWTs |
| `shared/`  | Reusable configuration and database connection (`psycopg` 3) + **`security.py`** (bcrypt, JWT, RBAC dependency) |
| `app/`     | Original root FastAPI app — **preserved for compatibility** (see below)  |
| `database/`| Read-only verification script + idempotent test-data script (executed 2026-11-01) + **Sprint 2 auth schema/seed scripts (executed 2026-11-03)** |
| `docs/`    | Sprint documentation                                                       |

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
| **Auth**   | **8004** | http://localhost:8004     | /docs              |
| Root `app/`| 8010 | http://localhost:8010         | /docs              |

Health checks: `GET /health` on every component, plus
`GET http://localhost:8000/health/services` on the gateway to see the three
microservices' status in one call.

## API Gateway routing map (v1)

| Gateway route                       | Forwards to                          | Method            |
|-------------------------------------|--------------------------------------|--------------------|
| `/api/v1/clientes`                  | `clientes` service, same path        | GET                |
| `/api/v1/clientes/{id}`             | `clientes` service                   | GET                |
| `/api/v1/reservas`                  | `reservas` service, same path        | GET                |
| `/api/v1/reservas/{codigo_reserva}` | `reservas` service                   | GET                |
| `/api/v1/catalogo/mesas`            | `catalogo` service                   | GET                |
| `/api/v1/catalogo/mesas/{id}`       | `catalogo` service                   | GET                |
| `/api/v1/catalogo/platillos`        | `catalogo` service                   | GET                |
| `/api/v1/catalogo/platillos/{id}`   | `catalogo` service                   | GET                |
| **`/api/v1/auth/login`**            | **`auth` service (Sprint 2)**        | **POST**           |
| `/health`                           | gateway's own health                 | GET                |
| `/health/services`                  | aggregated health of the 3 services  | GET                |

Business endpoints are read-only by design; mutation methods for
clientes/reservas/catalogo will be enabled when the corresponding
endpoints exist in later sprints. The one exception is **Sprint 2's
`POST /api/v1/auth/login`**, which the gateway proxies to the auth
service (the `Authorization` header is forwarded untouched — the gateway
never parses tokens). Unavailable services return a controlled JSON
`503` (`{"detail": ..., "service": ...}`); timeouts return `504`.
Internal URLs are never exposed.

## Environment setup

1. Python 3.15 with a virtual environment (`.venv/`):
   `python -m venv .venv && .venv\Scripts\activate && pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and set `DATABASE_URL` with the NeonDB
   connection string. **Never commit `.env`** (it is gitignored).
3. **Sprint 2:** set `JWT_SECRET` in `.env` as well (Docker Compose
   fails fast without it); `JWT_ALGORITHM` (HS256) and
   `JWT_EXPIRATION_MINUTES` (60) have working defaults. Without any
   configuration the security module falls back to an insecure dev
   secret **with a logged warning** — fine for unit tests, never for
   deployment.
4. Optional local gateway/auth URLs are already defaulted in code; the
   placeholders in `.env.example` document them.

## Running locally

```bash
# Original root app (kept for compatibility):
uvicorn app.main:app --port 8010

# Each microservice independently (from the repository root):
uvicorn app.main:app --app-dir services/clientes --port 8001
uvicorn app.main:app --app-dir services/reservas --port 8002
uvicorn app.main:app --app-dir services/catalogo --port 8003
uvicorn app.main:app --app-dir services/auth    --port 8004   # Sprint 2

# Gateway (routes to localhost:8001-8004 by default):
uvicorn gateway.app.main:app --port 8000
```

## Running with Docker Compose

Requires Docker Desktop with the Compose plugin and a local `.env`
containing `DATABASE_URL` **and `JWT_SECRET`** (the database stays
external on NeonDB — there is no local PostgreSQL container; Compose
fails fast if either variable is missing).

```bash
docker compose up --build
# Gateway: http://localhost:8000/docs   (5 services: + auth on :8004)
docker compose down
```

> **Verified 2026-11-01 (Sprint 1):** `docker compose config --quiet`
> passed, all images were built and all four containers started
> **healthy**. Health, aggregated health, read-only routing, Swagger and
> the controlled-failure path (stopping `catalogo` → gateway 503/
> degraded → restart → recovery) were exercised successfully — details
> in [test-results.md](docs/sprint-1/test-results.md) §4. One
> environment note: on this machine the Docker CLI must be invoked with
> Docker's `resources/bin` on `PATH` (otherwise the
> `docker-credential-desktop` helper cannot be found when pulling base
> images); this is a host configuration detail, not a repository issue.
>
> **Re-verified 2026-11-03 (Sprint 2):** config validation passed and
> the stack grew to **5/5 containers healthy** (gateway, clientes,
> reservas, catalogo, **auth**) — see
> [docs/sprint-2/test-results.md](docs/sprint-2/test-results.md) §3.

## Database

Nine tables exist in NeonDB. The original eight were verified read-only
on 2026-11-01: `clientes`, `administradores`, `mesas`, `platillos`,
`reservas`, `reserva_platillos`, `historial_estados`, `notificaciones` —
including primary/foreign/unique/check constraints, indexes, the
`generar_codigo_reserva()` function and 8 business-logic triggers (all
tables were empty at that time). Full report:
[docs/sprint-1/database-verification.md](docs/sprint-1/database-verification.md).

**Sprint 2 (executed 2026-11-03, team-approved):** the auth scripts
added the ninth table — `usuarios` (unified login accounts with
`rol CHECK ('administrador','cliente')`) — plus 1:1 `id_usuario` foreign
keys on `administradores` and `clientes`, and seeded the test admin
with a bcrypt cost-12 hash (replacing the Sprint 1 placeholder). Both
scripts are idempotent. Report:
[docs/sprint-2/database-verification.md](docs/sprint-2/database-verification.md).

Safety rules: `database/schema_verification.sql` is read-only;
`database/test_data.sql` seeds idempotent test data and was
**executed on 2026-11-01 with explicit team approval** (22 rows; an
immediate re-run inserted 0 rows, confirming idempotency); the Sprint 2
scripts (`sprint2_auth_schema.sql`, `sprint2_auth_seed.sql`) were
**executed on 2026-11-03 with explicit team approval** and change only
the auth objects described above.

## Testing

```bash
# Unit tests (no network, no database):
.venv\Scripts\python -m pytest -q

# Live integration tests (read-only SELECT 1 against NeonDB):
RUN_DB_TESTS=1 .venv\Scripts\python -m pytest -q -m integration
```

Last run (2026-11-03): **73 passed, 6 skipped** — the 60-test Sprint 1
baseline plus 13 new auth/gateway tests (`tests/test_security.py`
brings the total security coverage to 21 tests; see
[docs/sprint-2/test-results.md](docs/sprint-2/test-results.md)). The
opt-in live integration run (6 read-only tests) is documented in
[docs/sprint-1/test-results.md](docs/sprint-1/test-results.md).

## Known limitations and pending tasks

- **Frontend** (confirmed for Sprint 2: Marina, Sebastián) — still
  pending planning; the Sprint 2 backend security layer (authentication
  with JWT/roles) is **delivered and verified** (2026-11-03), see
  [docs/sprint-2](docs/sprint-2/README.md).
- RBAC is prepared but not yet enforced: `shared/security.py` ships
  `require_role(...)`, yet the three business services still expose
  only read-only GET endpoints with no protected routes (enforcement
  lands with the mutation endpoints).
- Business endpoints are read-only; no CRUD mutations yet (later
  sprints). The single exception is `POST /api/v1/auth/login`.
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

- **Sprint 2 deliverables (security layer):**
  [docs/sprint-2/](docs/sprint-2/README.md) — goal, architecture,
  database verification, test results, closure.
- Sprint 1 deliverables: [docs/sprint-1/](docs/sprint-1/README.md).
- Project management (team, agreements, communication):
  [docs/gestion-del-proyecto/](docs/gestion-del-proyecto/equipo-scrum.md).
