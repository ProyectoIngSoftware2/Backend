# Sprint 1 — Registro de actividades

> Fuente: información confirmada por el equipo (2026-11-03) y evidencia
> verificable del repositorio (historial de Git, PR #1). Cada entrada indica
> su origen. No se listan reuniones Daily Scrum: **no se realizaron
> reuniones Daily Scrum formales** (ver
> [daily-scrum.md](daily-scrum.md)).

## Cronología

| Fecha | Actividad | Participantes | Fuente |
|---|---|---|---|
| 2026-10-21 | Planificación inicial: Noé y David presentaron la propuesta de trabajo; el equipo la aceptó. Se definieron objetivo, alcance, división backend/frontend, responsabilidades, herramientas y colaboración. Sin Story Points ni estimaciones. | Los cuatro integrantes | Confirmación del equipo |
| 2026-10-22 → 2026-11-03 | Período de desarrollo del Sprint 1 (trabajo concentrado en backend). | Noé, David (backend) | Confirmación del equipo |
| 2026-10-27 | Commits iniciales del repositorio: proyecto base y configuración de entorno virtual. | David Ávila | `git log` (`3e018c8`, `7b40f81`) |
| 2026-10-28 | Limpieza del repositorio: eliminación del entorno virtual del repositorio. | Noé Mejía | `git log` (`ec792e4`) |
| 2026-10-30 | Reunión por Discord: revisión de código, base de datos y GitHub; David explicó a Noé el funcionamiento del repositorio y el trabajo con ramas individuales. | Noé, David | Confirmación del equipo |
| 2026-11-01 | Verificación técnica del Sprint 1: esquema de base de datos (8 tablas), inserción de datos de prueba autorizada por el equipo (22 filas), suite de pruebas, Docker (4/4 contenedores sanos) y aprobación de la decisión F-01 (nombres de platillos vía HTTP). | — (evidencia técnica) | `docs/sprint-1/test-results.md`, `design-change-log.md` |
| 2026-11-02 | Reunión por Discord: revisión de la rama individual de Noé y resolución de permisos de escritura de GitHub; David verificó avances y habilitó los permisos. | Noé, David | Confirmación del equipo |
| 2026-11-02 | Push de la rama `Dev/Noe-Mejia` con el commit del Sprint 1 (`1c6e0f3`, 50 archivos). | Noé Mejía | `git log`, `origin/Dev/Noe-Mejia` |
| 2026-11-03 | Los cuatro integrantes revisaron el resultado del Sprint 1: el backend fue aceptado y no se solicitaron correcciones adicionales. | Los cuatro integrantes | Confirmación del equipo (ver [sprint-review.md](sprint-review.md)) |
| 2026-11-03 | Marina informó a Noé sobre una investigación preliminar de tecnologías para el frontend y posibles formas de conexión con el backend. Conversación general, sin diseños ni decisiones técnicas definitivas. | Marina, Noé | Confirmación del equipo |
| 2026-11-03 | Integración mediante Pull Request: el PR #1 "Sprint 1 - Backend de Punto y Sal" (`Dev/Noe-Mejia` → `development`, 2 commits) fue fusionado en `development` (`91e071a`). | Noé Mejía (autor) | GitHub PR #1, `git log origin/development` |

## Observaciones de seguimiento (no son Daily Scrum)

La coordinación diaria ocurrió por chat de forma asíncrona (consultas de
avance, pendientes, ayuda y coordinación), sin reuniones formales ni
tablero de tareas. Ver
[herramientas y comunicación](../gestion-del-proyecto/herramientas-y-comunicacion.md).

## Dato faltante

- No hay registros diarios de trabajo pendiente (impide el
  [burndown](burndown.md)).
- No hay registro de actividades individuales de Marina y Sebastián durante
  el Sprint 1 (su trabajo de frontend está confirmado como pendiente para
  el Sprint 2, pero sin detalle de tareas).
