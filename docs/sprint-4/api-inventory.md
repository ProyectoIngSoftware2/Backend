# API Inventory — Sprint 4

All business APIs are consumed **only** through the API Gateway
(`http://localhost:8000`); microservice ports (8001–8004) are internal and
never exposed. The gateway forwards requests (including the
`Authorization` header) and performs **no authentication of its own** —
each protected microservice validates the JWT and its roles independently,
so routing through the gateway can never bypass authorization.

## The 5 accumulated APIs (routed through the Gateway)

| # | API | Microservice(s) | Base path(s) | Operations | Access | Status |
|---|-----|-----------------|--------------|------------|--------|--------|
| 1 | Auth & Users | `auth`, `clientes` | `/api/v1/auth/login`, `/api/v1/usuarios{/{id}}`, `/api/v1/roles{/{id}}` | POST login · GET/POST/PATCH/PUT/DELETE usuarios · GET/POST/PATCH/PUT/**DELETE** roles | login/roles read: public · usuarios/roles writes: admin | Implemented (**Sprint 4:** `DELETE /api/v1/roles/{id}`) |
| 2 | Clientes | `clientes` | `/api/v1/clientes{/{id}}` | GET, POST, PATCH, PUT, DELETE | GET/DELETE: admin · POST: public (self-registration) · GET/PUT/PATCH: admin or owner | Implemented |
| 3 | Mesas (catalog) | `catalogo` | `/api/v1/catalogo/mesas{/{id}}` | GET, POST, PATCH, PUT, DELETE | GET: public · writes: admin | Implemented |
| 4 | Platillos (catalog) | `catalogo` | `/api/v1/catalogo/platillos{/{id}}` | GET, POST, PATCH, PUT, DELETE | GET: public · writes: admin | Implemented |
| 5 | Reservas & Horarios | `reservas`, `catalogo` | `/api/v1/reservas{/{codigo}}`, `/api/v1/reservas/{codigo}/platillos{/{detalle_id}}`, `/api/v1/catalogo/horarios{/{id}}`, `/api/v1/catalogo/bloqueos{/{id}}` | GET, POST, PATCH, PUT, DELETE | GET list: admin · POST: authenticated · detail: admin or owner · horarios/bloqueos: public read / admin write | Implemented (DB triggers enforce business rules) |

## New Sprint 4 endpoints (3)

| Resource | Microservice | Base path | Operations | Access | Validation | Gap | Status |
|----------|-------------|-----------|------------|--------|------------|-----|--------|
| Disponibilidad | `reservas` | `/api/v1/disponibilidad` | GET | **public** (no token) | `fecha` required `YYYY-MM-DD` (400), `cantidad_personas` ≥ 1, `duracion_minutos` 15–720; any invalid value → 400 | G6 | Implemented |
| Reportes | `reservas` | `/api/v1/reportes/reservas` | GET | **admin only** (Bearer) | `fecha_inicio`/`fecha_fin` (`fecha_inicio` ≤ `fecha_fin`), `estado` whitelist of 6 values, `id_cliente`/`id_mesa` > 0; invalid → 400; client token → 403; no token → 401 | G4 | Implemented |
| Roles (delete) | `clientes` | `/api/v1/roles/{id_rol}` | DELETE | **admin only** (Bearer) | 404 unknown id · 400 if the role is still assigned to users · 403 for non-admin | G5 | Implemented |

### Endpoint contracts (Sprint 4)

**`GET /api/v1/disponibilidad`** — free-slot lookup for a date:

| Query param | Type | Rules | Default |
|-------------|------|-------|---------|
| `fecha` | `YYYY-MM-DD` | required; invalid → **400** | — |
| `cantidad_personas` | int | ≥ 1; invalid → 400 | none (all mesas) |
| `duracion_minutos` | int | 15–720; invalid → 400 | 60 |

Response `data`: `fecha`, `horarios` (day's schedule), `mesas` (candidate
tables by capacity), `slots` (per-slot availability computed from active
reservations **and** bloqueos), `slots_disponibles`. General bloqueos
block every mesa; mesa-specific bloqueos block only that mesa.

**`GET /api/v1/reportes/reservas`** — filtered reservation report:

| Query param | Type | Rules |
|-------------|------|-------|
| `fecha_inicio`, `fecha_fin` | `YYYY-MM-DD` | range must not be inverted → else 400 |
| `estado` | enum | one of `pendiente`, `confirmada`, `en_curso`, `completada`, `cancelada`, `no_asistio` → else 400 |
| `id_cliente`, `id_mesa` | int | > 0 → else 400 |

Response `data`: `filtros` (echo of normalized filters), `resumen`
(`total_reservas` + `por_estado` counts via `GROUP BY estado`), `reservas`
(rows). SQL uses static WHERE fragments and `%s` parameters only (no
string concatenation of user input).

**`DELETE /api/v1/roles/{id_rol}`** — physical delete with safeguards:
200 on success (nothing deleted for system roles), **404** unknown id,
**400** if users still reference the role (message: reassign users
first), **403** non-admin token, **401** missing/invalid token.

## Gateway routing map (v1) — Sprint 4 additions

| Gateway route | Forwards to | Methods | Access (Sprint 4) |
|---------------|-------------|---------|-------------------|
| `/api/v1/disponibilidad` | `reservas` service | **GET only** | public (marked public in gateway OpenAPI) |
| `/api/v1/reportes[/{path}]` | `reservas` service | **GET only** | **Bearer-protected** in gateway OpenAPI (`reportes` tag) |
| `/api/v1/roles[/{path}]` | `clientes` service | all proxied methods | reads public / writes admin (service-enforced); now includes DELETE |

Registered as `route_disponibilidad` and `route_reportes` via
`_register_proxy_routes` (`gateway/app/main.py`); the gateway registers
**only the methods the downstream service exposes** — it never invents
routes. All previous routes (auth login, clientes, reservas, catalogo,
usuarios, roles) are unchanged.

## Auth operation (not a business CRUD resource)

| Resource | Microservice | Base path | Operations | Status |
|----------|-------------|-----------|------------|--------|
| Auth (login) | `auth` | `/api/v1/auth/login` | POST | Implemented (single login implementation; Sprint 2) |

## Missing resources (Sprint 5+)

| Resource | Microservice | Base path | Status |
|----------|-------------|-----------|--------|
| Notificaciones | notificaciones | `/api/v1/notificaciones{/{id}}` | Not implemented |

## Cumulative count

- After Sprint 1: 4 business CRUD resources + 1 auth operation
- After Sprint 3: 7 business CRUD resources + 1 auth operation
- After Sprint 4: **9 business resources + 1 auth operation**
  (adds Disponibilidad and Reportes — read-only resources)
- Sprint 4 endpoints total: 3 new (`GET /api/v1/disponibilidad`,
  `GET /api/v1/reportes/reservas`, `DELETE /api/v1/roles/{id}`)
- Note: the lineamientos mention "5 APIs acumuladas" for Sprint 4; this
  inventory groups them as the 5 API families in the table above (Auth &
  Users, Clientes, Mesas, Platillos, Reservas & Horarios), with 9
  concrete business resources + 1 auth operation routed through the
  Gateway. The counting ambiguity noted in Sprint 3
  ([../sprint-3/api-inventory.md](../sprint-3/api-inventory.md)) still
  requires instructor confirmation.
