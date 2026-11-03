# Backend - ReservasPyS

Backend for **Punto y Sal**, a restaurant reservation and table management
system. Built with FastAPI and PostgreSQL (hosted on NeonDB).

> **Status: Sprint 1 implemented, verified and integrated (accepted by the
> team on 2026-11-03).** Locally verified on 2026-11-01 (39 unit tests +
> 6 live integration tests; Docker Compose 4/4 containers healthy; health,
> routing, Swagger and controlled-failure checks passing) and re-verified
> on 2026-11-03. Delivered via commit `1c6e0f3` (pushed 2026-11-02) and
> **PR #1 merged into `development` on 2026-11-03** — see
> [Sprint 1 documentation](docs/sprint-1/README.md) and
> [Known limitations](#known-limitations-and-pending-tasks).

## Architecture

```
Frontend ──► API Gateway :8000 ──HTTP──► clientes  :8001  (table: clientes)
                    │       └──HTTP──► reservas  :8002  (tables: reservas,
                    │       │                                reserva_platillos,
                    │       │                                historial_estados,
                    │       │                                notificaciones)
                    │       └──HTTP──► catalogo  :8003  (tables: mesas,
                    │                                     platillos)
                    │
                    └── uses shared/ (config + DB connection)
                                  │
                                  ▼
                        NeonDB PostgreSQL (external, port 5432)
```

| Component  | Responsibility                                                            |
|------------|---------------------------------------------------------------------------|
| `gateway/` | Single public entry point; HTTP routing to the three microservices        |
| `services/clientes` | Customer management (`clientes`)                                 |
| `services/reservas` | Reservations, dishes, status history, notifications              |
| `services/catalogo` | Restaurant tables and menu items (`mesas`, `platillos`)           |
| `shared/`  | Reusable configuration and database connection (`psycopg` 3)             |
| `app/`     | Original root FastAPI app — **preserved for compatibility** (see below)  |
| `database/`| Read-only verification script + idempotent test-data script (executed 2026-11-01) |
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
| Root `app/`| 8010 | http://localhost:8010         | /docs              |

Health checks: `GET /health` on every component, plus
`GET http://localhost:8000/health/services` on the gateway to see the three
microservices' status in one call.

## API Gateway routing map (v1)

| Gateway route                       | Forwards to                          | Method (Sprint 1) |
|-------------------------------------|--------------------------------------|--------------------|
| `/api/v1/clientes`                  | `clientes` service, same path        | GET                |
| `/api/v1/clientes/{id}`             | `clientes` service                   | GET                |
| `/api/v1/reservas`                  | `reservas` service, same path        | GET                |
| `/api/v1/reservas/{codigo_reserva}` | `reservas` service                   | GET                |
| `/api/v1/catalogo/mesas`            | `catalogo` service                   | GET                |
| `/api/v1/catalogo/mesas/{id}`       | `catalogo` service                   | GET                |
| `/api/v1/catalogo/platillos`        | `catalogo` service                   | GET                |
| `/api/v1/catalogo/platillos/{id}`   | `catalogo` service                   | GET                |
| `/health`                           | gateway's own health                 | GET                |
| `/health/services`                  | aggregated health of the 3 services  | GET                |

Sprint 1 is read-only by design; mutation methods will be enabled when the
corresponding endpoints exist in later sprints. Unavailable services return
a controlled JSON `503` (`{"detail": ..., "service": ...}`); timeouts return
`504`. Internal URLs are never exposed.

## Environment setup

1. Python 3.15 with a virtual environment (`.venv/`):
   `python -m venv .venv && .venv\Scripts\activate && pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and set `DATABASE_URL` with the NeonDB
   connection string. **Never commit `.env`** (it is gitignored).
3. Optional local gateway URLs are already defaulted in code; the placeholders
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
containing `DATABASE_URL` (the database stays external on NeonDB — there is
no local PostgreSQL container).

```bash
docker compose up --build
# Gateway: http://localhost:8000/docs
docker compose down
```

> **Verified 2026-11-01:** `docker compose config --quiet` passed, all
> images were built and all four containers started **healthy**. Health,
> aggregated health, read-only routing, Swagger and the controlled-failure
> path (stopping `catalogo` → gateway 503/degraded → restart → recovery)
> were exercised successfully — details in
> [test-results.md](docs/sprint-1/test-results.md) §4. One environment
> note: on this machine the Docker CLI must be invoked with Docker's
> `resources/bin` on `PATH` (otherwise the `docker-credential-desktop`
> helper cannot be found when pulling base images); this is a host
> configuration detail, not a repository issue.

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
# Unit tests (no network, no database):
.venv\Scripts\python -m pytest -q

# Live integration tests (read-only SELECT 1 against NeonDB):
RUN_DB_TESTS=1 .venv\Scripts\python -m pytest -q -m integration
```

Last run (2026-11-03): **39 passed, 6 skipped** (unit) and **6 passed**
(integration, opt-in read-only).
Details: [docs/sprint-1/test-results.md](docs/sprint-1/test-results.md).

## Known limitations and pending tasks

- Sprint 2 not started: **frontend** (confirmed for Sprint 2) and
  authentication (JWT/roles) — out of Sprint 1 scope; see
  [docs/sprint-2](docs/sprint-2/README.md).
- Read-only endpoints only; no CRUD mutations yet (later sprints).
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
