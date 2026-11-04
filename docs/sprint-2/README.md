# Sprint 2 Documentation

This folder collects the Sprint 2 artifacts for the Punto y Sal backend.
Sprint 2 delivered the **security layer (Option B)**: centralized
authentication and authorization — bcrypt password hashing (cost 12),
JWT generation/validation (PyJWT), a unified `usuarios` table, a new
auth microservice (port 8004) and the API Gateway POST proxy for
`/api/v1/auth/login`. Technical content was produced from actual
verification of the repository and the test suite (2026-11-03); the
database scripts and the Docker Compose run were executed on
**2026-11-03** (team confirmation). Fields with no confirmed data are
marked explicitly as **missing data** — they are never fabricated
(convention inherited from [Sprint 1](../sprint-1/README.md)).

> **Sprint 2 planning note (preserved from the previous placeholder):**
> the formal Sprint 2 planning session (objectives, stories,
> estimates, dates) has **not** been registered yet — **missing data**.
> The frontend remains confirmed for Sprint 2 and is owned by
> Marina Julissa Valladares Laínez and Sebastián Rivera García
> (see [equipo-scrum](../gestion-del-proyecto/equipo-scrum.md)).
> The security scope documented here was executed as Phases 1–2 of the
> Sprint 2 security setup.

## Artifact index

| #  | Artifact                                                       | Status                                                        |
|----|----------------------------------------------------------------|---------------------------------------------------------------|
| 1  | [Sprint Goal & Scope](sprint-goal.md)                           | ✅ Prepared 2026-11-03 (formal planning session: missing data) |
| 2  | [Architecture & Gateway](architecture.md)                       | ✅ Written and verified against the code (2026-11-03)          |
| 3  | [Database verification](database-verification.md)               | ✅ Both scripts executed on NeonDB (2026-11-03)                |
| 4  | [Testing evidence](test-results.md)                             | ✅ Real results recorded — 73 passed, 6 skipped (2026-11-03)   |
| 5  | [Sprint closure](cierre-sprint-2.md)                            | ✅ Closed 2026-11-03 — ready for PR into `development`         |
| +  | Previous placeholder (scope confirmations)                      | ✅ Preserved above — no confirmed information was lost         |

## Key facts for this sprint

- **Option B chosen:** one unified `public.usuarios` authentication
  table (`correo` unique, `password_hash`, `rol CHECK
  ('administrador','cliente')`, `activo`), linked **1:1** to
  `administradores` and `clientes` via nullable `id_usuario` foreign
  keys — credentials are read from `usuarios` only; the legacy
  `administradores.password_hash` is no longer read by the auth path.
- **Database executed (2026-11-03):**
  `database/sprint2_auth_schema.sql` (table + 1:1 links) and
  `database/sprint2_auth_seed.sql` (test admin with a real bcrypt
  cost-12 hash, replacing the Sprint 1 placeholder) — both scripts are
  idempotent by construction
  ([database-verification.md](database-verification.md)).
- **Crypto decisions:** bcrypt **cost 12** via `bcrypt==4.2.1` —
  chosen **instead of `passlib[bcrypt]==1.7.4`** (passlib has been
  unmaintained since 2016); JWT via **`pyjwt==2.10.1`**, HS256,
  60-minute default expiry, claims `sub` / `role` / `correo` / `iat` /
  `exp`.
- **New auth microservice** at **`:8004`** (`services/auth/`): only
  `POST /api/v1/auth/login` plus `/health`; uniform `401 "Invalid
  credentials"` for unknown user, wrong password and inactive account
  (no account enumeration), `503` database down, `500` unexpected —
  same error contract as the other services.
- **Gateway:** new `POST /api/v1/auth/login` route proxied to
  `AUTH_SERVICE_URL` (default `http://localhost:8004`, Compose
  `http://auth:8004`); the gateway forwards the `Authorization` header
  untouched and **never parses tokens itself**. `/health/services`
  still aggregates exactly the three business services (Sprint 1
  contract preserved).
- **RBAC dependency ready:** `shared/security.py` exposes
  `require_role(...)` (401 missing/expired/invalid, 403 wrong role);
  enforcement on service routes is a pending follow-up — the three
  business services were **not** modified in this phase.
- **Environment:** `JWT_SECRET` is **fail-fast** in Compose
  (`${JWT_SECRET:?…}`, mirroring `DATABASE_URL`);
  `JWT_ALGORITHM`/`JWT_EXPIRATION_MINUTES` default to `HS256`/`60`.
  `shared/security.py` falls back to safe defaults so unit tests run
  with no `.env` (verified: the Phase 1 suite passes without
  `DATABASE_URL`).
- **Tests: 73 passed, 6 skipped** on 2026-11-03 (60 prior baseline +
  13 new in `tests/test_auth_service.py` and
  `tests/test_auth_gateway.py`) — see [test-results.md](test-results.md).
- **Docker Compose: 5/5 containers healthy** (gateway, clientes,
  reservas, catalogo, auth — verified 2026-11-03).
- **Delivery:** all changes are on branch `Dev/David-Avila`,
  **uncommitted**; the Pull Request into `development` is the next
  step (see [cierre-sprint-2.md](cierre-sprint-2.md)).

## Conventions

- New technical code, identifiers and documentation in English.
- User-facing API messages may remain in Spanish.
- Database identifiers remain in Spanish to preserve the existing schema.
- Never record secrets, `.env` contents or real credentials in this
  folder (the test-admin password lives only in the header comment of
  `database/sprint2_auth_seed.sql`, never here).
