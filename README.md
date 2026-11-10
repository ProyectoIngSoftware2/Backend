# Backend - ReservasPyS

Backend for **Punto y Sal**, a restaurant reservation and table management
system. Built with FastAPI and PostgreSQL (hosted on NeonDB).

> **Status: Sprint 1 implemented, verified and integrated (accepted by the
> team on 2026-11-03); Sprint 2 (authentication, authorization and CRUD)
> implemented on this branch and integrated with the centralized auth
> microservice.** Sprint 1 delivered via commit `1c6e0f3`
> and **PR #1 merged into `development` on 2026-11-03**. Sprint 2 adds
> JWT login through `services/auth` (PyJWT + bcrypt), role-based access
> control for the two existing roles (`administrador`, `cliente`), client
> data isolation (IDOR-proof ownership in SQL), CRUD for
> clientes/reservas/catalogo and full gateway method support. See
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
                    │       └──HTTP──► auth      :8004  (table: usuarios)
                    │                                login → signed JWT
                    │
                    └── uses shared/ (config + DB connection + JWT auth)
                                  │
                                  ▼
                        NeonDB PostgreSQL (external, port 5432)
```

| Component  | Responsibility                                                            |
|------------|---------------------------------------------------------------------------|
| `gateway/` | Single public entry point; HTTP routing to the four services (all methods) |
| `services/auth` | **Sprint 2:** the only authentication microservice — validates credentials against `usuarios` and issues signed JWTs |
| `services/clientes` | Customer management (`clientes`) + `usuarios` account provisioning (public registration, logical deactivation) |
| `services/reservas` | Reservations, dishes, status history, notifications              |
| `services/catalogo` | Restaurant tables and menu items (`mesas`, `platillos`)           |
| `shared/`  | Reusable configuration, database connection (`psycopg` 3) and **JWT/bcrypt auth layer** (`shared/auth.py`) |
| `app/`     | Original root FastAPI app — **preserved for compatibility** (see below)  |
| `database/`| Read-only verification script + idempotent test-data script (executed 2026-11-01) + Sprint 2 auth schema/seed scripts (executed 2026-11-03, verified read-only 2026-11-09) |
| `docs/`    | Sprint documentation + [frontend API integration guide](docs/api-integration.md) + [Sprint 2 documentation](docs/sprint-2/README.md) |

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
`GET http://localhost:8000/health/services` on the gateway to see the four
microservices' status in one call.

## API Gateway routing map (v1)

| Gateway route                       | Forwards to                          | Methods (Sprint 2)     | Access                |
|-------------------------------------|--------------------------------------|------------------------|-----------------------|
| **`/api/v1/auth/login`**            | **`auth` service**                  | **POST**           | public (login)        |
| `/api/v1/clientes`                  | `clientes` service, same path        | GET/POST/PUT/PATCH/DELETE | GET/DELETE: admin · POST: public |
| `/api/v1/clientes/{id}`             | `clientes` service                   | GET/PUT/PATCH/DELETE   | GET/PUT/PATCH: admin or owner · DELETE: admin |
| `/api/v1/reservas`                  | `reservas` service, same path        | GET/POST/PUT/PATCH/DELETE | GET: admin · POST: authenticated |
| `/api/v1/reservas/{codigo_reserva}` | `reservas` service                   | GET/PUT/PATCH/DELETE    | admin or owner (clients: cancellation only) |
| `/api/v1/catalogo/mesas[/{id}]`     | `catalogo` service                   | GET/POST/PUT/PATCH/DELETE | GET: public · writes: admin |
| `/api/v1/catalogo/platillos[/{id}]` | `catalogo` service                   | GET/POST/PUT/PATCH/DELETE | GET: public · writes: admin |
| `/health`                           | gateway's own health                 | GET                    | public                |
| `/health/services`                  | aggregated health of the 4 services  | GET                    | public                |

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
   characters. Optional: `JWT_ALGORITHM` (default `HS256`),
   `JWT_EXPIRE_MINUTES` (default `60`) and `CORS_ORIGINS`
   (comma-separated frontend origins for the gateway; empty = no CORS
   allowed).
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
containing `DATABASE_URL` plus a `JWT_SECRET` for the auth layer (the
database stays external on NeonDB — there is no local PostgreSQL
container). Compose refuses to start when either variable is missing
(`:?` interpolation), so a forgotten secret can never silently fall back
to a default.

```bash
# JWT_SECRET must be visible to Compose (shell export or .env):
export JWT_SECRET="<long-random-value>"   # see .env.example
docker compose up --build
# Gateway: http://localhost:8000/docs   (5 services: gateway, auth
# on :8004, clientes, reservas, catalogo)
docker compose down                        # needs the same JWT_SECRET exported
```

> **Sprint 2 verified (local, 2026-11-09 — post-integration):**
> `docker compose config --quiet` passed (and **fails by design**
> without `JWT_SECRET` — fail-closed); all five images built; all five
> containers **healthy**; a 19-scenario read-only smoke test through
> the gateway returned **19/19 passed**: gateway health `200`,
> aggregated health `ok` for all four downstream services, service
> healths `database: connected` ×4, admin login `200` + signed JWT
> (`sub`/`rol`/profile/`iat`/`exp`), client login `200` + `id_cliente`,
> wrong password `401 Invalid credentials` + `WWW-Authenticate: Bearer`,
> unknown e-mail `401` with an **identical body** (no enumeration),
> malformed login body `422`, protected list without token
> `401 Not authenticated` + challenge, garbage token `401`, expired
> token `401 Token has expired`, foreign-signature token `401`, client
> token on admin list `403 Not enough permissions`, admin token `200`,
> catalog reads `200` without token, catalog write `401` without token
> and `403` with a client token, client reading another client's
> profile `404` (anti-IDOR), and controlled failure (stop `catalogo` →
> route `503` + `degraded`, other routes unaffected → restart → full
> recovery). Sprint 1 verification (2026-11-01):
> [test-results.md](docs/sprint-1/test-results.md) §4.
>
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
> Sprint 2 auth-service test results:
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

**Independently re-verified read-only on 2026-11-09** (SELECT-only, no
DDL/DML): `public.usuarios` exists with its PK/UNIQUE/CHECK constraints,
`clientes.id_usuario` and `administradores.id_usuario` exist with their
FKs and UNIQUE links, and exactly two active test accounts exist with
valid 60-character bcrypt hashes correctly linked to their profiles (1
administrador, 1 cliente). This confirms the scripts were executed; the
"NOT executed yet" comment previously found in the SQL file headers was
stale and has been corrected in the scripts' comments (no SQL statement
was changed).

Safety rules: `database/schema_verification.sql` is read-only;
`database/test_data.sql` seeds idempotent test data and was
**executed on 2026-11-01 with explicit team approval** (22 rows; an
immediate re-run inserted 0 rows, confirming idempotency); the Sprint 2
scripts (`sprint2_auth_schema.sql`, `sprint2_auth_seed.sql`) were
**executed on 2026-11-03 with explicit team approval** and change only
the auth objects described above.

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

The suite covers authentication (login success/failure,
missing/invalid/expired/forged/wrong-algorithm tokens, unknown-role
tokens), the shared security layer, the auth microservice contract, RBAC
(401 vs 403 vs 404 per role), ownership isolation (no IDOR on profiles
or reservations), mass-assignment rejection, CRUD contracts with
parameterization/logical-delete assertions, trigger-error mapping (400),
gateway routing (all methods, auth forwarding, no-bypass) and
regression of the Sprint 1 endpoints.

**Post-integration verification (2026-11-09, `Dev/Noe-Mejia`):**

| Command | Result |
|---|---|
| `.venv\Scripts\python -m pytest -q` | **174 passed, 17 skipped** (exit 0; skips = opt-in live tests) |
| `… pytest -q -m integration` (test-account credentials from env, read-only) | **17 passed** (exit 0) |
| `.venv\Scripts\python -m pip check` | `No broken requirements found.` (exit 0) |
| `docker compose config --quiet` (with `JWT_SECRET` exported) | exit 0 — without it the command **fails by design** (fail-closed `:?` interpolation) |
| `docker compose build` / `up -d` | exit 0 — **5/5 containers healthy** (gateway, clientes, reservas, catalogo, auth) |
| 19-scenario read-only smoke through the gateway | **19/19 passed** (exit 0) |
| `docker compose down` | clean removal, 0 containers left |

The historical Phase 1–2 numbers of `Dev/David-Avila` (73 passed,
6 skipped, 2026-11-03) remain recorded in
[docs/sprint-2/test-results.md](docs/sprint-2/test-results.md).

## Known limitations and pending tasks

- **Frontend:** the team repository
  (`ProyectoIngSoftware2/Frontend`) currently contains **only planning
  documents — no application yet** (confirmed by inspection on
  2026-11-09). This backend deliverable gives the team the complete
  [API integration guide](docs/api-integration.md) as the definitive
  contract; the Frontend requirements also describe a `recepción` role
  and modules (mesas, horarios, reportes, bitácora) that do not exist in
  this backend yet — see the guide's known gaps.
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

- **Sprint 2 deliverables (security layer):**
  [docs/sprint-2/](docs/sprint-2/README.md) — goal, architecture,
  database verification, test results, closure.
- Sprint 1 deliverables: [docs/sprint-1/](docs/sprint-1/README.md).
- Project management (team, agreements, communication):
  [docs/gestion-del-proyecto/](docs/gestion-del-proyecto/equipo-scrum.md).
