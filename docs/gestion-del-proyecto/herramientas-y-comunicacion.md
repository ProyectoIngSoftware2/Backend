# Herramientas y comunicación — Punto y Sal

> Fuente: información confirmada por el equipo (2026-11-03) y evidencia
> observable del repositorio. Se distingue entre lo confirmado y lo
> inferido de la evidencia técnica.

## Comunicación y seguimiento (confirmado)

- **No se realizaron reuniones Daily Scrum formales** durante el Sprint 1.
- El equipo se comunicaba mediante **chat** para:
  - consultar avances de la base de datos y GitHub;
  - preguntar qué actividades faltaban;
  - identificar dónde se necesitaba ayuda;
  - coordinar las actividades.
- **No se utilizó una herramienta formal de gestión de tareas** (Trello,
  Jira, GitHub Projects u otra). La distribución y el seguimiento se
  realizaron mediante conversaciones.

> Estas conversaciones **no** deben presentarse como reuniones Daily Scrum.
> Ver [herramientas de registro](../sprint-1/daily-scrum.md).

## Reuniones puntuales por Discord (confirmado)

| Fecha | Participantes | Tema |
|---|---|---|
| 2026-10-30 | Noé, David | Revisión de código, base de datos y GitHub; David explicó el uso del repositorio y las ramas individuales |
| 2026-11-02 | Noé, David | Revisión de la rama individual de Noé y resolución de permisos de escritura de GitHub |

Detalle completo: [registro de actividades](../sprint-1/registro-actividades.md).

## Herramientas del proyecto (evidencia del repositorio)

| Herramienta | Uso | Evidencia |
|---|---|---|
| Git / GitHub | Control de versiones, ramas individuales, integración por PR | `git log`, PR #1 |
| Python + FastAPI | Microservicios y gateway | `services/`, `gateway/` |
| PostgreSQL (NeonDB) | Base de datos de 8 tablas aprobadas | `docs/sprint-1/database-verification.md` |
| Docker Compose | Orquestación de 4 contenedores | `docker-compose.yml` |
| pytest | Pruebas unitarias y de integración (opt-in) | `docs/sprint-1/test-results.md` |
| Discord | Coordinación puntual del equipo | registro de actividades |
| Chat (plataforma no especificada) | Coordinación diaria asíncrona | información del equipo |

> Dato faltante: no se registró qué plataforma específica se usó para el
> chat diario (solo se confirmó "chat" y "Discord" para las reuniones).

## Documentación del proyecto

- Documentación técnica del Sprint 1: [`docs/sprint-1/`](../sprint-1/README.md).
- Gestión del proyecto (esta carpeta): equipo, acuerdos y comunicación.
- Evidencias técnicas: [`docs/sprint-1/evidencias/`](../sprint-1/evidencias/README.md).
