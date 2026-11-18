# Sprint 2 — Cierre

> Resumen de cierre de las Fases 1–2 del Sprint 2 (capa de seguridad,
> Option B) del proyecto Punto y Sal, elaborado con evidencia técnica
> verificable en este repositorio y resultados de verificación
> ejecutados el 2026-11-03. La planificación formal del Sprint 2 aún no
> ha sido registrada (**dato faltante**) — ver [README.md](README.md).

## Datos generales

| Campo | Valor |
|---|---|
| Planificación formal | ⚠️ **Dato faltante** — no hay sesión de planificación registrada (los artefactos de esta carpeta se prepararon con la información confirmada) |
| Fecha de ejecución/verificación | 2026-11-03 |
| Alcance ejecutado | Fases 1–2: dependencias de seguridad, `shared/auth.py` (antes `shared/security.py`, consolidado en la ronda de integración), esquema `usuarios` + seed, microservicio `auth` (:8004), proxy POST en el Gateway, Docker Compose (5 servicios), pruebas |
| Integración | Integrado localmente en `Dev/Noe-Mejia` como merge preparado **sin commit** (espera aprobación explícita; sin acciones remotas) |
| Objetivo | Autenticación y autorización centralizada: bcrypt (cost 12), JWT (PyJWT), tabla unificada `usuarios`, `POST /api/v1/auth/login` vía Gateway |
| Resultado | **Cumplido (Fases 1–2)** — 73 pruebas en verde, 5/5 contenedores sanos, scripts ejecutados en NeonDB (resultados históricos; los números vigentes tras la integración están en el README raíz) |

## Objetivo y alcance vs. entregado

| Alcance | Estado | Evidencia |
|---|---|---|
| Dependencias `PyJWT==2.15.1` + `bcrypt==5.0.0` (ruedas 3.12+) | ✅ Entregado | `requirements.txt`, [test-results.md](test-results.md) §2 |
| Módulo compartido `shared/auth.py` (hash, verify, token, dependencias RBAC) | ✅ Entregado — configuración fail-closed, sin BD ni `.env` | `shared/auth.py`, `test_security.py` (34) |
| Configuración JWT (`.env.example`) | ✅ Entregado | `JWT_SECRET` / `JWT_ALGORITHM` / `JWT_EXPIRE_MINUTES` / `AUTH_SERVICE_URL` |
| Esquema Option B (`usuarios` + enlaces 1:1) | ✅ Ejecutado en NeonDB (2026-11-03) | [database-verification.md](database-verification.md) §1–§2 |
| Seed idempotente de administrador de prueba (bcrypt cost 12) | ✅ Ejecutado en NeonDB (2026-11-03) — placeholder Sprint 1 reemplazado | [database-verification.md](database-verification.md) §3 |
| Microservicio `auth` (:8004) con `POST /api/v1/auth/login` | ✅ Entregado — contrato 422/401/503/500 uniforme | `services/auth/`, `test_auth_service.py` (9) |
| Proxy POST en el Gateway + `AUTH_SERVICE_URL` | ✅ Entregado — el Gateway no parsea tokens | `gateway/app/main.py`, `test_auth_gateway.py` (4) |
| Docker Compose (5 servicios, JWT env, healthchecks) | ✅ Verificado — **5/5 contenedores sanos** (2026-11-03) | [test-results.md](test-results.md) §3 |
| Pruebas automatizadas | ✅ **73 passed, 6 skipped** (60 base + 13 nuevas) | [test-results.md](test-results.md) §1 |
| RBAC (`require_roles`) en rutas de los 3 servicios | ✅ **Aplicado** en la ronda de integración sobre `Dev/Noe-Mejia` (401/403 + propiedad anti-IDOR) | `shared/auth.py`, `test_auth.py`, `test_security.py` |
| Frontend | ⏸️ Confirmado para Sprint 2 (Marina, Sebastián), pendiente de planificación | [equipo-scrum](../gestion-del-proyecto/equipo-scrum.md) |
| Documentación técnica Sprint 2 | ✅ Entregada | [README de Sprint 2](README.md) |

## Verificación al cierre (2026-11-03, Fases 1–2)

> Resultados **históricos** de la fase original en `Dev/David-Avila`.
> La verificación final tras la integración (suite completa, Docker y
> base de datos) está en el [README raíz](../../README.md) y en el
> informe de integración.

| Verificación | Resultado |
|---|---|
| `pytest -q` | **73 passed, 6 skipped** (60 base + 13 nuevas) |
| Suite sin `DATABASE_URL` (Phase 1) | ✅ 21/21 aisladas — el módulo de seguridad no requiere BD |
| `pip check` | ✅ `No broken requirements found.` |
| `docker compose config --quiet` | ✅ exit 0 |
| `docker compose up --build` | ✅ **5/5 contenedores sanos** (gateway, clientes, reservas, catalogo, **auth**) |
| Scripts de esquema/seed | ✅ Ejecutados una vez, guardas idempotentes, sin sentencias destructivas |
| Regresión Sprint 1 | ✅ Las 60 pruebas previas siguen verdes; rutas GET y `/health/services` sin cambios |
| Secretos en documentación | ✅ 0 credenciales reales; la contraseña de prueba vive solo en el entorno local del equipo (retirada del comentario del script seed en la integración) |
| Git | ✅ Nada en staging ni commiteado; rama `Dev/David-Avila` sin cambios de historial |

## Estado de la documentación Scrum

| Artefacto | Estado |
|---|---|
| [Sprint Goal](sprint-goal.md) | ✅ Preparado 2026-11-03 (planificación formal: **dato faltante**) |
| [Arquitectura](architecture.md) | ✅ Escrita y verificada contra el código |
| [Verificación de base de datos](database-verification.md) | ✅ Scripts ejecutados y registrados |
| [Resultados de pruebas](test-results.md) | ✅ Resultados reales (73 passed) |
| Sprint Planning / Backlog / Review / Retrospective / Daily | ⏳ **Dato faltante** — no se inventan registros (convención de Sprint 1) |
| Frontend | ⏸️ Confirmado para Sprint 2, pendiente de planificar |

## Pendientes al cierre

1. **Aprobación de la integración** — el merge de `development` y
   `Dev/David-Avila` en `Dev/Noe-Mejia` está preparado **sin commit**;
   cualquier commit o acción remota requiere aprobación explícita
   (regla vigente de la ronda de integración).
2. ~~Aplicar RBAC en los servicios~~ — **completado** en la ronda de
   integración: `require_roles`/`get_current_user` de `shared/auth.py`
   protegen todas las rutas de negocio (401/403 + propiedad).
3. **Frontend** (Marina, Sebastián) — pendiente de planificación; el
   contrato actual está en [api-integration.md](../api-integration.md).
4. **Planificación formal del Sprint 2** — registrar objetivos,
   historias y fechas cuando el equipo la confirme.
5. **Re-ejecución idempotente de los scripts** — opcional: re-ejecutar
   `sprint2_auth_schema.sql` / `sprint2_auth_seed.sql` debe insertar
   0 filas/cambios (guardas `IF NOT EXISTS` / `WHERE NOT EXISTS`).

## Seguridad verificada al cierre

- `.env` excluido de Git (`.gitignore`), nunca trackeado; contiene
  `DATABASE_URL` (verificado por inspección de claves, sin imprimir
  valores) — `JWT_SECRET` se inyecta por variable de entorno, nunca
  vive en el repositorio.
- `JWT_SECRET` con **fail-fast** en Compose (`${JWT_SECRET:?…}`) y
  **fail-closed** en código: obligatorio, ≥32 caracteres, sin secreto
  de respaldo de desarrollo.
- Contraseña de prueba administrada solo como **hash bcrypt cost 12**;
  el texto plano vive únicamente en el entorno local del equipo
  (`TEST_ADMIN_PASSWORD`) — fue retirado del comentario del script
  seed en la ronda de integración.
- Respuestas de login uniformes (`401 Invalid credentials`) — sin
  enumeración de cuentas; sin hashes, SQL ni trazas en las respuestas.
- 0 credenciales, hosts reales o claves privadas en esta carpeta
  (barrido por patrones, solo conteos).
