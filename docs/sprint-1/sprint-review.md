# Sprint Review — Sprint 1

> **Status: held on 2026-11-03** (confirmed by the team). Content below is
> based on confirmed team information; technical facts link to their
> evidence. No product owner was designated, so feedback is recorded as
> team acceptance.

## Review event

| Field | Value |
|---|---|
| Date | 2026-11-03 |
| Attendees | All four team members (Noé Mejía, David Ávila, Marina Valladares, Sebastián Rivera) |
| Outcome | **The backend was accepted by the team; no additional corrections were requested** |

> Who presented the increment was not recorded — no attribution is made
> without evidence. No formal Product Owner or Scrum Master was designated
> (see [equipo-scrum](../gestion-del-proyecto/equipo-scrum.md)); the
> decision was made by consensus among the four members.

## Demonstrated increment (what actually exists)

Facts available to demonstrate (see [test-results.md](test-results.md)):

- Three microservices + gateway running with `/health` and Swagger.
- Gateway routing demo: `GET http://localhost:8000/api/v1/{clientes|reservas|catalogo/...}`
- Controlled 503/504 behavior when a service stops.
- Database: eight approved tables verified (read-only); test data inserted
  2026-11-01 with team authorization — 22 rows across the eight tables.
- Docker: images built, **4/4 containers healthy** (health, routing,
  Swagger and controlled-failure checks all passed).
- Automated tests: **39 unit + 6 integration passing** (re-run
  2026-11-03, after all changes).
- Integration: PR #1 merged into `development` on 2026-11-03
  ([evidence](evidencias/README.md)).

## Product owner / team feedback

| Item | Feedback | Action |
|------|----------|--------|
| Backend increment presented 2026-11-03 | **Accepted by all four team members; no additional corrections requested** | None |
| Frontend | Not part of this increment — deferred to Sprint 2 | Plan in [Sprint 2](../sprint-2/README.md) |

## Sprint scope vs. delivered

| Requirement | Delivered? | Notes |
|-------------|-----------|-------|
| Repo structure + documentation | ✅ | |
| 8 tables with constraints | ✅ verified | test data inserted 2026-11-01 (team-authorized) |
| 3 microservices with `/health` | ✅ | |
| API Gateway routing | ✅ | read-only (Sprint 1 scope) |
| Docker Compose starting everything | ✅ verified | 4/4 containers healthy |
| Automated tests | ✅ | 39 unit + 6 integration (re-run 2026-11-03) |
| Integration via Pull Request | ✅ verified | PR #1 merged into `development` 2026-11-03 |
| Scrum docs + traceability | ✅ | planning, activities, review, retro recorded; Daily Scrum: none held (confirmed); burndown: no data available (documented) |

## Adjustments for the next sprint

Taken from the confirmed [retrospective](sprint-retrospective.md):

- More constant communication and better synchronization among members.
- Coordinate activities in advance.
- Better organization and tracking of tasks (a formal board was not used
  in Sprint 1 — see [herramientas y comunicación](../gestion-del-proyecto/herramientas-y-comunicacion.md)).
- Frontend work starts in Sprint 2 (preliminary tech research already
  shared by Marina on 2026-11-03; no technical decisions yet).

## Pending follow-ups

- Individual contribution reports (per team member).
- Per-story owner assignment in the [Sprint Backlog](sprint-backlog.md)
  (only general area responsibilities are confirmed).
