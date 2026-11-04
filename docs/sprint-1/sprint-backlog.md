# Sprint 1 — Sprint Backlog

> User stories are derived from the approved conceptual design and the
> official Sprint 1 requirements.
>
> **Owners (2026-11-03):** the team confirmed *general* responsibilities —
> Noé Mejía and David Ávila: database and backend; Marina Valladares and
> Sebastián Rivera: frontend. The **individual split per story is not
> recorded**, so each owner below is shown at area level and the individual
> assignment remains *pending*. **Story Points: not assigned** (explicit
> team decision at planning — not a pending task).

## User stories and tasks

| ID  | User story | Tasks | Owner | Points | Status |
|-----|------------|-------|-------|--------|--------|
| US-01 | As a developer, I want a documented repository structure so that the team can collaborate without conflicts | Create service folders, `.gitignore`, `.dockerignore`, README | Noé / David (backend)* | No asignados | ✅ Done (verified 2026-11-01) |
| US-02 | As a developer, I want the eight approved tables verified so that the backend matches the approved design | Read-only schema inspection (columns, PK/FK, unique/check constraints, indexes, function, triggers) | Noé / David (database)* | No asignados | ✅ Done — [report](database-verification.md) |
| US-03 | As an administrator, I want test data in the database so that interfaces can be demonstrated later | Prepare idempotent `database/test_data.sql`; execute **only after team approval** | Noé / David (database)* | No asignados | ✅ Executed 2026-11-01 (team-authorized) — 22 rows; re-run inserted 0 ([evidence](test-results.md)) |
| US-04 | As a frontend developer, I want a customers microservice with `/health` so that customer data can be queried | FastAPI app, `/health`, read-only list/detail on `clientes` | Noé / David (backend)* | No asignados | ✅ Done (tests + live run) |
| US-05 | As a frontend developer, I want a reservations microservice exposing reservations with dishes and status history | FastAPI app, `/health`, read-only list/detail on `reservas`, `reserva_platillos`, `historial_estados` | Noé / David (backend)* | No asignados | ✅ Done (tests + live run) |
| US-06 | As a frontend developer, I want a catalog microservice for tables and menu items | FastAPI app, `/health`, read-only list/detail on `mesas`, `platillos` | Noé / David (backend)* | No asignados | ✅ Done (tests + live run) |
| US-07 | As a frontend developer, I want a single API Gateway that routes `/api/v1/**` so that the client only knows one base URL | Gateway app, HTTP proxying, routing map, consistent JSON errors, aggregated `/health/services` | Noé / David (backend)* | No asignados | ✅ Done (tests + live run) |
| US-08 | As an operator, I want Docker Compose to start the whole system with health checks | Dockerfile per service/gateway, compose file with dependencies and health checks | Noé / David (backend)* | No asignados | ✅ Verified 2026-11-01 — images built, 4/4 containers healthy |
| US-09 | As a developer, I want automated tests covering health, routing and error paths | pytest suite (unit + optional live integration) | Noé / David (backend)* | No asignados | ✅ Done — 39 unit + 6 integration passing (re-run 2026-11-03) |
| US-10 | As the team, I want Sprint 1 documentation with traceability to the approved design | This folder: goal, backlog, architecture, DB report, test evidence, templates | ⏳ Pendiente de asignación | No asignados | ✅ Done — planning, activities, review, retro and closure recorded (2026-11-03) |

\* **General area responsibility confirmed by the team** (database and
backend → Noé Mejía and David Ávila; see
[equipo-scrum](../gestion-del-proyecto/equipo-scrum.md)). **Which specific
story each of them owned is not recorded** — individual assignment per
story remains pending. Marina Valladares and Sebastián Rivera's confirmed
responsibility is frontend, which had no stories in Sprint 1 (deferred to
[Sprint 2](../sprint-2/README.md)).

## Sprint 2 preview (not in this sprint)

Authentication and access control (login, password hashing, JWT, roles) are
**not** part of Sprint 1 — the `administradores` table exists and is unused;
no authentication code was written. Whether this scope belongs to Sprint 2
is **not team-confirmed** yet (see [docs/sprint-2](../sprint-2/README.md)).

What *is* confirmed for Sprint 2: **the frontend** (Marina and Sebastián).
