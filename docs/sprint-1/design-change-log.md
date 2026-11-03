# Design Change Log (Sprint 1)

Traceability of changes relative to the **approved conceptual design**.
The approved design remains the source of truth; no table, column,
constraint or business rule was redesigned.

## Changes to the database design

| # | Change | Reason | Executed? | Approval |
|---|--------|--------|-----------|----------|
| — | **None.** | The live schema already matches the approved design (verified read-only on 2026-11-01, see [database-verification.md](database-verification.md)). | n/a | n/a |

## Resolved items (2026-11-01, team authorization)

| # | Item | Resolution |
|---|------|------------|
| 1 | Insert test data (`database/test_data.sql`) | **Authorized and executed 2026-11-01.** Script pre-flight checked (INSERT/SELECT only, `WHERE NOT EXISTS` guards, FK order) then run against the configured database; 22 rows total, re-run inserted 0 (idempotent). See [test-results.md](test-results.md). |
| 2 | Root `app/` overlap with `services/reservas` | **Decision: preserve `app/` unchanged** as the legacy/compatibility application; the three services under `services/` are the official Sprint 1 microservices (see architecture decision 5). |
| 3 | Branch naming: official `develop` vs actual `development` | **Decision: keep `development` as the team's integration branch** (authorized). The official course guideline specifies `develop`; no rename was performed. Recorded in architecture.md. |
| 4 | F-01 approval: reservations resolving dish names from catalogo over HTTP | **APPROVED by the team (2026-11-01).** See the F-01 row below for the recorded decision and rationale. |

## Changes to the application architecture (relative to the initial repo)

| Date | Change | Reason | Impact |
|------|--------|--------|--------|
| 2026-10-29 | `shared/` module created; root `app/` kept unchanged | Single source of DB configuration without breaking the original app | None (additive) |
| 2026-11-01 | Three microservices + gateway implemented under `services/` and `gateway/` | Sprint 1 requirements | New code only; no existing file overwritten |
| 2026-11-01 | Gateway proxies GET only (mutations deferred) | Sprint 1 is read-only; services expose no mutations yet | Later sprints will add methods to both layers |
| 2026-11-01 | `requirements.txt`: added `httpx` (gateway proxying + TestClient) and `pytest` (tests) | Strictly necessary for Sprint 1 deliverables | Pinned versions; no upgrades of existing packages |

## Post-audit corrections (2026-11-01)

Implemented after the independent Sprint 1 audit. These are **technical
clarifications and corrections**, not redesigns: no table, column,
constraint or business rule of the approved design changed.

| Ref | Change | Reason | Status / Approval |
|-----|--------|--------|-------------------|
| F-01 | The reservations service no longer queries the `platillos` table (the JOIN at `services/reservas/app/main.py` was removed). Dish names in the reservation detail are now resolved by calling the catalogo microservice over HTTP (`GET /api/v1/catalogo/platillos/{id}`) with a 5 s timeout and controlled 503/504 errors. `docker-compose.yml` passes `CATALOGO_SERVICE_URL` to the reservas container. | Microservice table-ownership violation found in the audit: `platillos` belongs to catalogo. Respects the rule of never reading another service's tables and avoids circular dependencies (catalogo does not call reservas). | **APPROVED (team decision, 2026-11-01).** Decision: reservations communicates with catalogo exclusively over HTTP; direct cross-service table access is prohibited. Rationale: preserves single table ownership (`platillos` owned by catalogo only), keeps a one-way dependency (reservas → catalogo, no cycle), keeps each service independently deployable, and returns controlled 503/504 JSON errors when catalogo is unavailable. Verified live on 2026-11-01: reservation detail returns dish names resolved through catalogo's HTTP API with data consistent with the inserted test records. |
| F-02 | Services and `shared/database.py` now catch `psycopg.OperationalError` specifically (HTTP 503, same contract as before), log unexpected exceptions with `logging.exception`, and return a generic HTTP 500 ("Internal server error") for non-database bugs instead of a misleading "database unavailable". | The audit found bare `except Exception` blocks that masked real errors as 503s with no logging. | Implemented (no design impact; approval not required). |
| F-06 | `database/test_data.sql` header now describes the actual `WHERE NOT EXISTS` safeguards (no `ON CONFLICT` clauses exist), the reservation guard also matches the table, and `reserva_platillos` rows target a reservation by its full business fingerprint (customer + table + date/time + duration + guests + status + note) instead of the timestamp alone. | Audit accuracy findings; hardens idempotency. | **Implemented and executed 2026-11-01** (team-authorized): pre-flight guard confirmed INSERT/SELECT only, run committed 22 rows, immediate re-run inserted 0 (sequential re-run safe). |
| F-07 | Test suite hardened: SQL-parameterization tests, proper closing of gateway test HTTP clients, new F-01/F-02 behavior tests, and two opt-in live read-only list tests. | Audit test-gap findings. | Implemented (no design impact). |

## Open design questions for the team

**None open.** All four previously open questions (root `app/`, branch
naming, test-data execution, F-01 approval) were resolved by the team
authorizations of 2026-11-01 and are recorded in the "Resolved items"
table above.
