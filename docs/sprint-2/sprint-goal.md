# Sprint 2 — Sprint Goal

> Prepared 2026-11-03 from the executed security work (Phases 1–2). A
> **formal Sprint 2 planning session has not been registered** — objective,
> stories, estimates and dates are **missing data** and are not fabricated
> here (see the placeholder note preserved in [README.md](README.md)).
> Frontend remains confirmed for Sprint 2 (Marina, Sebastián).

## Goal statement

Deliver a centralized authentication and authorization layer for the
Punto y Sal backend (Option B): a unified `usuarios` table with 1:1
links to `administradores` and `clientes`, bcrypt password hashing
(cost 12), JWT creation and validation (PyJWT), a dedicated auth
microservice exposing `POST /api/v1/auth/login`, and API Gateway
integration so the frontend has a single, versioned login entry point —
without breaking any Sprint 1 contract (read-only routes, health
aggregation, controlled error responses).

## Scope delivered (Phases 1–2)

| # | Scope item | Delivered in |
|---|------------|--------------|
| 1 | Security dependencies (`PyJWT==2.15.1`, `bcrypt==5.0.0`, Python 3.12+ wheels) | Phase 1 — `requirements.txt` |
| 2 | Shared security layer: `hash_password`, `verify_password`, `create_access_token`, `decode_token`, `get_current_user`, `require_roles` (fail-closed env) | Phase 1 — `shared/auth.py` (canonicalized during integration; `shared/security.py` removed) |
| 3 | JWT environment configuration (`JWT_SECRET`, `JWT_ALGORITHM`, `JWT_EXPIRE_MINUTES`) | Phase 1 — `.env.example` |
| 4 | Option B schema: `usuarios` table + 1:1 `id_usuario` FKs on `administradores`/`clientes` | Phase 2 — `database/sprint2_auth_schema.sql` (**executed 2026-11-03**) |
| 5 | Idempotent test-admin seed with a bcrypt cost-12 hash (replaces the Sprint 1 placeholder) | Phase 2 — `database/sprint2_auth_seed.sql` (**executed 2026-11-03**) |
| 6 | Auth microservice (`services/auth/`, port 8004) with `POST /api/v1/auth/login` | Phase 2 |
| 7 | Gateway `POST /api/v1/auth/login` proxy + `AUTH_SERVICE_URL` | Phase 2 — `gateway/app/main.py` |
| 8 | Compose wiring: auth service, `JWT_SECRET` fail-fast, JWT env passthrough | Phase 2 — `docker-compose.yml` |
| 9 | Tests: `tests/test_security.py` (34, re-adapted to `shared/auth.py`), `tests/test_auth_service.py` (9), `tests/test_auth_gateway.py` (4) | Phases 1–2 + integration round |

**Explicitly out of scope for Phases 1–2** (recorded so the boundary is
traceable): enforcement of the RBAC dependency on the three business
services, frontend, refresh-token flow, and any mutation endpoints.
> **Integration note:** the enforcement of `require_roles` /
> `get_current_user` on the business services — originally out of scope
> for Phases 1–2 — was completed in the integration round on
> `Dev/Noe-Mejia` (see [architecture.md](architecture.md) decision 8).

## Definition of Done (Sprint 2, Phases 1–2)

- [x] Dependencies added and installable on Python 3.12+ (abi3 wheel
      verified on the local 3.15 venv; images run 3.12).
- [x] `shared/auth.py` standalone: unit tests pass **without**
      `DATABASE_URL` or a `.env` file (conftest injects a test-only
      `JWT_SECRET`; production configuration is fail-closed).
- [x] `database/sprint2_auth_schema.sql` executed on NeonDB
      (2026-11-03): `usuarios` created, 1:1 links in place.
- [x] `database/sprint2_auth_seed.sql` executed on NeonDB
      (2026-11-03): test admin seeded with bcrypt cost-12 hash,
      legacy placeholder replaced, profile linked.
- [x] Auth service answers `POST /api/v1/auth/login` with a signed JWT
      (`sub`, `rol`, `correo`, profile id) and the established
      422/401/503/500 error contract.
- [x] Gateway proxies `POST /api/v1/auth/login` (OpenAPI shows `post`
      only for that path).
- [x] `docker compose config --quiet` valid; Compose run starts
      **5/5 containers healthy** (2026-11-03).
- [x] Full suite green: **73 passed, 6 skipped**
      (2026-11-03 — see [test-results.md](test-results.md)).
- [x] Integrated into `Dev/Noe-Mejia` as a prepared (uncommitted) merge
      of `origin/development` — awaiting explicit approval; no commit
      or remote action taken.

## Success criteria

| Criterion | Measurement | Result |
|-----------|-------------|--------|
| Login works end-to-end | Valid credentials return a decodable JWT | ✅ In-process gateway→auth test + service test (2026-11-03) |
| No account enumeration | Unknown user, wrong password, inactive account return an identical 401 | ✅ Asserted in `test_auth_service.py` |
| Controlled failures | 503 (DB down) / 500 (unexpected) / 422 (bad body), no internals leaked | ✅ Asserted, including gateway 503 pass-through |
| Password storage | bcrypt cost 12, salted per hash, >72-byte input rejected | ✅ `shared/auth.py` + `test_security.py` |
| Token integrity | Tampered/expired/foreign-signed tokens rejected | ✅ `test_security.py` (`TokenError`) |
| Automated tests | Suite passes | ✅ **73 passed, 6 skipped** (2026-11-03) |
| Docker orchestration | `docker compose up --build` runs | ✅ Verified 2026-11-03 — **5/5 containers healthy** |
| Database intact | Only the two Sprint 2 scripts executed (team-approved) | ✅ 9 tables; Sprint 1 structure untouched — see [database-verification.md](database-verification.md) |
| Sprint 1 preserved | Existing 60-test baseline still green, routes unchanged | ✅ Baseline re-run green in the same suite execution |
