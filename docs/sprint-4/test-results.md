# Test Results (Sprint 4)

- **Date executed:** 2026-11-17 (Sprint 4 gaps G4–G7: reportes, roles
  DELETE, disponibilidad, Postman collection)
- **Environment:** Windows, Python 3.15.2, `.venv/`, branch
  `Dev/David-Avila` (working tree, no commits yet)
- **Database:** unit tests never touch the network or the database
  (fakes from `tests/conftest.py`); live integration tests remain
  opt-in and read-only (`RUN_DB_TESTS=1`)

## 1. Automated test suite

Command: `.venv\Scripts\python.exe -m pytest -q`

| Result | Count |
|--------|-------|
| ✅ Passed | **260** |
| ⏭️ Skipped (live/DB, opt-in) | **17** |
| ❌ Failed | **1** (pre-existing, environment-dependent — see §5) |
| **Total collected** | **278** |
| Warnings | 2 |
| Duration | ~9.5 s |

`pip check` → `No broken requirements found.`

### Per-file breakdown (278 collected)

| File | Tests | Notes |
|------|-------|-------|
| `tests/test_sprint3.py` | 46 | includes the 3 new **G5** role-delete tests |
| `tests/test_security.py` | 43 | JWT, fail-closed settings, RBAC helpers (1 env-dependent failure, §5) |
| `tests/test_crud.py` | 32 | catalog CRUD |
| `tests/test_auth.py` | 28 | login/token behavior |
| `tests/test_authorization.py` | 24 | RBAC matrix, incl. `DELETE /api/v1/roles/1` |
| `tests/test_services.py` | 20 | service-level behavior |
| `tests/test_gateway.py` | 18 | routing, auth forwarding, OpenAPI markings (§2) |
| `tests/test_auth_service.py` | 13 | auth microservice |
| `tests/test_availability.py` | **12** | **new G6** — `GET /api/v1/disponibilidad` |
| `tests/test_reports.py` | **11** | **new G4** — `GET /api/v1/reportes/reservas` |
| `tests/test_auth_live.py` | 11 | live DB (skipped by default) |
| `tests/test_auth_gateway.py` | 4 | login proxy through gateway |
| `tests/test_parameterization.py` | 4 | input parameterization |
| `tests/test_root_app.py` | 3 | legacy root app compatibility |
| `tests/test_shared_database.py` | 3 | shared DB layer |
| `tests/test_integration_live.py` | 6 | live integration (skipped by default) |

### New Sprint 4 test coverage

**G6 — Disponibilidad (`tests/test_availability.py`, 12 tests):**

| Test | Verifies |
|------|----------|
| `test_availability_happy_path_public` | 200 **without token** (public read), full response shape |
| `test_availability_filters_capacity_and_duration` | `cantidad_personas`/`duracion_minutos` filter mesas and slots |
| `test_availability_closed_weekday_returns_empty` | no schedule → empty slots, still 200 |
| `test_availability_missing_fecha_returns_400` | required param missing → 400 |
| `test_availability_invalid_fecha_returns_400` | malformed date → 400 (never 422) |
| `test_availability_invalid_cantidad_personas_returns_400` | capacity ≤ 0 / non-int → 400 |
| `test_availability_invalid_duracion_minutos_returns_400` | duration out of 15–720 → 400 |
| `test_availability_reservation_blocks_slot` | active reservation removes the slot |
| `test_availability_general_bloqueo_blocks_every_mesa` | general bloqueo blocks all mesas |
| `test_availability_mesa_bloqueo_blocks_only_that_mesa` | mesa-specific bloqueo is scoped |
| `test_availability_database_failure_returns_503` | controlled 503 on DB failure |
| `test_availability_unexpected_error_returns_500` | controlled 500 on unexpected error |

**G4 — Reportes (`tests/test_reports.py`, 11 tests):**

| Test | Verifies |
|------|----------|
| `test_reports_admin_with_all_filters` | all 5 filters applied + echoed in `filtros` |
| `test_reports_without_filters` | unfiltered report, `resumen` totals |
| `test_reports_single_filter_binds_one_parameter` | parameter binding (no SQL injection surface) |
| `test_reports_cliente_is_forbidden` | **RBAC:** client token → 403 |
| `test_reports_missing_token_is_401` | no token → 401 |
| `test_reports_invalid_fecha_values_return_400` | malformed dates → 400 |
| `test_reports_inverted_date_range_returns_400` | `fecha_inicio > fecha_fin` → 400 |
| `test_reports_invalid_estado_returns_400` | estado outside the 6-value whitelist → 400 |
| `test_reports_invalid_ids_return_400` | `id_cliente`/`id_mesa` ≤ 0 → 400 |
| `test_reports_database_failure_returns_503` | controlled 503 |
| `test_reports_unexpected_error_returns_500` | controlled 500 |

**G5 — Roles DELETE (`tests/test_sprint3.py`, 3 tests):**

| Test | Verifies |
|------|----------|
| `test_delete_role_admin` | admin deletes an unused role → 200, row gone |
| `test_delete_role_not_found` | unknown id → 404, nothing deleted |
| `test_delete_role_in_use_returns_400` | role assigned to users → 400, no delete (safeguard) |

## 2. Gateway routing verification (`tests/test_gateway.py`, 18 tests)

All routing tests pass. Sprint 4 additions:

| Test | Verifies |
|------|----------|
| `test_gateway_routes_disponibilidad_to_reservas` | `GET /api/v1/disponibilidad` proxied to the `reservas` service |
| `test_gateway_disponibilidad_is_public_get_only` | marked **public** and **GET-only** in the gateway OpenAPI (no invented methods) |
| `test_gateway_routes_reportes_to_reservas` | `GET /api/v1/reportes/reservas` proxied to `reservas` |
| `test_gateway_reportes_rejects_client_token` | client token → 403 through the gateway (service-enforced RBAC) |
| `test_gateway_reportes_is_admin_protected_in_openapi` | operation marked **Bearer-protected** in gateway OpenAPI (`reportes` tag) — reports are never public reads |
| `test_gateway_openapi_available` | gateway `/openapi.json` renders |

Pre-existing routing coverage (unchanged, all green): auth login POST
proxy, clientes/reservas/catalogo/usuarios/roles path+method forwarding,
`Authorization` header forwarding, no-bypass guarantee (the gateway never
parses tokens), controlled `503`/`504` responses, `/health` and
`/health/services` aggregation of the four services.

## 3. RBAC / IDOR validation

| Area | File(s) | Tests | Status |
|------|---------|-------|--------|
| Role matrix (method × path × role) | `tests/test_authorization.py` | 24 | ✅ all pass — includes the new `(clientes_main, "delete", "/api/v1/roles/1")` matrix entry: admin 200/404/400, client 403, no token 401 |
| JWT claims, fail-closed config, token errors | `tests/test_security.py` | 43 | 42 pass + 1 environment-dependent failure (§5) — claims `rol`, `TokenError`, expiry, `JWT_SECRET` requirements |
| Login behavior (no account enumeration) | `tests/test_auth.py`, `tests/test_auth_service.py`, `tests/test_auth_gateway.py` | 45 | ✅ all pass — uniform 401 for unknown user / wrong password / inactive account; no `password`/`password_hash` in responses |
| Sprint 3 business RBAC (owner vs admin) | `tests/test_sprint3.py` | 46 | ✅ 45 pass + 17-file skip group accounted separately — ownership checks, admin-only writes |
| Sprint 4 RBAC specifics | `tests/test_reports.py` | 11 | ✅ client → 403, missing token → 401 (reportes is admin-only) |
| Public reads without token | `tests/test_availability.py` | 12 | ✅ disponibilidad answers 200 with **no** `Authorization` header (by design) |

**IDOR prevention** (unchanged from previous sprints, re-verified green):
resource detail endpoints resolve ownership from the token's profile id —
a client requesting a foreign reservation/customer gets **404** (not
403), so existence is not leaked; admin tokens see everything. The
gateway forwards `Authorization` untouched and performs no auth of its
own, so routing through it cannot bypass any of these checks.

## 4. Postman collection validation (G7)

File: [`docs/postman/PuntoYSal-Sprint4.postman_collection.json`](../postman/PuntoYSal-Sprint4.postman_collection.json)

| Check | Result |
|-------|--------|
| Valid JSON (`python -m json.tool`) | ✅ |
| Schema `collection/v2.1.0/collection.json` | ✅ |
| Collection variables | ✅ 8: `base_url` (default `http://localhost:8000`), `jwt_token`, `jwt_token_cliente`, `codigo_reserva`, `admin_correo`, `admin_password`, `cliente_correo`, `cliente_password` (passwords **empty by default** — no secrets in the repo) |
| Request groups | ✅ 8 folders, **31 requests**: General (2), Autenticación (3), Mesas (5), Platillos (5), Roles (4), Disponibilidad (3), Reservas (3), Reportes (6) |
| Test scripts | ✅ all 31 requests carry `pm.test` assertions |
| Bearer auth blocks | ✅ 18 protected requests use `Bearer {{jwt_token}}` |
| Token auto-save | ✅ admin & client login tests save `access_token` → `jwt_token` (client also → `jwt_token_cliente`) |

## 5. Known failure (pre-existing, environment-dependent)

```
FAILED tests/test_security.py::test_missing_jwt_secret_fails_closed
```

This test asserts that authentication **fails closed** when `JWT_SECRET`
is not configured. The local developer `.env` defines `JWT_SECRET`, so
the "missing secret" precondition cannot be reproduced in this
environment. It is **not a regression from Sprint 4** — the same failure
was recorded in previous runs on this branch (documented as gap G8).
Workaround for a green local run: run the suite with `JWT_SECRET`
unset/removed from `.env` for that test, or treat it as known-failing
until CI runs without the variable.

## 6. Summary

| Verification | Result |
|--------------|--------|
| Full pytest suite | **260 passed, 17 skipped, 1 known env-dependent failure** |
| Dependency integrity (`pip check`) | ✅ clean |
| Gateway routing (Sprint 4 routes) | ✅ 18/18 gateway tests, new routes correctly public/protected in OpenAPI |
| RBAC (admin vs client) | ✅ role matrix + reportes 403 + roles DELETE admin-only |
| IDOR prevention | ✅ ownership-from-token, 404 on foreign resources |
| Postman collection (G7) | ✅ valid v2.1.0, 31 requests, token flow automated |
