# Test Results (Sprint 2)

- **Date executed:** 2026-11-03 (Phases 1–2 of the security layer)
- **Environment:** Windows, Python 3.15.2, `venv/`, branch `Dev/David-Avila`
- **Database:** unit tests never touch the network or the database
  (fakes from `tests/conftest.py`); live integration tests remain
  opt-in and read-only (`RUN_DB_TESTS=1`)

> **Integration note (2026-11-09):** this document is the **historical
> record of the Phase 1–2 run on `Dev/David-Avila`** and is kept
> unchanged as evidence of that execution. After the integration round
> on `Dev/Noe-Mejia` the suites were re-adapted to the canonical
> contract: `tests/test_security.py` now runs **34 tests** against
> `shared/auth.py` (claims `rol`, `TokenError`, `JWT_EXPIRE_MINUTES`,
> fail-closed settings), dependencies are `PyJWT==2.15.1` /
> `bcrypt==5.0.0`, and the test-admin password was removed from the
> seed script comment (env-only). Current post-integration numbers are
> in the root [README](../../README.md).

## 1. Automated test suite

| Command | Result |
|---------|--------|
| `venv\Scripts\python -m pytest -q` (with `DATABASE_URL` set) | **73 passed, 6 skipped** (skips = live integration tests, disabled by default) |
| Full run with duration | `73 passed, 6 skipped, 1 warning in 3.61s` |
| `RUN_DB_TESTS=1 … pytest -q -m integration` | 6 read-only live tests (unchanged from Sprint 1; not part of this run) |

**Breakdown: 73 = 60 prior baseline + 13 new auth/gateway tests**

| File | Tests | Status |
|------|-------|--------|
| `tests/test_gateway.py` | 9 | ✅ baseline unchanged |
| `tests/test_integration_live.py` | 6 | ⏭️ skipped by default (opt-in, read-only) |
| `tests/test_parameterization.py` | 4 | ✅ baseline unchanged |
| `tests/test_root_app.py` | 3 | ✅ baseline unchanged |
| `tests/test_security.py` | 21 | ✅ Phase 1 (shared security layer) |
| `tests/test_services.py` | 20 | ✅ baseline unchanged |
| `tests/test_shared_database.py` | 3 | ✅ baseline unchanged |
| **`tests/test_auth_service.py`** | **9** | ✅ **new — Phase 2** |
| **`tests/test_auth_gateway.py`** | **4** | ✅ **new — Phase 2** |

Coverage of the new tests:

- **Password hashing** (`test_security.py`): bcrypt hash format,
  per-call salt, empty/>72-byte input rejected, verify accepts the
  correct password and rejects wrong/empty/malformed/`None` hashes
  without raising.
- **JWT lifecycle** (`test_security.py`): claims encoded (`sub`,
  `role`, `iat`, `exp`) without mutating the caller's dict; default
  lifetime = `JWT_EXPIRATION_MINUTES × 60`; custom `expires_delta`
  honored; expired token → `ExpiredSignatureError`; garbage token,
  foreign-secret signature and tampered payload → `PyJWTError`.
- **RBAC dependency** (`test_security.py`): correct role → payload;
  missing/invalid/expired token → **401** (with `WWW-Authenticate`);
  wrong role or absent `role` claim → **403**.
- **Settings fallbacks**: `HS256` / 60 min / non-empty secret with no
  `.env` present — the Phase 1 suite was additionally run **without
  `DATABASE_URL`** and passed (standalone guarantee).
- **Login contract** (`test_auth_service.py`): success → 200 with
  decodable JWT (`sub='1'`, `role='administrador'`, `correo`), no
  password/hash in the response, correo sent as a bound SQL parameter;
  wrong password / unknown correo / `activo=false` → identical
  **401 `{"detail":"Invalid credentials"}`** (no enumeration); DB down
  → **503**; unexpected error → **500** without leaking `Traceback`;
  missing fields → **422** before any DB access; `/health` 200/503.
- **Gateway POST proxy** (`test_auth_gateway.py`): in-process
  gateway→auth login round-trip returns a verifiable JWT; downstream
  401 passes through untouched; unreachable auth → controlled JSON 503
  (asserts no `localhost`/`Traceback` leak); OpenAPI exposes
  `/api/v1/auth/login` with **`post` only**.
- **Sprint 1 regression**: the full 60-test baseline (gateway routing,
  health aggregation, error contracts, parameterization, root app,
  shared DB) passed in the same execution — no contract broken.

## 2. Dependency and integrity checks

| Command | Result |
|---------|--------|
| `pip install pyjwt==2.10.1 bcrypt==4.2.1` | ✅ installed; `PyJWT-2.10.1-py3-none-any.whl` (pure Python) + `bcrypt-4.2.1-cp39-abi3-win_amd64.whl` (abi3 → runs on Python 3.12 images and the 3.15 venv) |
| `python -c "import jwt, bcrypt; …"` | ✅ `pyjwt 2.10.1`; bcrypt hash/verify round-trip OK |
| `python -m pip check` | ✅ `No broken requirements found.` |
| `git status --short` | ✅ only expected files (2 modified, 10 new/untracked); **nothing staged or committed** |
| `git branch --show-current` | ✅ `Dev/David-Avila` |

Note: `passlib[bcrypt]==1.7.4` was deliberately **not** installed —
unmaintained since 2016 and incompatible with current bcrypt/Python;
`bcrypt==4.2.1` is the approved alternative (recorded in
`requirements.txt` and [architecture.md](architecture.md) decision 2).

## 3. Docker Compose verification (executed 2026-11-03)

| Step | Command | Result |
|------|---------|--------|
| 1 | `docker compose config --quiet` (with `DATABASE_URL`/`JWT_SECRET` set) | ✅ exit 0 — YAML + interpolation valid, including the new `auth` block |
| 2 | `docker compose up --build -d` (local `.env` with `DATABASE_URL` + `JWT_SECRET`) | ✅ all images built (5 services; `services/auth/Dockerfile` copies `shared/`) |
| 3 | `docker compose ps` | ✅ **5/5 healthy**: `gateway`, `clientes`, `reservas`, `catalogo`, **`auth`** (healthchecks hit each `/health`; gateway additionally waits for `service_healthy` on all four upstreams) |
| 4 | Gateway login route | ✅ `POST :8000/api/v1/auth/login` proxied to `auth:8004` (route present in gateway OpenAPI — asserted by `test_auth_gateway.py`) |
| 5 | JWT env propagation | ✅ `JWT_SECRET` (fail-fast), `JWT_ALGORITHM`, `JWT_EXPIRATION_MINUTES` present on all 5 services; gateway receives `AUTH_SERVICE_URL=http://auth:8004` |

Container-level verification follows the same procedure as Sprint 1
([Sprint 1 test-results §4](../sprint-1/test-results.md)); no
containers were left in a modified state and no schema objects were
touched by the run.

## 4. Final verification summary (2026-11-03)

| Check | Result |
|-------|--------|
| `pytest -q` (unit) | **73 passed, 6 skipped** |
| `pip check` | No broken requirements found |
| `docker compose config --quiet` | exit 0 |
| Docker `compose ps` | **5/5 healthy** (incl. auth) |
| Schema execution | `sprint2_auth_schema.sql` + `sprint2_auth_seed.sql` executed once, idempotent guards — see [database-verification.md](database-verification.md) |
| Secrets scan (new docs + diff) | 0 credentials, no `.env` contents, no real connection strings (the test password was in the seed script header at that time; **removed in the integration round** — env-only now) |
| `.env` protection | ignored via `.gitignore`, untracked, untouched |
| Git | nothing staged; branch `Dev/David-Avila` unchanged; 0 commits created |
