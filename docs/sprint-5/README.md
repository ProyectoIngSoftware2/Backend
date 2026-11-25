# Sprint 5 — README

## Contenido

| Archivo | Descripción |
|---------|-------------|
| `ARQUITECTURA.md` | Arquitectura del microservicio de notificaciones y flujo de eventos |
| `OUTBOX_PATTERN.md` | Patrón Transactional Outbox: diseño, implementación y garantías |
| `REDIS_STREAMS.md` | Redis Streams: configuración, consumer groups, recuperación |
| `NOTIFICACIONES_API.md` | API del microservicio de notificaciones |
| `MIGRACIONES.md` | Migraciones de Sprint 5 aplicadas a NeonDB |
| `PRUEBAS.md` | Resultados de pruebas del Sprint 5 |
| `CONFIGURACION.md` | Configuración de Docker Compose y variables de entorno |
| `RECUPERACION_ERRORES.md` | Procedimientos de recuperación ante fallos |

## Resumen del sprint

- **Fecha de cierre:** 2026-11-25
- **Rama:** `feat/sprint-5-notificaciones`
- **SHA de referencia:** `c59cd09ffda46240ce1deb6240c70a4305eaf6`
- **Base:** `development` @ `a8c1850b9089f4951761963418841e61fb5cd53e`

## Objetivos cumplidos

1. ✅ Microservicio de notificaciones (puerto 8005) implementado
2. ✅ Redis Streams integrado (puerto 6379) con consumer group `notificaciones`
3. ✅ Patrón Transactional Outbox en reservas (tabla `outbox_events`)
4. ✅ Eventos: `reserva.creada`, `reserva.estado_cambiado`
5. ✅ Idempotencia de notificaciones (constraint `uq_notificacion_reserva_tipo_destinatario`)
6. ✅ Triggers G1 (solapamiento horarios) y G2 (solapamiento bloqueos) aplicados
7. ✅ Ownership de notificaciones (cliente solo ve las propias)
8. ✅ Docker Compose con 7 contenedores (incluye notificaciones + redis)
9. ✅ CORS corregido (`CORS_ORIGINS`)
10. ✅ Suite de pruebas: 275 passed, 17 skipped, 0 failed

## Convenciones

- Documentación técnica en español
- Nunca se registran secretos, contenidos de `.env` ni credenciales reales
- Los tests live requieren `RUN_DB_TESTS=1` + credenciales dedicadas
