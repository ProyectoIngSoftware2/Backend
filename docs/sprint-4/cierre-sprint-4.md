# Sprint 4 — Cierre

> Resumen de cierre del Sprint 4 del backend Punto y Sal (FastAPI +
> microservicios + API Gateway), elaborado con evidencia técnica
> verificable en este repositorio y resultados de verificación
> ejecutados el **2026-11-17** en la rama `Dev/David-Avila`. Cierra los
> gaps **G4–G7** de la auditoría y documenta el estado honesto de
> **G1–G3** (pendientes, con mitigaciones), la integración de los
> endpoints nuevos y la colección Postman oficial.

## Datos generales

| Campo | Valor |
|---|---|
| Fecha de ejecución/verificación | 2026-11-17 |
| Rama | `Dev/David-Avila` (cambios en working tree, **sin commit** — el commit lo realiza el equipo) |
| Alcance ejecutado | G4 reportes de reservas · G5 `DELETE /api/v1/roles/{id}` · G6 consulta pública de disponibilidad · G7 colección Postman v2.1.0 · documentación `docs/sprint-4/` |
| Suite de pruebas | **260 passed, 17 skipped, 1 failed** (falla preexistente dependiente del entorno — §6); `pip check` limpio |
| Entregable Postman | `docs/postman/PuntoYSal-Sprint4.postman_collection.json` — 31 requests, 8 grupos, 8 variables |
| Integración | Rama acumulada sobre el trabajo de sprints previos; los 5 servicios siguen enrutados por el Gateway (`/docs` y OpenAPI verificados) |

## 1. Logros del sprint

| # | Logro | Evidencia |
|---|-------|-----------|
| 1 | **Reportes de reservas** (G4): `GET /api/v1/reportes/reservas`, solo administrador, 5 filtros combinables (rango de fechas, estado, cliente, mesa), resumen `GROUP BY estado` | `services/reservas/app/main.py` · `gateway/app/main.py` (`route_reportes`, GET-only, Bearer en OpenAPI) · `tests/test_reports.py` (11) · `tests/test_gateway.py` (3) |
| 2 | **Eliminación de roles** (G5): `DELETE /api/v1/roles/{id_rol}` con salvaguardas (400 si el rol está en uso, 404 si no existe, 403 no-admin) | `services/clientes/app/main.py` (`delete_role`) · `tests/test_sprint3.py` (3) · matriz `tests/test_authorization.py` (`delete /api/v1/roles/1`) |
| 3 | **Disponibilidad pública** (G6): `GET /api/v1/disponibilidad` sin token — horarios del día, mesas por capacidad, slots libres considerando reservas activas y bloqueos | `services/reservas/app/main.py` · `gateway/app/main.py` (`route_disponibilidad`, GET-only, pública en OpenAPI) · `tests/test_availability.py` (12) · `tests/test_gateway.py` (2) |
| 4 | **Colección Postman oficial** (G7): v2.1.0 con login que auto-guarda tokens, CRUD de catálogo, roles (incluye el DELETE nuevo), disponibilidad, reservas y reportes con filtros | `docs/postman/PuntoYSal-Sprint4.postman_collection.json` — 31 requests, 8 carpetas, 18 con Bearer, 31 con `pm.test` |
| 5 | **Documentación Sprint 4** estructuralmente consistente con los sprints previos | `docs/sprint-4/README.md`, `cierre-sprint-4.md`, `api-inventory.md`, `test-results.md` |
| 6 | **Sin regresiones**: la suite completa queda en 260 passed / 17 skipped con `pip check` limpio | §6 · `docs/sprint-4/test-results.md` |

## 2. Estado de los gaps G1–G7

| Gap | Descripción | Estado | Detalle / mitigación |
|-----|-------------|--------|----------------------|
| **G1** | Validación de horarios a nivel de base de datos | ⏳ **Pendiente** | Requiere **DDL de triggers** con aprobación del equipo (no implementado en este sprint). *Mitigación vigente:* validación Pydantic en el servicio (`hora_cierre > apertura`, `intervalo > 0`) — cobierta por `tests/test_sprint3.py`. La regla fuerte a nivel BD sigue abierta. |
| **G2** | Validación de bloqueos a nivel de base de datos | ⏳ **Pendiente** | Mismo caso: DDL pendiente de aprobación. *Mitigación vigente:* validación Pydantic (`fin > inicio`) en el servicio, testeada en `tests/test_sprint3.py`; además G6 ya **consume** los bloqueos al calcular disponibilidad, por lo que cualquier bloqueo inválido afectaría el reporte de slots. |
| **G3** | Solapamiento/capacidad no auditable en BD | ⏳ **Pendiente** | Los triggers de solapamiento/capacidad no fueron implementados (requieren aprobación del equipo). *Mitigación vigente:* la regla se respeta en la capa de servicio y se ejercita en las pruebas de reservas; G6 muestra el efecto de solapamientos en los slots. La auditoría a nivel BD queda pendiente. |
| **G4** | Endpoint de reportes | ✅ **Cerrado** | `GET /api/v1/reportes/reservas` — admin-only, 5 filtros, validación 400, resumen por estado; gateway GET-only con Bearer en OpenAPI; 11 + 3 pruebas verdes. |
| **G5** | `DELETE /api/v1/roles/{id}` | ✅ **Cerrado** | Implementado con salvaguardas 400/404/403; 3 pruebas nuevas + entrada en la matriz de autorización; documentado en el inventario y en Postman. |
| **G6** | Consulta de disponibilidad | ✅ **Cerrado** | `GET /api/v1/disponibilidad` público, parámetros validados con 400 (nunca 422), considera reservas y bloqueos; 12 + 2 pruebas verdes. |
| **G7** | Colección Postman | ✅ **Cerrado** | Colección v2.1.0 válida con variables `base_url` y `jwt_token`, login con auto-guardado de token, los 5 APIs cubiertos y los 3 endpoints nuevos incluidos; sin credenciales reales en el repo. |

> **Transparencia:** G1–G3 **no** se cierran en este sprint porque
> exigen cambios de DDL en la base de datos con aprobación conjunta del
> equipo; nunca se implementaron aquí. Se documentan con sus
> mitigaciones de aplicación en lugar de reportarse como cerrados.

## 3. Integración de los entregables nuevos

### 3.1 Disponibilidad (G6)

- **Endpoint:** `GET /api/v1/disponibilidad` (microservicio `reservas`),
  registrado en el Gateway como `route_disponibilidad` — **solo GET**, y
  marcado como **lectura pública** en el OpenAPI del Gateway.
- **Contrato:** `fecha` obligatoria (`YYYY-MM-DD`); `cantidad_personas`
  ≥ 1 y `duracion_minutos` 15–720 opcionales; cualquier valor inválido
  responde **400 Bad Request** con mensaje en `detail` (la API no usa
  422 en este endpoint).
- **Cálculo:** horarios del día + mesas candidatas por capacidad + slots
  libres considerando reservas activas y bloqueos (general = todas las
  mesas; específico = solo esa mesa), con aritmética de slots sobre
  pared local (naive wall-clock) y 4 queries autónomas.
- **Pruebas:** `tests/test_availability.py` (12) + 2 en
  `tests/test_gateway.py` (enrutamiento y marcado público/GET-only).

### 3.2 Reportes (G4)

- **Endpoint:** `GET /api/v1/reportes/reservas` (microservicio
  `reservas`), registrado como `route_reportes` — **solo GET** y
  **protegido con Bearer** en el OpenAPI del Gateway (tag `reportes`).
- **Filtros:** `fecha_inicio`/`fecha_fin` (rango no invertido), `estado`
  (whitelist de 6 estados), `id_cliente`, `id_mesa` — todos combinables;
  valores inválidos → **400**; cliente → **403**; sin token → **401**.
- **Respuesta:** `filtros` (eco normalizado), `resumen` (totales +
  conteos por estado vía `GROUP BY`) y `reservas` (filas). El SQL usa
  fragmentos WHERE estáticos y parámetros `%s` (sin concatenación de
  entrada del usuario).
- **Pruebas:** `tests/test_reports.py` (11) + 3 en
  `tests/test_gateway.py` (enrutamiento, 403 con token de cliente, y
  marcado admin-only en OpenAPI).

### 3.3 Eliminación de roles (G5)

- **Endpoint:** `DELETE /api/v1/roles/{id_rol}` en el microservicio
  `clientes` (enrutado por el Gateway existente `route_roles`).
- **Salvaguardas:** 200 al eliminar; **400** si el rol sigue asignado a
  usuarios (mensaje que indica reasignar primero); **404** id inexistente;
  **403** token no-admin; **401** sin token.
- **Pruebas:** 3 en `tests/test_sprint3.py` + entrada
  `(clientes_main, "delete", "/api/v1/roles/1")` en la matriz de
  `tests/test_authorization.py`.

### 3.4 Colección Postman (G7)

- **Archivo:** `docs/postman/PuntoYSal-Sprint4.postman_collection.json`
  (válida v2.1.0, verificada con `python -m json.tool`).
- **Variables de colección:** `base_url` (`http://localhost:8000`),
  `jwt_token`, `jwt_token_cliente`, `codigo_reserva`, `admin_correo`
  (correo sembrado público en `database/sprint2_auth_seed.sql`),
  `admin_password`, `cliente_correo`, `cliente_password` — **las tres
  contraseñas/correo de cliente están vacías por defecto: no se
  commitan credenciales** (precedente del Sprint 2).
- **Grupos (8 carpetas, 31 requests):** General/smoke · Autenticación
  (login admin y cliente con `pm.test` que guardan el token; registro
  público de cliente opcional) · Mesas CRUD · Platillos CRUD · Roles
  (incluye `DELETE /api/v1/roles/{id}` ★ G5) · Disponibilidad (G6, con
  caso 400) · Reservas (crear / listado admin / detalle) · Reportes (G4:
  filtros por fechas, estado, cliente, caso 400 y caso **403 RBAC** con
  token de cliente).
- **Flujo de token:** el último login de la carpeta de autenticación es
  el del administrador, de modo que `jwt_token` queda como admin para
  todos los grupos protegidos; las aserciones son tolerantes
  (`[200,404]`, `[201,409]`, etc.) para que re-ejecuciones no fallen.
- **Anti-IDOR documentado:** los clientes no tienen listado propio de
  reservas (decisión de diseño) — obtienen la suya por `codigo_reserva`
  con su propio token.

## 4. Verificación de enrutamiento por Gateway

| Verificación | Resultado |
|---|---|
| Rutas nuevas registradas | ✅ `route_disponibilidad` (GET, pública) y `route_reportes` (GET, Bearer) en `gateway/app/main.py` |
| Solo métodos expuestos por el servicio | ✅ ambos endpoints nuevos son GET-only; el Gateway no inventa métodos |
| OpenAPI público vs protegido | ✅ disponibilidad marcada pública; reportes marcada con Bearer (tag `reportes`) — verificado por pruebas |
| Sin bypass de autorización | ✅ el Gateway solo reenvía (incluye `Authorization`); cada servicio valida JWT y roles por su cuenta |
| Salud agregada | ✅ `/health` y `/health/services` (4 servicios) — carpeta "0. General" de Postman |
| Pruebas | ✅ `tests/test_gateway.py` **18/18 verdes** |

## 5. Validación RBAC / anti-IDOR

| Área | Evidencia | Resultado |
|---|---|---|
| Matriz método × ruta × rol (incluye `DELETE /api/v1/roles/1`) | `tests/test_authorization.py` (24) | ✅ verdes |
| Claims JWT, configuración fail-closed, errores de token | `tests/test_security.py` (43) | 42 ✅ + 1 falla preexistente de entorno (§6) |
| Login sin enumeración de cuentas (401 uniforme; sin `password`/`password_hash` en respuestas) | `tests/test_auth.py` (28) + `test_auth_service.py` (13) + `test_auth_gateway.py` (4) | ✅ verdes |
| Reportes: cliente → 403, sin token → 401 | `tests/test_reports.py` | ✅ verdes |
| Disponibilidad pública sin token (diseño) | `tests/test_availability.py` | ✅ verdes |
| IDOR: detalle ajeno → 404 (no filtra existencia), dueño/admin → 200 | `tests/test_sprint3.py` / matriz de autorización | ✅ verdes (sin regresiones) |

## 6. Resultados de pruebas (resumen)

Comando: `.venv\Scripts\python.exe -m pytest -q` — detalle completo en
[test-results.md](test-results.md).

| Resultado | Cantidad |
|---|---|
| ✅ Passed | **260** |
| ⏭️ Skipped (live/DB, opt-in `RUN_DB_TESTS=1`) | **17** |
| ❌ Failed | **1** — `tests/test_security.py::test_missing_jwt_secret_fails_closed`: **preexistente y dependiente del entorno** (el `.env` local define `JWT_SECRET`, por lo que no se puede simular el "secret ausente"). No es una regresión del Sprint 4 (gap G8, fuera de este alcance). |
| Total recolectado | 278 |
| `pip check` | ✅ `No broken requirements found.` |

Cadena de crecimiento del suite en este sprint: 229 → **232** (G5) →
**246** (G6) → **260** (G4).

## 7. Pendientes y notes

- **G1, G2, G3:** DDL de triggers pendiente de aprobación del equipo
  (§2). No se cierran sin esa aprobación.
- **G8:** falla preexistente `test_missing_jwt_secret_fails_closed`
  dependiente del `.env` local (§6) — fuera del alcance del Sprint 4.
- **G11:** los clientes no tienen listado propio de reservas — decisión
  de diseño documentada (el detalle por `codigo_reserva` con el token
  del dueño es el flujo soportado), reflejada en la carpeta de Reservas
  de Postman.
- **Notificaciones** (`/api/v1/notificaciones`) sigue como único recurso
  faltante del inventario (Sprint 5+).
- **Postman:** las contraseñas (`admin_password`, `cliente_password`) y
  el correo de cliente se definen en el entorno local de cada quien;
  nunca se commitan valores reales.
- **Commit:** todo está limpio y listo en el working tree de
  `Dev/David-Avila`; el commit lo realiza el equipo (sin acciones
  remotas en esta sesión).

## 8. Convenciones

- Código técnico y documentación en inglés; este cierre en español
  (consistencia con `docs/sprint-2/cierre-sprint-2.md`).
- Nunca se registran secretos, contenidos de `.env` ni credenciales
  reales en `docs/` (los emails son de dominio de prueba
  `@puntoysal.test` / `@example.com`; las contraseñas viven solo en el
  entorno local).
- Campos sin dato confirmado se marcan explícitamente como datos
  faltantes; nunca se fabrican (convención heredada del Sprint 1).
