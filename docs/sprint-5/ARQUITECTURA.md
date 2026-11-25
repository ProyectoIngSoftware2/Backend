# Sprint 5 — Arquitectura

## 1. Visión general

Sprint 5 introduce el microservicio de **Notificaciones** y el patrón **Transactional Outbox** para desacoplar la creación de reservas de la notificación a usuarios/administradores.

## 2. Microservicios

| Servicio | Puerto | Responsabilidad |
|----------|--------|-----------------|
| Gateway | 8000 | Proxy, CORS, autenticación JWT |
| Clientes | 8001 | Gestión de clientes |
| Reservas | 8002 | Reservas, disponibilidad, Outbox |
| Catálogo | 8003 | Platillos, precios |
| Auth | 8004 | Autenticación, JWT |
| Notificaciones | 8005 | Consumo de eventos, creación de notificaciones |
| Redis | 6379 | Streams, consumer groups |

## 3. Flujo de eventos

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Reservas  │────▶│  PostgreSQL  │────▶│   Outbox    │
│   (API)     │     │  (TX atómica)│     │  (misma TX) │
└─────────────┘     └──────────────┘     └──────┬──────┘
                                                  │
                                                  ▼
                                          ┌──────────────┐
                                          │  Publisher   │
                                          │  (cada 5s)   │
                                          └──────┬───────┘
                                                  │
                                                  ▼
                                          ┌──────────────┐
                                          │ Redis Stream │
                                          │ reservas.    │
                                          │ events       │
                                          └──────┬───────┘
                                                  │
                                                  ▼
                                          ┌──────────────┐
                                          │  Consumer    │
                                          │  Group:      │
                                          │ notificacion │
                                          │ es           │
                                          └──────┬───────┘
                                                  │
                                                  ▼
                                          ┌──────────────┐
                                          │ Notificaciones│
                                          │ (idempotente)│
                                          └──────────────┘
```

## 4. Eventos definidos

| Evento | Trigger | Payload |
|--------|---------|---------|
| `reserva.creada` | INSERT en reservas | `{id_reserva, codigo_reserva, id_cliente, id_mesa, fecha_hora_inicio, ...}` |
| `reserva.estado_cambiado` | UPDATE de estado en reservas | `{id_reserva, estado_anterior, estado_nuevo, ...}` |

## 5. Idempotencia

- Constraint: `uq_notificacion_reserva_tipo_destinatario` UNIQUE (id_reserva, tipo, destinatario)
- Manejo: `UniqueViolation` se trata como éxito (no error)
- Garantía: Una notificación por (reserva, tipo, destinatario) máximo

## 6. Ownership de notificaciones

- **Admin**: ve y gestiona todas las notificaciones
- **Cliente**: ve y actualiza solo notificaciones de sus propias reservas (subquery join con `reservas.id_cliente`)
- **Creación manual**: solo admin (`POST /api/v1/notificaciones`)

## 7. Desacoplamiento

- Reservas no conoce el microservicio de Notificaciones
- Comunicación vía eventos (Redis Streams)
- Sin llamadas HTTP directas entre servicios para notificaciones
- El frontend NO puede crear notificaciones arbitrariamente para sustituir el flujo event-driven
