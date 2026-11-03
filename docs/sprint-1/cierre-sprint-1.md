# Sprint 1 — Cierre

> Resumen de cierre del Sprint 1 del proyecto Punto y Sal, elaborado con
> información confirmada por el equipo (2026-11-03) y evidencia técnica
> verificable en este repositorio.

## Datos generales

| Campo | Valor |
|---|---|
| Planificación | 2026-10-21 ([sprint-planning.md](sprint-planning.md)) |
| Período de desarrollo | 2026-10-22 al 2026-11-03 |
| Revisión / aceptación | 2026-11-03 — los cuatro integrantes aceptaron el backend, sin correcciones adicionales ([sprint-review.md](sprint-review.md)) |
| Integración | PR #1 "Sprint 1 - Backend de Punto y Sal" (`Dev/Noe-Mejia` → `development`), fusionado el 2026-11-03 (`91e071a`) |
| Objetivo | Infraestructura backend inicial: 3 microservicios + API Gateway + Docker Compose + BD + pruebas + documentación |
| Resultado | **Cumplido** — el equipo aceptó el incremento entregado |

## Objetivo y alcance vs. entregado

| Alcance confirmado | Estado | Evidencia |
|---|---|---|
| Microservicio de Clientes | ✅ Entregado | `services/clientes/`, [test-results.md](test-results.md) |
| Microservicio de Reservas | ✅ Entregado | `services/reservas/`, [test-results.md](test-results.md) |
| Microservicio de Catálogo | ✅ Entregado | `services/catalogo/`, [test-results.md](test-results.md) |
| API Gateway | ✅ Entregado | `gateway/`, [architecture.md](architecture.md) |
| Docker Compose | ✅ Verificado (4/4 contenedores sanos) | [test-results.md](test-results.md) §4 |
| Integración con la base de datos | ✅ Verificado (8 tablas; 22 filas de prueba) | [database-verification.md](database-verification.md) |
| Comunicación HTTP entre servicios | ✅ Verificado (F-01 aprobado y probado en vivo) | [design-change-log.md](design-change-log.md) |
| Pruebas unitarias y de integración | ✅ 39 unitarias + 6 de integración (re-ejecutadas 2026-11-03) | [test-results.md](test-results.md) |
| Documentación técnica | ✅ Entregada | [README de Sprint 1](README.md) |
| Frontend | ⏸️ Pendiente para el Sprint 2 (decisión del equipo) | [docs/sprint-2](../sprint-2/README.md) |

## Resultado de la revisión (2026-11-03)

- Participaron los cuatro integrantes.
- Se presentó el backend.
- El equipo aceptó el resultado.
- No se solicitaron correcciones adicionales.

## Estado de la documentación Scrum

| Artefacto | Estado |
|---|---|
| [Sprint Goal](sprint-goal.md) | ✅ Objetivo confirmado en planificación |
| [Sprint Planning](sprint-planning.md) | ✅ Registrado (2026-10-21) |
| [Sprint Backlog](sprint-backlog.md) | ✅ Historias con responsabilidad general; reparto individual pendiente |
| [Registro de actividades](registro-actividades.md) | ✅ Registrado |
| [Sprint Review](sprint-review.md) | ✅ Evento realizado (2026-11-03) |
| [Sprint Retrospective](sprint-retrospective.md) | ✅ Contenido confirmado (reflexión de Noé aceptada por el equipo) |
| [Daily Scrum](daily-scrum.md) | ✅ Sin reuniones formales (confirmado; no hay registros que inventar) |
| [Burndown](burndown.md) | ⚠️ Sin datos: no hubo Story Points ni seguimiento diario (no se genera gráfico) |
| Reportes individuales de contribución | ⏳ Pendiente por integrante |
| [Evidencias técnicas](evidencias/README.md) | ✅ Indexadas |

## Pendientes al cierre

1. **Reportes individuales de contribución** — cada integrante debe
   aportar el suyo (no hay datos en el repositorio para redactarlos).
2. **Reparto de responsables por historia** en el backlog — solo está
   confirmada la responsabilidad general por área
   ([equipo-scrum](../gestion-del-proyecto/equipo-scrum.md)).
3. **Burndown** — imposible de construir sin Story Points ni registros
   diarios; queda documentada la limitación.
4. **Sprint 2** — frontend (Marina, Sebastián) pendiente de planificación;
   ver [docs/sprint-2](../sprint-2/README.md).

## Seguridad verificada al cierre

- `.env` excluido de Git (`.gitignore:13`), nunca trackeado ni en el
  historial; sin cambios (mtime 2026-10-29).
- `.env.example` no está trackeado; valores de ejemplo (la contraseña real
  de Neon ya fue rotada, confirmado por el responsable del proyecto).
- 0 credenciales, hosts reales o claves privadas en la documentación
  (barrido por patrones, solo conteos).
