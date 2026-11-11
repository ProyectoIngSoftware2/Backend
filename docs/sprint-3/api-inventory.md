# API Inventory — Sprint 3

## Implemented and functional API resources (4)

| Resource | Microservice | Base Path | Operations | Auth | Validation | Docs |
|----------|-------------|-----------|------------|------|------------|------|
| Clientes | clientes | `/api/v1/clientes{/{id}}` | GET, POST, PATCH, PUT, DELETE | Admin/owner | Pydantic, bcrypt, unique email | Gateway /docs |
| Reservas | reservas | `/api/v1/reservas{/{codigo}}` | GET, POST, PATCH, PUT, DELETE | Admin/owner | Pydantic (tz datetime, gt>0), DB triggers | Gateway /docs |
| Mesas | catalogo | `/api/v1/catalogo/mesas{/{id}}` | GET, POST, PATCH, PUT, DELETE | Public read / Admin write | Pydantic (capacidad>0, unique) | Gateway /docs |
| Platillos | catalogo | `/api/v1/catalogo/platillos{/{id}}` | GET, POST, PATCH, PUT, DELETE | Public read / Admin write | Pydantic (precio>=0, nombre) | Gateway /docs |

## New Sprint 3 API resources (2)

| Resource | Microservice | Base Path | Operations | Auth | Validation | Status |
|----------|-------------|-----------|------------|------|------------|--------|
| Horarios y bloqueos | catalogo | `/api/v1/catalogo/horarios{/{id}}`, `/api/v1/catalogo/bloqueos{/{id}}` | GET, POST, PATCH, PUT, DELETE | Public read / Admin write | hora_cierre > apertura, intervalo > 0, bloqueo fin > inicio | Implemented |
| Detalle platillos de reserva | reservas | `/api/v1/reservas/{codigo}/platillos{/{detalle_id}}` | GET, POST, PUT, DELETE | Owner / Admin | precio from catalogo, no duplicates, modifiable state | Implemented |

## Sprint 2 required but missing before Sprint 3

| Resource | Microservice | Base Path | Status |
|----------|-------------|-----------|--------|
| Usuarios y roles | clientes | `/api/v1/usuarios{/{id}}`, `/api/v1/roles{/{id}}` | Implemented in Sprint 3 |

## Auth operation (not a business CRUD resource)

| Resource | Microservice | Base Path | Operations | Status |
|----------|-------------|-----------|----------|
| Auth (login) | auth | `/api/v1/auth/login` | POST | Implemented |

## Missing resources (Sprint 4+)

| Resource | Microservice | Base Path | Status |
|----------|-------------|-----------|--------|
| Disponibilidad | catalogo/reservas | `/api/v1/disponibilidad` | Not implemented (GET-only, not CRUD) |
| Reportes y auditoría | reportes/reservas | `/api/v1/reportes/*` | Not implemented (read-only) |
| Notificaciones | notificaciones | `/api/v1/notificaciones{/{id}}` | Not implemented |

## Cumulative count

- Before Sprint 3: 4 business CRUD resources + 1 auth operation
- After Sprint 3: 6 business CRUD resources + 1 auth operation
- Note: lineamientos specifies "4 APIs acumuladas" for Sprint 3 and "5 APIs acumuladas" for Sprint 4. The counting ambiguity (whether the 4 existing CRUD resources count toward the cumulative total) requires instructor confirmation.
