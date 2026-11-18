# API Inventory — Sprint 3

## Implemented and functional API resources (4)

| Resource | Microservice | Base Path | Operations | Auth | Validation | Docs |
|----------|-------------|-----------|------------|------|------------|------|
| Clientes | clientes | `/api/v1/clientes{/{id}}` | GET, POST, PATCH, PUT, DELETE | Admin/owner | Pydantic, bcrypt, unique email | Gateway /docs |
| Reservas | reservas | `/api/v1/reservas{/{codigo}}` | GET, POST, PATCH, PUT, DELETE | Admin/owner | Pydantic (tz datetime, gt>0), DB triggers | Gateway /docs |
| Mesas | catalogo | `/api/v1/catalogo/mesas{/{id}}` | GET, POST, PATCH, PUT, DELETE | Public read / Admin write | Pydantic (capacidad>0, unique) | Gateway /docs |
| Platillos | catalogo | `/api/v1/catalogo/platillos{/{id}}` | GET, POST, PATCH, PUT, DELETE | Public read / Admin write | Pydantic (precio>=0, nombre) | Gateway /docs |

## New Sprint 3 API resources (3)

| Resource | Microservice | Base Path | Operations | Auth | Validation | Status |
|----------|-------------|-----------|------------|------|------------|--------|
| Usuarios y roles | clientes | `/api/v1/usuarios{/{id}}`, `/api/v1/roles{/{id}}` | GET, POST, PATCH, PUT, DELETE | Admin only | Pydantic, bcrypt, unique email, role validation | Implemented |
| Horarios y bloqueos | catalogo | `/api/v1/catalogo/horarios{/{id}}`, `/api/v1/catalogo/bloqueos{/{id}}` | GET, POST, PATCH, PUT, DELETE | Public read / Admin write | hora_cierre > apertura, intervalo > 0, bloqueo fin > inicio | Implemented |
| Detalle platillos de reserva | reservas | `/api/v1/reservas/{codigo}/platillos{/{detalle_id}}` | GET, POST, PUT, DELETE | Owner / Admin | precio from catalogo, no duplicates, modifiable state | Implemented |

## Auth operation (not a business CRUD resource)

| Resource | Microservice | Base Path | Operations | Status |
|----------|-------------|-----------|----------|--------|
| Auth (login) | auth | `/api/v1/auth/login` | POST | Implemented |

## Sprint 4 API additions (2)

| Resource | Microservice | Base Path | Operations | Auth | Validation | Status |
|----------|-------------|-----------|------------|------|------------|--------|
| Disponibilidad | reservas | `/api/v1/disponibilidad` | GET | Public read | `fecha` required (400), `cantidad_personas` >= 1, `duracion_minutos` 15–720 | Implemented |
| Reportes | reservas | `/api/v1/reportes/reservas` | GET | Admin only | date range (`fecha_inicio` <= `fecha_fin`), `estado` whitelist, `id_cliente`/`id_mesa` > 0 (400) | Implemented |

## Missing resources (Sprint 4+)

| Resource | Microservice | Base Path | Status |
|----------|-------------|-----------|--------|
| Notificaciones | notificaciones | `/api/v1/notificaciones{/{id}}` | Not implemented |

## Cumulative count

- Before Sprint 3: 4 business CRUD resources + 1 auth operation
- After Sprint 3: 7 business CRUD resources + 1 auth operation
- After G4/G6 (Sprint 4): +2 read-only resources (9 resources + 1 auth operation)
- Note: lineamientos specifies "4 APIs acumuladas" for Sprint 3 and "5 APIs acumuladas" for Sprint 4. The counting ambiguity (whether the 4 existing CRUD resources count toward the cumulative total, and whether "usuarios y roles" counts as one or two resources) requires instructor confirmation.
