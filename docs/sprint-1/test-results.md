# Test Results (Sprint 1)

- **Date executed:** 2026-11-01 (post-audit corrections re-run same day;
  test-data execution and F-01 live verification added the same day)
- **Environment:** Windows, Python 3.15.2, `.venv`, branch `Dev/Noe-Mejia`
- **Database:** configured Neon database; read-only queries except the
  team-authorized `database/test_data.sql` execution (see §5)

## 1. Automated test suite

| Command | Result |
|---------|--------|
| `.venv\Scripts\python -m pytest -q` | **39 passed, 6 skipped** (skips = live tests, disabled by default) |
| `RUN_DB_TESTS=1 .venv\Scripts\python -m pytest -q -m integration` | **6 passed** |

Coverage of the suite:

- Health endpoints of all three services: 200 (ok) and 503 (db down)
- OpenAPI (`/openapi.json`) present for every service and the gateway
- List/detail endpoints (fakes, no network): empty lists, found rows, 404s
- DB failure on data endpoints → controlled 503 (psycopg `OperationalError`)
- Unexpected (non-database) errors → generic 500 with `logging.exception`
  traceback logged, no SQL/traceback/URL leaked to the client (F-02)
- SQL parameterization: values passed as `%s` parameters, never
  interpolated into SQL text (F-07)
- F-01: reservation detail resolves dish names via HTTP (mock transport),
  asserts no `platillos` SQL executes, controlled 503 (unreachable) and
  504 (timeout), no catalogo call when the reservation has no dishes
- Gateway: own health, aggregated health (all-ok and all-down), routing to
  all three services, downstream 404 pass-through, JSON 503 when a service
  is unreachable (asserts no internal URL/traceback leaks), JSON 504 on
  timeout, JSON 404 outside the routing map; test HTTP clients closed
- Root `app/`: info endpoint, health with fake DB, health 503
- `shared/database.check_connection()`: True/False paths (incl. psycopg)
- Live integration (opt-in): `/health` on root app + 3 services plus two
  read-only list endpoints (`/api/v1/clientes`, `/api/v1/reservas`)
  against real NeonDB — SELECT only, no writes

## 2. Manual end-to-end run (real processes, 2026-11-01)

Started five uvicorn processes (root :8010, clientes :8001, reservas :8002,
catalogo :8003, gateway :8000) and exercised them with `curl`:

| Check | Expected | Actual |
|-------|----------|--------|
| `GET :8001/8002/8003/health` | 200, `database: connected` | ✅ `{"service":"…","status":"ok","database":"connected"}` ×3 |
| `GET :8000/health` | 200 gateway ok | ✅ `{"service":"gateway","status":"ok"}` |
| `GET :8000/health/services` | all ok | ✅ `downstream: {clientes: ok, reservas: ok, catalogo: ok}` |
| `GET :8000/api/v1/clientes` | `{"data":[]}` (empty table) | ✅ |
| `GET :8000/api/v1/reservas` | `{"data":[]}` | ✅ |
| `GET :8000/api/v1/catalogo/mesas` | `{"data":[]}` | ✅ |
| `GET :8000/api/v1/catalogo/platillos` | `{"data":[]}` | ✅ |
| `GET :8000/api/v1/clientes/1` | 404 (no data) | ✅ HTTP 404 |
| `GET /docs` on 5 components | 200 | ✅ 5/5 (gateway, 3 services, root app) |
| Stop catalogo → `GET :8000/api/v1/catalogo/mesas` | controlled 503 JSON | ✅ `{"detail":"Service 'catalogo' is unavailable","service":"catalogo"}` |
| Stop catalogo → `GET :8000/health/services` | degraded | ✅ `catalogo: unavailable`, overall `degraded` |

All processes were stopped afterwards; no listeners left on ports
8000-8003/8010.

## 3. Dependency and integrity checks

| Command | Result |
|---------|--------|
| `python -m pip check` | `No broken requirements found.` |
| `git check-ignore -v .env` | ignored by `.gitignore:13` |
| `git branch --show-current` | `Dev/Noe-Mejia` |
| `git status --short` | only expected files; **nothing staged or committed** |

## 4. Docker Compose verification (executed 2026-11-01)

Docker Desktop 29.9.2 (Compose v5.6.1, WSL 2) is now installed. The
compose file was executed for the first time:

| Step | Command | Result |
|------|---------|--------|
| 1 | `docker compose config --quiet` | ✅ exit 0 (validation OK, no output printed) |
| 2 | `docker compose up --build -d` | ✅ first attempt failed on a **host PATH issue only**: `docker-credential-desktop not found in %PATH%` (the Docker CLI was invoked from a directory not on PATH, so the registry credential helper could not be resolved). **No project/build defect.** Re-run with Docker's `resources/bin` prepended to `PATH` → images built and all 4 containers started. |
| 3 | `docker compose ps` | ✅ 4/4 **healthy**: `backend-gateway-1`, `backend-clientes-1`, `backend-reservas-1`, `backend-catalogo-1` |
| 4 | `GET :8000/health` | ✅ `{"service":"gateway","status":"ok"}` |
| 5 | `GET :8000/health/services` | ✅ `downstream: {clientes: ok, reservas: ok, catalogo: ok}` |
| 6 | `GET :8001/8002/8003/health` | ✅ `database: connected` ×3 |
| 7 | Gateway read-only routes | ✅ `{"data":[]}` ×4 (clientes, reservas, mesas, platillos); `clientes/1` and `reservas/NOT-EXIST` → 404 |
| 8 | Swagger | ✅ `/docs` 200 on gateway + 3 services; `/openapi.json` 200 |
| 9 | Service-to-service (F-01) | ✅ inside the `reservas` container: `http://catalogo:8003/health` → 200, dish endpoint → 404 (empty DB), `CATALOGO_SERVICE_URL` resolves to the compose service (value not printed) |
| 10 | Controlled failure (non-destructive) | ✅ `docker compose stop catalogo` → gateway route 503 JSON `{"detail":"Service 'catalogo' is unavailable","service":"catalogo"}`, aggregation `degraded`, other routes and gateway health unaffected; `docker compose start catalogo` → full recovery (`all ok`, route 200) |
| 11 | Logs inspection | ✅ grep of all container logs: **0** matches for traceback/credential/password/`DATABASE_URL=` (count only; no log lines printed) |

**Containers left running** as instructed after successful verification.

Notes:

- The host PATH workaround above is an environment detail of this
  machine, not a repository change (no config file was modified).

## 5. Test-data execution and F-01 live verification (2026-11-01, authorized)

After explicit team authorization, `database/test_data.sql` was reviewed
and executed (this was the **only** SQL write of the task):

| Pre-flight check | Result |
|------------------|--------|
| Statement types (comments stripped) | 7 `INSERT` + read-only `SELECT`s only — **0** destructive statements (`DROP/ALTER/TRUNCATE/UPDATE/DELETE/CREATE/GRANT`) |
| Duplicate prevention | Per-row `WHERE NOT EXISTS` on business keys / full reservation fingerprint; no `ON CONFLICT` |
| Foreign-key order | administradores → clientes → mesas → platillos → reservas → reserva_platillos |
| Target | Same configured connection used by all services; Neon backend confirmed (`neon.*` settings present), 8 approved tables found; pre-execution counts all 0 |
| Execution | Committed OK; **immediate re-run inserted 0 rows** (idempotency proven) |

Per-table counts — **all rows are newly inserted** (every table had 0
rows before execution; no pre-existing records existed):

| Table | Pre-existing | Newly inserted | Total |
|-------|--------------|----------------|-------|
| `administradores` | 0 | 1 | 1 |
| `clientes` | 0 | 3 | 3 |
| `mesas` | 0 | 4 | 4 |
| `platillos` | 0 | 5 | 5 |
| `reservas` | 0 | 2 | 2 |
| `reserva_platillos` | 0 | 3 | 3 |
| `historial_estados` | 0 | 2 (trigger-created) | 2 |
| `notificaciones` | 0 | 2 (trigger-created) | 2 |

Reservation/dish consistency was audited read-only: table assignments,
guest counts, timestamps and dish quantities all match the script's
intended values (the earlier "mesa 4/3" observation was only the `id_mesa`
foreign key vs. business key `numero_mesa`).

### F-01 enrichment verified live (through the Gateway)

| Check | Result |
|-------|--------|
| `GET :8000/api/v1/catalogo/platillos` | 200, **5 dishes** (test data) |
| `GET :8000/api/v1/reservas/PS-20261102-000001` | 200; `platillos` = `Pollo a la parrilla` (qty 1, price 150.0) — name resolved via catalogo HTTP, `historial` 1 row |
| `GET :8000/api/v1/reservas/PS-20261102-000002` | 200; `platillos` = `Filete de pescado a la plancha` (qty 2, 180.0) + `Baleada tradicional` (qty 2, 45.0) — all names resolved, `historial` 1 row |
| Consistency | Every name returned in reservations exists in catalogo's catalog; prices match menu snapshots; quantities match `reserva_platillos` rows |
| Error paths | Covered by unit tests (unreachable → 503, timeout → 504, no dishes → no catalogo call) and the gateway controlled-failure test (§4); no containers were stopped for this round |

## 6. Final verification (2026-11-01, after all authorized changes)

| Check | Result |
|-------|--------|
| `pytest -q` (unit) | **39 passed, 6 skipped** |
| `RUN_DB_TESTS=1 pytest -m integration` (read-only) | **6 passed** |
| `pip check` | No broken requirements found |
| Docker `compose ps` | 4/4 **healthy** (gateway, clientes, reservas, catalogo) |
| Gateway `/health` + `/health/services` | ok; downstream `all ok` |
| Service health ×3 | `database: connected` |
| Gateway routes | 4 read-only routes 200 with data; detail 404 correct |
| Root `app/` | `/`, `/health`, `/docs` all 200 (in-process, read-only) |
| Secrets scan (tracked diff + docs) | 0 matches (counts only) |
| `.env` | ignored via `.gitignore:13`, untracked, untouched |
| Git | nothing staged; branch `Dev/Noe-Mejia` unchanged |
