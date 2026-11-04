# Sprint 1 — Sprint Goal

> **Confirmed by the team at Sprint Planning on 2026-10-21** (objective,
> scope and backend/frontend division were defined there and accepted by
> all four members). Development period: 2026-10-22 → 2026-11-03; accepted
> at the review on 2026-11-03 ([sprint-review.md](sprint-review.md)).

## Goal statement

Deliver a deployable backend foundation for Punto y Sal consisting of three
independent microservices and an API Gateway, backed by the approved
eight-table NeonDB database, with health checks, automated tests, Docker
orchestration files and traceability documentation — establishing a
verified base for future functionalities, whose scope will be defined
during Sprint 2 planning.

## Definition of Done (Sprint 1)

- [x] Repository structure and documentation in place.
- [x] Eight approved tables verified in the database (relationships,
      constraints, `generar_codigo_reserva()`); no destructive changes.
- [x] Test data inserted (team-authorized execution of
      `database/test_data.sql` on 2026-11-01; 22 rows, idempotent).
- [x] Three independent microservices, each with `/health`.
- [x] API Gateway routing requests to all three services under `/api/v1/`.
- [x] Docker Compose starts all components (**verified 2026-11-01** —
      images built, 4/4 containers healthy).
- [x] Scrum documentation and traceability to the approved design.
- [x] Integrated via Pull Request into `development` (PR #1 merged
      2026-11-03) and accepted by the team at the Sprint Review.

## Success criteria

| Criterion | Measurement | Result |
|-----------|-------------|--------|
| Services healthy | `/health` returns 200 with database status | ✅ 3/3 verified locally (2026-11-01) |
| Gateway routes | Requests reach the correct service | ✅ Verified end-to-end (2026-11-01) |
| Controlled errors | JSON 503/504 when a service is down | ✅ Verified with catalogo stopped |
| Automated tests | Suite passes | ✅ 45 passing: 39 unit + 6 live integration (the 6 integration tests are skipped unless `RUN_DB_TESTS=1`); rerun 2026-11-03 |
| Swagger available | `/docs` on every component | ✅ 5/5 returned HTTP 200 |
| Database intact | Read-only inspection, 8 tables present | ✅ Verified; schema untouched (only team-authorized test-data INSERTs, 2026-11-01) |
| Docker orchestration | `docker compose up --build` runs | ✅ Verified 2026-11-01 — 4/4 containers healthy |
