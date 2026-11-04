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
| Alcance ejecutado | Fases 1–2: dependencias de seguridad, `shared/security.py`, esquema `usuarios` + seed, microservicio `auth` (:8004), proxy POST en el Gateway, Docker Compose (5 servicios), pruebas |
| Integración | Cambios en `Dev/David-Avila` **sin commitear**; PR hacia `development` listo para crearse (siguiente paso) |
| Objetivo | Autenticación y autorización centralizada: bcrypt (cost 12), JWT (PyJWT), tabla unificada `usuarios`, `POST /api/v1/auth/login` vía Gateway |
| Resultado | **Cumplido (Fases 1–2)** — 73 pruebas en verde, 5/5 contenedores sanos, scripts ejecutados en NeonDB |

## Objetivo y alcance vs. entregado

| Alcance | Estado | Evidencia |
|---|---|---|
| Dependencias `pyjwt==2.10.1` + `bcrypt==4.2.1` (ruedas 3.12+) | ✅ Entregado | `requirements.txt`, [test-results.md](test-results.md) §2 |
| Módulo compartido `shared/security.py` (hash, verify, token, `require_role`) | ✅ Entregado — con fallbacks, sin BD ni `.env` | `shared/security.py`, `test_security.py` (21) |
| Configuración JWT (`.env.example`) | ✅ Entregado | `JWT_SECRET` / `JWT_ALGORITHM` / `JWT_EXPIRATION_MINUTES` |
| Esquema Option B (`usuarios` + enlaces 1:1) | ✅ Ejecutado en NeonDB (2026-11-03) | [database-verification.md](database-verification.md) §1–§2 |
| Seed idempotente de administrador de prueba (bcrypt cost 12) | ✅ Ejecutado en NeonDB (2026-11-03) — placeholder Sprint 1 reemplazado | [database-verification.md](database-verification.md) §3 |
| Microservicio `auth` (:8004) con `POST /api/v1/auth/login` | ✅ Entregado — contrato 422/401/503/500 uniforme | `services/auth/`, `test_auth_service.py` (9) |
| Proxy POST en el Gateway + `AUTH_SERVICE_URL` | ✅ Entregado — el Gateway no parsea tokens | `gateway/app/main.py`, `test_auth_gateway.py` (4) |
| Docker Compose (5 servicios, JWT env, healthchecks) | ✅ Verificado — **5/5 contenedores sanos** (2026-11-03) | [test-results.md](test-results.md) §3 |
| Pruebas automatizadas | ✅ **73 passed, 6 skipped** (60 base + 13 nuevas) | [test-results.md](test-results.md) §1 |
| RBAC (`require_role`) en rutas de los 3 servicios | ⏳ Dependencia lista; **no aplicada** (fuera de alcance de las Fases 1–2) | [sprint-goal.md](sprint-goal.md) |
| Frontend | ⏸️ Confirmado para Sprint 2 (Marina, Sebastián), pendiente de planificación | [equipo-scrum](../gestion-del-proyecto/equipo-scrum.md) |
| Documentación técnica Sprint 2 | ✅ Entregada | [README de Sprint 2](README.md) |

## Verificación al cierre (2026-11-03)

| Verificación | Resultado |
|---|---|
| `pytest -q` | **73 passed, 6 skipped** (60 base + 13 nuevas) |
| Suite sin `DATABASE_URL` (Phase 1) | ✅ 21/21 aisladas — el módulo de seguridad no requiere BD |
| `pip check` | ✅ `No broken requirements found.` |
| `docker compose config --quiet` | ✅ exit 0 |
| `docker compose up --build` | ✅ **5/5 contenedores sanos** (gateway, clientes, reservas, catalogo, **auth**) |
| Scripts de esquema/seed | ✅ Ejecutados una vez, guardas idempotentes, sin sentencias destructivas |
| Regresión Sprint 1 | ✅ Las 60 pruebas previas siguen verdes; rutas GET y `/health/services` sin cambios |
| Secretos en documentación | ✅ 0 credenciales reales; la contraseña de prueba solo vive en el comentario del script seed |
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

1. **Pull Request hacia `development`** — commitear los cambios de las
   Fases 1–2 en `Dev/David-Avila` y abrir el PR (flujo solo por PR;
   nada se ha commiteado aún).
2. **Aplicar RBAC en los servicios** — usar `require_role(...)` en las
   rutas protegidas cuando existan mutaciones (Fase 3; los `main.py`
   de clientes/reservas/catalogo no se modificaron en esta fase).
3. **Frontend** (Marina, Sebastián) — pendiente de planificación.
4. **Planificación formal del Sprint 2** — registrar objetivos,
   historias y fechas cuando el equipo la confirme.
5. **Re-ejecución idempotente de los scripts** — opcional: re-ejecutar
   `sprint2_auth_schema.sql` / `sprint2_auth_seed.sql` debe insertar
   0 filas/cambios (guardas `IF NOT EXISTS` / `WHERE NOT EXISTS`).

## Seguridad verificada al cierre

- `.env` excluido de Git (`.gitignore`), nunca trackeado; contiene
  `DATABASE_URL` y `JWT_SECRET` — nunca se registran aquí.
- `JWT_SECRET` con **fail-fast** en Compose (`${JWT_SECRET:?…}`);
  en desarrollo sin configurar se usa un secreto de respaldo con
  advertencia en log (nunca válido para producción).
- Contraseña de prueba administrada solo como **hash bcrypt cost 12**;
  el texto plano existe únicamente en el comentario del script seed.
- Respuestas de login uniformes (`401 Invalid credentials`) — sin
  enumeración de cuentas; sin hashes, SQL ni trazas en las respuestas.
- 0 credenciales, hosts reales o claves privadas en esta carpeta
  (barrido por patrones, solo conteos).
