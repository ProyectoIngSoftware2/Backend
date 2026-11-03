# Technical Implementation Checklist (Sprint 1)

Verified on 2026-11-01 on the development machine. Each ✅ has concrete
evidence; ⏳ items state exactly why they are pending.

## Repository structure and documentation

- [x] Service directories with independent entry points (`services/*/app/main.py`)
- [x] `shared/` module for configuration and DB connection
- [x] Root `README.md` with architecture, ports, routing map and run instructions
- [x] `.gitignore` (venvs, `.env`, caches) — `.env` confirmed ignored (`git check-ignore`)
- [x] `.dockerignore` (no `.env`, no venvs, no `.git` in images)
- [x] `.env.example` with placeholders only (no secrets)
- [x] `docs/sprint-1/` organized with all required artifacts

## Database

- [x] All 8 approved tables exist with PK/FK/unique/check constraints — [report](database-verification.md)
- [x] `generar_codigo_reserva()` exists
- [x] Triggers for history, notifications, validation verified
- [x] Read-only verification script in `database/`
- [x] Test data inserted — **executed 2026-11-01 with explicit team
      authorization**: `database/test_data.sql` (pre-flight checked
      INSERT/SELECT only, FK-ordered, `WHERE NOT EXISTS` guards); 22 rows;
      immediate re-run inserted 0 ([evidence](test-results.md) §5)
- [x] No destructive SQL executed at any point

## Microservices

- [x] `clientes`, `reservas`, `catalogo`: separate FastAPI apps with own entry point
- [x] Each exposes `/health` with clear JSON (`service`, `status`, `database`)
- [x] Graceful DB failure handling (HTTP 503 JSON, no secrets leaked)
- [x] Own OpenAPI docs per service (`/docs`, `/openapi.json`)
- [x] Each service uses only its own tables; no cross-service imports
- [x] Credentials only from environment variables (`DATABASE_URL`)
- [x] Each service starts and answers `/health` — verified as real processes (2026-11-01)

## API Gateway

- [x] Separate FastAPI app, single public entry point
- [x] HTTP proxying (httpx) — not imported routers
- [x] Versioned routes under `/api/v1/` for all three services
- [x] Gateway `/health` + aggregated `/health/services`
- [x] Consistent JSON errors: 503 (unavailable), 504 (timeout), no internal URLs leaked
- [x] Routing map documented (README + architecture.md)
- [x] End-to-end routing verified against live services (2026-11-01)

## Docker

- [x] One Dockerfile per microservice + gateway (build context = repo root)
- [x] `docker-compose.yml`: 4 containers, service-name networking, health checks,
      `depends_on: service_healthy` for the gateway, `DATABASE_URL` from host `.env`
- [x] No local PostgreSQL container (external NeonDB)
- [x] Compose file structurally validated (YAML parse + assertions)
- [x] **Containers built and started — verified 2026-11-01** with Docker
      Desktop 29.9.2: `docker compose config --quiet` OK, `up --build -d`
      built all images, `ps` shows 4/4 **healthy**, health/routing/Swagger
      endpoints and the controlled-failure path all verified
      (see [test-results.md](test-results.md) §4)

## Testing

- [x] pytest suite: health (ok/down), OpenAPI, list/detail endpoints, 404s,
      gateway routing to all three services, 503/504, aggregated health, root app
- [x] Live integration tests (read-only `SELECT 1`) behind `RUN_DB_TESTS=1`
- [x] All tests passing: 39 unit + 6 integration (rerun 2026-11-01, after all authorized changes)
- [ ] Test evidence attached to the Sprint Review — ⏳ pending the real review event

## Compliance / scope

- [x] No Sprint 2 code (no auth, no JWT, no roles)
- [x] No frontend code created
- [x] No schema changes; data writes limited to the team-authorized
      `database/test_data.sql` execution (2026-11-01); `.env` untouched and unexposed
- [x] No Git mutations (no add/commit/push/branch operations)
