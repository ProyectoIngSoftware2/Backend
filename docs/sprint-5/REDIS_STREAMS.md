# Sprint 5 — Redis Streams

## 1. Configuración

| Parámetro | Valor |
|-----------|-------|
| Host | redis (Docker) / localhost (local) |
| Puerto | 6379 |
| Stream | `reservas.events` |
| Consumer Group | `notificaciones` |
| Volumen persistente | `redis_data` |

## 2. Estructura del stream

```
reservas.events (Stream)
├── Message 1795581952065-0
│   └── data: {"tipo_evento": "reserva.creada", "payload": {...}}
├── Message ...
└── ...
```

## 3. Consumer Group

- **Nombre:** `notificaciones`
- **Consumidores:** 1 (microservicio notificaciones)
- **Pending messages:** Monitoreado vía `XINFO GROUPS`

## 4. Comandos de diagnóstico

```bash
# Ver streams
redis-cli XINFO STREAMS

# Ver grupos de consumidores
redis-cli XINFO GROUPS reservas.events

# Ver mensajes pendientes
redis-cli XPENDING reservas.events notificaciones

# Leer mensajes recientes
redis-cli XREVRANGE reservas.events + - COUNT 10
```

## 5. Recuperación ante fallos

| Escenario | Comportamiento |
|-----------|----------------|
| Redis caído | Publisher reintenta en siguiente ciclo (5s) |
| Consumer caído | Mensajes quedan en pending, se reprocesan al reiniciar |
| Mensaje duplicado | Idempotencia en notificaciones (constraint UNIQUE) |
| Stream lleno | Configurar MAXLEN en XADD |

## 6. Persistencia

- Volumen Docker `redis_data` persiste datos entre reinicios
- Redis configurado con AOF (Append Only File) para durabilidad
- En producción: configurar snapshot RDB + AOF

## 7. Monitoreo

```python
import redis
r = redis.from_url("redis://localhost:6379/0")
groups = r.xinfo_groups("reservas.events")
for g in groups:
    print(f"Grupo: {g['name']}, Consumers: {g['consumers']}, Pending: {g['pending']}")
```
