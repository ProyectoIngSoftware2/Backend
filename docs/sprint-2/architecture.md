# Architecture and Routing (Sprint 2 — Security Layer, Option B)

## Overview

Sprint 2 adds a fourth microservice — **auth** — plus a shared security
module, without changing the Sprint 1 topology: the gateway is still the
single public entry point, services never import each other's code, and
gateway↔service communication remains real HTTP. The auth service is the
only component that reads credentials; it validates them against the
unified `usuarios` table and issues JWTs signed with the shared secret.

```
                    ┌──────────────────────────────┐
                    │   API Gateway  (port 8000)    │  uvicorn gateway.app.main:app
                    │   public entry point          │
                    │   POST /api/v1/auth/login ────────┐
                    └────────────┬─────────────────┘   │ HTTP proxy
         HTTP proxy ────────────┼───────────────┐      │
        ┌────────────┬──────────┼──────────┬────┴─────┐│
        ▼            ▼          ▼          ▼          ▼│
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│clientes :8001│ │reservas :8002│ │catalogo :8003│ │  auth :8004  │
│ table:       │ │ tables:      │ │ tables:      │ │ table:       │
│  clientes    │ │  reservas,   │ │  mesas,      │ │  usuarios    │
│              │ │  reserva_    │ │  platillos   │ │ (login → JWT)│
│              │ │  platillos,  │ │              │ │              │
│              │ │  historial,  │ │              │ │              │
│              │ │  notificac.  │ │              │ │              │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       └────────────────┴───────┬────────┴────────────────┘
                                ▼
              ┌─────────────────────────────────────┐
              │ shared/database.py   psycopg 3       │  DATABASE_URL
              │ shared/auth.py   bcrypt + PyJWT + RBAC│  JWT_SECRET / ALG / TTL
              └─────────────────┬───────────────────┘
                                ▼
              ┌─────────────────────────────────────┐
              │ NeonDB PostgreSQL                    │  external, port 5432
              │ 9 tables (8 approved + usuarios)     │
              └─────────────────────────────────────┘
```

> **Token flow (Option B):** the browser/client calls
> `POST :8000/api/v1/auth/login` → gateway proxies to `auth:8004` →
> auth queries `usuarios`, verifies with bcrypt, returns a signed JWT →
> subsequent requests carry `Authorization: Bearer <jwt>`, which the
> gateway **forwards untouched** (only hop-by-hop headers are stripped).
> The gateway never parses or stores tokens; every service validates
> them through the canonical `shared/auth.py` (`get_current_user` /
> `require_roles`) and enforces RBAC + ownership on its own endpoints.

## Repository layout (delta vs Sprint 1)

```
Backend/
├── shared/
│   ├── database.py            # unchanged (Sprint 1)
│   └── auth.py                # canonical auth: bcrypt + JWT + RBAC deps (fail-closed env)
├── services/
│   ├── clientes/              # Sprint 1 CRUD + public registration (no login route)
│   ├── reservas/              # unchanged
│   ├── catalogo/              # unchanged
│   └── auth/                  # NEW: Dockerfile + app/{__init__,main}.py :8004
├── gateway/app/main.py        # +AUTH_SERVICE_URL, +POST /api/v1/auth/login
├── database/
│   ├── schema_verification.sql / test_data.sql   # Sprint 1 (unchanged)
│   ├── sprint2_auth_schema.sql                   # NEW (executed 2026-11-03)
│   └── sprint2_auth_seed.sql                     # NEW (executed 2026-11-03)
├── tests/
│   ├── test_security.py       # (34)  shared/auth unit tests
│   ├── test_auth_service.py   # (9)   login contract
│   └── test_auth_gateway.py   # (4)   gateway ↔ auth
├── docker-compose.yml         # 4 → 5 services; JWT env; auth healthcheck
├── requirements.txt           # +PyJWT==2.15.1, +bcrypt==5.0.0
└── .env.example               # +AUTH_SERVICE_URL / JWT_SECRET / JWT_ALGORITHM / JWT_EXPIRE_MINUTES
```

## Decisions

1. **Option B — unified `usuarios` table.** Credentials live in one
   table with `rol IN ('administrador','cliente')` and 1:1 nullable
   `id_usuario` FKs from `administradores` and `clientes` (FK direction
   points *to* `usuarios`, avoiding a circular dependency). Rationale:
   one login path for both roles, profile tables stay free of auth
   concerns, and a `cliente` can gain a login later without schema
   changes. The legacy `administradores.password_hash` is kept for
   compatibility but is **never read** by the auth path.
2. **bcrypt instead of passlib.** `passlib[bcrypt]==1.7.4` was rejected
   (unmaintained since 2016, incompatible with newer bcrypt/Python);
   `bcrypt==5.0.0` ships an abi3 wheel, so one build covers the
   Python 3.12 images and the local 3.15 venv (and refuses >72-byte
   inputs outright instead of truncating). **Cost 12**
   (`bcrypt.gensalt()` default) — the seeded hash is `$2b$12$…`.
3. **PyJWT, HS256, 60-minute expiry.** Claims: `sub` (id_usuario),
   `rol` (database column name), `correo`, `iat`, `exp`, plus the
   profile id (`id_cliente` or `id_administrador`). `JWT_SECRET` is
   **fail-closed**: required, ≥32 characters, no development fallback —
   a missing/short secret raises a clear configuration error at the
   first authentication operation (Compose uses `${JWT_SECRET:?…}`).
4. **Auth is a separate microservice** (`services/auth/`, port 8004)
   with its own Dockerfile copying `shared/` — same layout, sys.path
   bootstrap and error contract (422/401/503/500) as the other
   services. It owns exactly one business route:
   `POST /api/v1/auth/login`, plus `/health`. It is the **only** login
   implementation in the system (the duplicate route in
   `services/clientes` was removed).
5. **Uniform 401 — no account enumeration.** Unknown correo, wrong
   password and `activo = false` all return
   `{"detail": "Invalid credentials"}` with `WWW-Authenticate: Bearer`;
   the response never contains hashes or stack traces. Database-class
   failures map to 503 and unexpected failures to 500, identical to
   the Sprint 1 convention.
6. **Gateway proxies login; it does not authenticate.** A
   method-specific `@app.post("/api/v1/auth/login")` route reuses the
   existing `_proxy_request` helper (bodies, query and headers
   forwarded; internal URLs never exposed). Business routes
   (clientes/reservas/catalogo) proxy **all five methods**
   (GET/POST/PUT/PATCH/DELETE), collection + nested paths, with one
   uniquely-named route per (path, method) so Swagger operation ids
   stay unique.
7. **`/health/services` aggregates four services.** `auth` joins
   `clientes`, `reservas` and `catalogo` in the aggregate (Compose
   healthchecks report all four), and the auth service is a
   `depends_on` of the gateway.
8. **RBAC is enforced through `shared/auth.py`.** `get_current_user`
   (401 for missing/invalid/expired/unsigned tokens) and
   `require_roles` (403 for a valid token with the wrong role) are
   wired into every protected endpoint of the business services;
   ownership checks filter queries by the authenticated profile id
   (anti-IDOR, 404 on foreign resources). There is exactly one shared
   security module — the Phase-1 `shared/security.py` was removed.

## Ports and URLs

| Component | Port | Health | Swagger | Notes |
|-----------|------|--------|---------|-------|
| gateway | 8000 | `/health`, `/health/services` | `/docs` | public entry point |
| clientes | 8001 | `/health` | `/docs` | published for testing only |
| reservas | 8002 | `/health` | `/docs` | published for testing only |
| catalogo | 8003 | `/health` | `/docs` | published for testing only |
| **auth** | **8004** | `/health` | `/docs` | **new — login issues JWTs** |
| root app | 8010 | `/health` | `/docs` | legacy, unchanged |

## Gateway routing map (Sprint 2)

| Gateway route | Method | Downstream |
|---|---|---|
| `/api/v1/clientes` and `/api/v1/clientes/**` | GET, POST, PUT, PATCH, DELETE | `CLIENTES_SERVICE_URL` |
| `/api/v1/reservas` and `/api/v1/reservas/**` | GET, POST, PUT, PATCH, DELETE | `RESERVAS_SERVICE_URL` |
| `/api/v1/catalogo` and `/api/v1/catalogo/**` | GET, POST, PUT, PATCH, DELETE | `CATALOGO_SERVICE_URL` |
| **`/api/v1/auth/login`** | **POST** | **`AUTH_SERVICE_URL`** (any other auth path → 404) |
| `/health` | GET | gateway itself |
| `/health/services` | GET | aggregated `/health` of the four services |

Internal URLs come from environment variables (`CLIENTES_SERVICE_URL`,
`RESERVAS_SERVICE_URL`, `CATALOGO_SERVICE_URL`, **`AUTH_SERVICE_URL`**);
Docker Compose sets them to the Compose service names
(`http://clientes:8001`, …, `http://auth:8004`). Local defaults are
`http://localhost:8001-8004`.

### JWT environment variables

| Variable | Default | Where it matters |
|---|---|---|
| `JWT_SECRET` | **none — fail-closed** (required, ≥32 chars; Compose: `${JWT_SECRET:?…}` on all 5 services) | auth service signs; every service verifies via `shared/auth.py` |
| `JWT_ALGORITHM` | `HS256` (HS384/HS512 allowed; anything else rejected at startup) | `shared/auth.py` |
| `JWT_EXPIRE_MINUTES` | `60` | token lifetime (`exp - iat`), auth service + validators |

`.env.example` documents all four (plus `AUTH_SERVICE_URL`); real
values live only in the gitignored `.env` (never committed, never
logged).

## Integration status

The Sprint 2 work of `development` and `Dev/David-Avila` is integrated
locally into branch `Dev/Noe-Mejia` as a prepared (uncommitted) merge of
`origin/development` (`2199f3b`): all conflicts were resolved, the
canonical contract described above was applied across both branches'
code, and **no local commits were created** — the merge awaits explicit
approval before any commit or remote action. Branch policy
(`development` vs the guideline's `develop`) is recorded in the
[Sprint 1 architecture](../sprint-1/architecture.md) and unchanged.
