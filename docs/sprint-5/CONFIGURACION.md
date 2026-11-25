# Sprint 5 — Configuración

## 1. Docker Compose

### Servicios (7 contenedores)

| Servicio | Imagen | Puerto | Health Check |
|----------|--------|--------|--------------|
| gateway | python:3.12 | 8000 | GET /health |
| clientes | python:3.12 | 8001 | GET /health |
| reservas | python:3.12 | 8002 | GET /health |
| catalogo | python:3.12 | 8003 | GET /health |
| auth | python:3.12 | 8004 | GET /health |
| notificaciones | python:3.12 | 8005 | GET /health |
| redis | redis:7-alpine | 6379 | redis-cli ping |

### Volúmenes

| Volumen | Propósito |
|---------|-----------|
| `redis_data` | Persistencia de Redis Streams |

### Variables de entorno (.env.docker)

```env
DATABASE_URL=postgresql://...?sslmode=require
JWT_SECRET=<secret>
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60
CORS_ORIGINS=http://localhost:8080
REDIS_URL=redis://redis:6379/0
```

## 2. Variables de entorno locales (.env)

```env
DATABASE_URL=postgresql://...?sslmode=require
JWT_SECRET=<secret>
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60
CORS_ORIGINS=http://localhost:8080
```

**Nota:** `.env` no incluye `REDIS_URL` (solo para Docker). En local, Redis se conecta a `localhost:6379`.

## 3. CORS

Variable: `CORS_ORIGINS` (no `CORS_ORIONS` — corregido en commit `79c1001`)

Formato: lista separada por comas de orígenes permitidos.
Ejemplo: `http://localhost:8080,http://localhost:5173`

## 4. Ejecución

```bash
# Levantar todos los servicios
docker compose --env-file .env.docker up -d

# Verificar health
curl http://localhost:8000/health

# Ver logs
docker compose logs -f notificaciones

# Detener
docker compose down
```

## 5. Tests

```bash
# Ejecutar suite completa
python -m pytest -q

# Con tests live (requiere credenciales)
RUN_DB_TESTS=1 python -m pytest -q
```
