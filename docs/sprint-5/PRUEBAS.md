# Sprint 5 — Pruebas

## 1. Suite de pruebas

| Métrica | Valor |
|---------|-------|
| Tests passed | 275 |
| Tests skipped | 17 |
| Tests failed | 0 |
| Tiempo | ~13.7s |

**Comando:** `python -m pytest -q`

## 2. Tests nuevos (Sprint 5)

| Archivo | Tests | Descripción |
|---------|-------|-------------|
| `test_notifications.py` | 14 | CRUD, idempotencia, ownership, autorización |

## 3. Tests actualizados (Sprint 5)

| Archivo | Cambios |
|---------|---------|
| `test_gateway.py` | Rutas proxy para notificaciones |
| `test_authorization.py` | Permisos de notificaciones por rol |
| `test_crud.py` | Outbox events en creación/modificación de reservas |

## 4. Tests omitidos (17)

| Archivo | Cantidad | Motivo |
|---------|----------|--------|
| `test_auth_live.py` | 11 | Requieren `RUN_DB_TESTS=1` + credenciales reales |
| `test_integration_live.py` | 6 | Requieren `RUN_DB_TESTS=1` + credenciales reales |

## 5. Validaciones de base de datos

| Validación | Estado | Método |
|------------|--------|--------|
| G1 (solapamiento horarios) | ✅ | Trigger + pruebas negativas SQL directas |
| G2 (solapamiento bloqueos) | ✅ | Trigger + pruebas negativas SQL directas |
| G3 (reservas y mesas) | ✅ | CHECK + FK + triggers |
| Idempotencia notificaciones | ✅ | Constraint UNIQUE + UniqueViolation handling |

## 6. Prueba E2E

| Paso | Identificador |
|------|---------------|
| Reserva creada | id_reserva=10, codigo=PS-20261125-000010 |
| Evento Outbox | id_evento=1, tipo=reserva.creada |
| Mensaje Redis | stream=reservas.events, message_id=1795581952065-0 |
| Notificación | id_notificacion=13, tipo=reserva_recibida |

## 7. Pruebas de recuperación (pendientes)

- Redis down: no ejecutado (requiere Docker)
- Consumer restart: no ejecutado
- Mensaje duplicado: verificado vía idempotencia
- Rollback sin evento: verificado vía atomicidad
