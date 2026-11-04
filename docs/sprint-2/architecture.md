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
              │ shared/security.py   bcrypt + PyJWT  │  JWT_SECRET / ALG / TTL
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
> The gateway never parses or stores tokens; services validate them via
> `shared/security.py` when RBAC enforcement is wired (pending).

## Repository layout (delta vs Sprint 1)

```
Backend/
├── shared/
│   ├── database.py            # unchanged (Sprint 1)
│   └── security.py            # NEW: bcrypt + JWT + require_role (env fallbacks)
├── services/
│   ├── clientes/              # unchanged
│   ├── reservas/              # unchanged
│   ├── catalogo/              # unchanged
│   └── auth/                  # NEW: Dockerfile + app/{__init__,main}.py :8004
├── gateway/app/main.py        # +AUTH_SERVICE_URL, +POST /api/v1/auth/login
├── database/
│   ├── schema_verification.sql / test_data.sql   # Sprint 1 (unchanged)
│   ├── sprint2_auth_schema.sql                   # NEW (executed 2026-11-03)
│   └── sprint2_auth_seed.sql                     # NEW (executed 2026-11-03)
├── tests/
│   ├── test_security.py       # NEW (21)  Phase 1
│   ├── test_auth_service.py   # NEW (9)   Phase 2
│   └── test_auth_gateway.py   # NEW (4)   Phase 2
├── docker-compose.yml         # 4 → 5 services; JWT env; auth healthcheck
├── requirements.txt           # +pyjwt==2.10.1, +bcrypt==4.2.1
└── .env.example               # +JWT_SECRET / JWT_ALGORITHM / JWT_EXPIRATION_MINUTES
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
   `bcrypt==4.2.1` ships an abi3 wheel, so one build covers the
   Python 3.12 images and the local 3.15 venv. **Cost 12**
   (`bcrypt.gensalt()` default) — the seeded hash is `$2b$12$…`.
3. **PyJWT, HS256, 60-minute expiry.** Claims: `sub` (id_usuario),
   `role`, `correo`, `iat`, `exp`. `JWT_SECRET` is read from env →
   repo-root `.env` → insecure dev fallback **with a logged warning**,
   so unit tests never require configuration while deployments fail
   fast (Compose uses `${JWT_SECRET:?…}`).
4. **Auth is a separate microservice** (`services/auth/`, port 8004)
   with its own Dockerfile copying `shared/` — same layout, sys.path
   bootstrap and error contract (422/401/503/500) as the other
   services. It owns exactly one business route:
   `POST /api/v1/auth/login`, plus `/health`.
5. **Uniform 401 — no account enumeration.** Unknown correo, wrong
   password and `activo = false` all return
   `{"detail": "Invalid credentials"}`; the response never contains
   hashes or stack traces. Database-class failures map to 503 and
   unexpected failures to 500, identical to the Sprint 1 convention.
6. **Gateway proxies login; it does not authenticate.** A method-specific
   `@app.post("/api/v1/auth/login")` route reuses the existing
   `_proxy_request` helper (bodies, query and headers forwarded;
   internal URLs never exposed). Sprint 1's GET-only map for
   clientes/reservas/catalogo is untouched — mutation methods for those
   routes remain deliberately unproxied.
7. **`/health/services` scope unchanged.** It still aggregates exactly
   `clientes`, `reservas` and `catalogo` (Sprint 1 contract asserted by
   `test_gateway.py`); the auth service is reached through its own
   `/health` (Compose healthcheck) and is a `depends_on` of the
   gateway.
8. **`require_role()` shipped but not yet enforced.** The RBAC
   dependency (`401` missing/expired/invalid token, `403` wrong role)
   is ready in `shared/security.py`, but the three business services'
   `main.py` files were deliberately **not modified** in Phases 1–2
   (scope boundary — see [sprint-goal.md](sprint-goal.md)).

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
| `/api/v1/clientes` and `/api/v1/clientes/**` | GET | `CLIENTES_SERVICE_URL` |
| `/api/v1/reservas` and `/api/v1/reservas/**` | GET | `RESERVAS_SERVICE_URL` |
| `/api/v1/catalogo` and `/api/v1/catalogo/**` | GET | `CATALOGO_SERVICE_URL` |
| **`/api/v1/auth/login`** | **POST** | **`AUTH_SERVICE_URL`** |
| `/health` | GET | gateway itself |
| `/health/services` | GET | aggregated `/health` of the three business services |

Internal URLs come from environment variables (`CLIENTES_SERVICE_URL`,
`RESERVAS_SERVICE_URL`, `CATALOGO_SERVICE_URL`, **`AUTH_SERVICE_URL`**);
Docker Compose sets them to the Compose service names
(`http://clientes:8001`, …, `http://auth:8004`). Local defaults are
`http://localhost:8001-8004`.

### JWT environment variables

| Variable | Default | Where it matters |
|---|---|---|
| `JWT_SECRET` | dev fallback **with warning** (never for production) | auth service signs; any validator verifies. Compose: **fail-fast** `${JWT_SECRET:?…}` on all 5 services |
| `JWT_ALGORITHM` | `HS256` | auth service + `shared/security.py` |
| `JWT_EXPIRATION_MINUTES` | `60` | auth service (encoded as `exp - iat`) |

`.env.example` documents all three; real values live only in the
gitignored `.env` (never committed, never logged).

## Integration status

All Sprint 2 changes are **uncommitted** on branch `Dev/David-Avila`
(HEAD `1ca0d75`, which equals `origin/development`). The next step is a
Pull Request into `development` following the repository's PR-only flow
(see [cierre-sprint-2.md](cierre-sprint-2.md)); branch policy
(`development` vs the guideline's `develop`) is recorded in the
[Sprint 1 architecture](../sprint-1/architecture.md) and unchanged.
