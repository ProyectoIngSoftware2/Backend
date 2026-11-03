# Sprint 1 — Sprint Backlog

> User stories are derived from the approved conceptual design and the
> official Sprint 1 requirements. **Owners and story points are Pending** —
> the team must assign them; they are not invented here.

## User stories and tasks

| ID  | User story | Tasks | Owner | Points | Status |
|-----|------------|-------|-------|--------|--------|
| US-01 | As a developer, I want a documented repository structure so that the team can collaborate without conflicts | Create service folders, `.gitignore`, `.dockerignore`, README | ⏳ Pending | ⏳ Pending | ✅ Done (verified 2026-11-01) |
| US-02 | As a developer, I want the eight approved tables verified so that the backend matches the approved design | Read-only schema inspection (columns, PK/FK, unique/check constraints, indexes, function, triggers) | ⏳ Pending | ⏳ Pending | ✅ Done — [report](database-verification.md) |
| US-03 | As an administrator, I want test data in the database so that interfaces can be demonstrated later | Prepare idempotent `database/test_data.sql`; execute **only after team approval** | ⏳ Pending | ⏳ Pending | ✅ Executed 2026-11-01 (team-authorized) — 22 rows; re-run inserted 0 ([evidence](test-results.md)) |
| US-04 | As a frontend developer, I want a customers microservice with `/health` so that customer data can be queried | FastAPI app, `/health`, read-only list/detail on `clientes` | ⏳ Pending | ⏳ Pending | ✅ Done (tests + live run) |
| US-05 | As a frontend developer, I want a reservations microservice exposing reservations with dishes and status history | FastAPI app, `/health`, read-only list/detail on `reservas`, `reserva_platillos`, `historial_estados` | ⏳ Pending | ⏳ Pending | ✅ Done (tests + live run) |
| US-06 | As a frontend developer, I want a catalog microservice for tables and menu items | FastAPI app, `/health`, read-only list/detail on `mesas`, `platillos` | ⏳ Pending | ⏳ Pending | ✅ Done (tests + live run) |
| US-07 | As a frontend developer, I want a single API Gateway that routes `/api/v1/**` so that the client only knows one base URL | Gateway app, HTTP proxying, routing map, consistent JSON errors, aggregated `/health/services` | ⏳ Pending | ⏳ Pending | ✅ Done (tests + live run) |
| US-08 | As an operator, I want Docker Compose to start the whole system with health checks | Dockerfile per service/gateway, compose file with dependencies and health checks | ⏳ Pending | ⏳ Pending | ✅ Verified 2026-11-01 — images built, 4/4 containers healthy |
| US-09 | As a developer, I want automated tests covering health, routing and error paths | pytest suite (unit + optional live integration) | ⏳ Pending | ⏳ Pending | ✅ Done — 39 unit + 6 integration passing (rerun 2026-11-01) |
| US-10 | As the team, I want Sprint 1 documentation with traceability to the approved design | This folder: goal, backlog, architecture, DB report, test evidence, templates | ⏳ Pending | ⏳ Pending | 🟡 Written; review/retro/dailies pending the real events |

## Sprint 2 preview (not in this sprint)

Authentication and access control (login, password hashing, JWT, roles) are
**not** part of Sprint 1. The `administradores` table exists and is unused;
no authentication code was written.
