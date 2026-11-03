# Sprint Review (Template)

> **Status: the Sprint Review has not taken place.** This template must be
> completed during the real review with the product owner / professor.
> Nothing below is presented as an accomplished review event.

## Review event

- Date: ⏳ Pending
- Attendees: ⏳ Pending
- Demonstrated by: ⏳ Pending

## Demonstrated increment (what actually exists today)

Facts available to demonstrate (see [test-results.md](test-results.md)):

- Three microservices + gateway running locally with `/health` and Swagger.
- Gateway routing demo: `GET http://localhost:8000/api/v1/{clientes|reservas|catalogo/...}`
- Controlled 503/504 behavior when a service stops.
- Database: eight approved tables verified (read-only); test data inserted
  2026-11-01 with team authorization — 22 rows across the eight tables.
- Docker: **executed 2026-11-01 — images built, 4/4 containers healthy**
  (health, routing, Swagger and controlled-failure checks all passed).

## Product owner feedback

| Item | Feedback | Action |
|------|----------|--------|
| ⏳ Pending | ⏳ | ⏳ |

## Sprint scope vs. delivered

| Requirement | Delivered? | Notes |
|-------------|-----------|-------|
| Repo structure + documentation | ✅ | |
| 8 tables with constraints | ✅ verified | test data inserted 2026-11-01 (team-authorized) |
| 3 microservices with `/health` | ✅ | |
| API Gateway routing | ✅ | read-only (Sprint 1 scope) |
| Docker Compose starting everything | ✅ verified | 2026-11-01, 4/4 containers healthy |
| Scrum docs + traceability | 🟡 | review/retro/dailies pending the real events |

## Adjustments for the next sprint

- ⏳ Pending (fill during the review)
