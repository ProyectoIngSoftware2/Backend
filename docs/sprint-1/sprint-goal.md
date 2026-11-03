# Sprint 1 — Sprint Goal

> Drafted from the official Sprint 1 requirements. Confirm with the team
> before the Sprint Review.

## Goal statement

Deliver a deployable backend foundation for Punto y Sal consisting of three
independent microservices and an API Gateway, backed by the approved
eight-table NeonDB database, with health checks, automated tests, Docker
orchestration files and traceability documentation — so that Sprint 2 can
build authentication on top of a verified architecture.

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

## Success criteria

| Criterion | Measurement | Result |
|-----------|-------------|--------|
| Services healthy | `/health` returns 200 with database status | ✅ 3/3 verified locally (2026-11-01) |
| Gateway routes | Requests reach the correct service | ✅ Verified end-to-end (2026-11-01) |
| Controlled errors | JSON 503/504 when a service is down | ✅ Verified with catalogo stopped |
| Automated tests | Suite passes | ✅ 45 passing: 39 unit + 6 live integration (the 6 integration tests are skipped unless `RUN_DB_TESTS=1`); rerun 2026-11-01 |
| Swagger available | `/docs` on every component | ✅ 5/5 returned HTTP 200 |
| Database intact | Read-only inspection, 8 tables present | ✅ Verified; schema untouched (only team-authorized test-data INSERTs, 2026-11-01) |
| Docker orchestration | `docker compose up --build` runs | ✅ Verified 2026-11-01 — 4/4 containers healthy |
