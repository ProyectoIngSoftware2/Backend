# Sprint 5 — API de Notificaciones

## 1. Base URL

```
http://localhost:8005/api/v1/notificaciones
```

(Proxied via Gateway: `http://localhost:8000/api/v1/notificaciones`)

## 2. Endpoints

### 2.1 Listar notificaciones

```
GET /api/v1/notificaciones
```

**Headers:** `Authorization: Bearer <token>`

**Query params:**
- `leida` (bool, optional): filtrar por estado de lectura
- `tipo` (string, optional): filtrar por tipo
- `limit` (int, default 50): paginación
- `offset` (int, default 0): paginación

**Respuesta (admin):** Todas las notificaciones
**Respuesta (cliente):** Solo notificaciones de sus reservas

### 2.2 Obtener notificación por ID

```
GET /api/v1/notificaciones/{id}
```

**Headers:** `Authorization: Bearer <token>`

**Permisos:** Admin (todas) / Cliente (solo propias)

### 2.3 Marcar como leída

```
PATCH /api/v1/notificaciones/{id}
```

**Headers:** `Authorization: Bearer <token>`
**Body:** `{"leida": true}`

**Permisos:** Admin (todas) / Cliente (solo propias)

### 2.4 Crear notificación (admin only)

```
POST /api/v1/notificaciones
```

**Headers:** `Authorization: Bearer <token>`
**Body:**
```json
{
    "id_reserva": 1,
    "destinatario": "admin",
    "tipo": "reserva_recibida",
    "mensaje": "Nueva reserva recibida"
}
```

**Permisos:** Solo administrador

## 3. Tipos de notificación

| Tipo | Descripción |
|------|-------------|
| `reserva_recibida` | Nueva reserva creada |
| `reserva_confirmada` | Reserva confirmada |
| `reserva_cancelada` | Reserva cancelada |
| `reserva_modificada` | Reserva modificada |

## 4. Destinatarios

| Destinatario | Descripción |
|--------------|-------------|
| `admin` | Notificación para administradores |
| `cliente` | Notificación para el cliente |

## 5. Idempotencia

Crear una notificación duplicada (mismo `id_reserva`, `tipo`, `destinatario`) retorna la notificación existente sin error (HTTP 200, no 201).

## 6. Respuestas de error

| Código | Descripción |
|--------|-------------|
| 401 | Token inválido o ausente |
| 403 | Sin permisos (ej. cliente intentando crear) |
| 404 | Notificación no encontrada |
| 422 | Datos inválidos |
