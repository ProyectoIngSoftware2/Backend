# Architecture and Routing (Sprint 1)

## Overview

Microservices-oriented backend: three independently deployable FastAPI
services plus an API Gateway, sharing a thin database module and talking to
an external NeonDB PostgreSQL instance. No service imports another service's
code; communication between gateway and services is real HTTP.

```
                    ┌──────────────────────────┐
                    │  API Gateway  (port 8000) │  uvicorn gateway.app.main:app
                    │  public entry point       │
                    └────────────┬─────────────┘
             HTTP proxy ─────────┼────────────── HTTP proxy
        ┌────────────────────────┼────────────────────────┐
        ▼                        ▼                        ▼
┌───────────────────┐  ┌───────────────────┐  ┌───────────────────┐
│ clientes (:8001)  │  │ reservas (:8002)  │  │ catalogo (:8003)  │
│ uvicorn app.main  │  │ uvicorn app.main  │  │ uvicorn app.main  │
│ tables: clientes  │  │ tables: reservas, │  │ tables: mesas,    │
│                   │  │  reserva_platillos│  │  platillos        │
│                   │  │  historial_estados│  │                   │
│                   │  │  notificaciones   │  │                   │
└─────────┬─────────┘  └────────┬──────────┘  └─────────┬─────────┘
          └─────────────────────┼───────────────────────┘
                                ▼
                    ┌───────────────────────┐
                    │  shared/database.py   │  psycopg 3 + pydantic-settings
                    │  DATABASE_URL from env│  (reads local .env in dev)
                    └───────────┬───────────┘
                                ▼
                    ┌───────────────────────┐
                    │ NeonDB PostgreSQL     │  external, port 5432
                    │ (8 approved tables)   │
                    └───────────────────────┘
```

> **Service-to-service call (F-01, APPROVED 2026-11-01):** `reservas` →
> `catalogo` — HTTP `GET /api/v1/catalogo/platillos/{id}` (5 s timeout,
> controlled 503/504) to resolve dish names, replacing the direct
> `platillos` JOIN found by the audit. One-way dependency; no cycle.
> Verified live: reservation detail returns catalogo-resolved dish names.

## Repository layout

```
Backend/
├── app/                       # original root app (preserved, still runs)
├── shared/                    # shared config + DB connection (English code)
│   ├── __init__.py
│   └── database.py            # Settings, get_connection(), check_connection()
├── services/
│   ├── clientes/              # Dockerfile + app/{__init__,main}.py
│   ├── reservas/              # Dockerfile + app/{__init__,main}.py
│   └── catalogo/              # Dockerfile + app/{__init__,main}.py
├── gateway/                   # Dockerfile + app/{__init__,main}.py
├── database/                  # read-only verification + test data (executed)
├── docs/sprint-1/             # this documentation
├── tests/                     # pytest suite (unit + optional live)
├── docker-compose.yml         # 4 services, health checks, no DB container
├── dockerignore / .env.example / requirements.txt / README.md
```

## Decisions

1. **HTTP proxying in the gateway** (httpx): the gateway forwards method,
   path (original `raw_path` — Starlette can rewrite `scope["path"]`), query
   and headers; hop-by-hop headers are stripped; redirect `location` headers
   are rewritten to remove internal hosts. Errors map to JSON 503
   (unreachable) / 504 (timeout) without leaking internals.
2. **Read-only Sprint 1**: only GET endpoints exist, matching the official
   Sprint 1 scope. Mutation methods are deliberately not proxied yet.
3. **Database rules stay in the database**: triggers already generate
   reservation codes, history and notifications and validate transitions and
   table overlap — services do not reimplement them.
4. **`shared/` module**: single source of connection settings; services add
   the repository root to `sys.path` at startup (works locally with
   `--app-dir` and inside containers where `shared/` is copied to `/app`).
5. **Root `app/` preserved (decision 2026-11-01)**: the root application
   is kept unchanged as the legacy/compatibility entry point (it is still
   tested by `tests/test_root_app.py` and documented in the README). The
   three independent services under `services/` are the **official
   Sprint 1 microservices**; Docker Compose and the Gateway route all
   traffic to them only (the root app is not part of the compose file and
   no service imports its code). No code was migrated, duplicated or
   refactored.
6. **No local PostgreSQL container** — NeonDB remains the single database.
7. **Service-to-service HTTP for dish names (F-01, APPROVED 2026-11-01)**:
   the reservations service never queries `platillos` (owned by catalogo).
   Its reservation detail reads `reserva_platillos` (own table) and
   resolves dish names by calling catalogo over HTTP with a 5 s timeout,
   returning a controlled 503/504 JSON error if catalogo is unreachable.
   Dependency direction is one-way (reservas → catalogo), so there is no
   circular dependency. **Team decision:** HTTP is the only permitted
   cross-service data path; direct cross-service table access remains
   prohibited. Rationale: single table ownership, independent deployability,
   no cycles (see [design-change-log.md](design-change-log.md)).

## Ports and URLs

| Component | Port | Health | Swagger |
|-----------|------|--------|---------|
| gateway | 8000 | `/health`, `/health/services` | `/docs` |
| clientes | 8001 | `/health` | `/docs` |
| reservas | 8002 | `/health` | `/docs` |
| catalogo | 8003 | `/health` | `/docs` |
| root app | 8010 | `/health` | `/docs` |

## Gateway routing map

| Gateway route | Downstream |
|---|---|
| `/api/v1/clientes` and `/api/v1/clientes/**` | `CLIENTES_SERVICE_URL` |
| `/api/v1/reservas` and `/api/v1/reservas/**` | `RESERVAS_SERVICE_URL` |
| `/api/v1/catalogo` and `/api/v1/catalogo/**` | `CATALOGO_SERVICE_URL` |
| `/health` | gateway itself |
| `/health/services` | aggregated `/health` of all three |

Internal URLs come from environment variables (`CLIENTES_SERVICE_URL`,
`RESERVAS_SERVICE_URL`, `CATALOGO_SERVICE_URL`); Docker Compose sets them to
the Compose service names (`http://clientes:8001`, …). Local defaults are
`http://localhost:8001-8003`.

## Branch structure (team decision recorded 2026-11-01)

The official course guideline requires `main`, `develop` and one personal
branch per member. The team has **authorized the existing `development`
branch as the team's integration branch**; this repository uses
**`development`** (plus `main` and `Dev/Noe-Mejia` / `Dev/David-Avila`).

- `development` is preserved and used as-is — it was **not** renamed, and
  no additional integration branch was created.
- The naming difference (`develop` in the official guideline vs
  `development` in this repository) is explicitly acknowledged here for
  traceability; aligning the name would require separate team coordination
  and was not performed.
