# Acuerdos de trabajo del equipo — Punto y Sal

> Fuente: acuerdos definidos en la planificación del Sprint 1 (2026-10-21)
> y prácticas confirmadas por el equipo (2026-11-03). No se inventan
> acuerdos que no hayan sido confirmados.

## Acuerdos de la planificación (2026-10-21)

Durante la planificación inicial el equipo acordó:

1. **Objetivo del Sprint.**
2. **Alcance del trabajo.**
3. **División entre backend y frontend.**
4. **Responsabilidades de cada integrante** (ver
   [equipo-scrum.md](equipo-scrum.md)).
5. **Herramientas y forma general de colaboración** (ver
   [herramientas-y-comunicacion.md](herramientas-y-comunicacion.md)).

La propuesta de trabajo fue elaborada inicialmente por Noé y David y
presentada al equipo, que estuvo de acuerdo con el plan.

## Acuerdos confirmados sobre estimación

- **No se asignaron Story Points.**
- **No se asignaron estimaciones de tiempo.**

Por lo tanto, cualquier documento de este repositorio que muestre puntos o
estimaciones como "pendientes" debe leerse como **"no asignados"** (decisión
del equipo), no como una tarea olvidada.

## Flujo de ramas e integración (confirmado)

- Cada desarrollador con rama individual (`Dev/Noe-Mejia`, `Dev/David-Avila`).
- `development` es la rama de integración del equipo.
- Los cambios llegan a `development` mediante Pull Requests (verificado con
  el PR #1 del Sprint 1).
- `main` permanece como rama estable.

> Nota: la guía oficial del curso especifica `develop`; el equipo usa
> `development` tal cual (decisión registrada, sin renombrar ramas).

## Acuerdos sobre documentación

- Documentación técnica y código nuevos en inglés; mensajes de API al
  usuario pueden ir en español; identificadores de base de datos en español
  (para no alterar el esquema existente).
- **Nunca** registrar secretos, contenidos de `.env` ni credenciales
  reales en la documentación.
- Los datos de Scrum (reuniones, estimaciones, resultados) solo se
  documentan si fueron confirmados por el equipo; lo no registrado se
  marca explícitamente como dato faltante.

## Acuerdos de seguridad de Git (verificados)

- `.env` está excluido de Git (`.gitignore:13`); nunca ha estado trackeado
  ni en el historial (verificado con `git check-ignore`, `git ls-files` y
  `git log --all -- .env`).
- `.env.example` no está trackeado en el repositorio; sus valores son datos
  de ejemplo (la contraseña real de Neon ya fue rotada, confirmado por el
  responsable del proyecto).
- Sin autorización expresa no se realizan commits, push ni operaciones Git
  que alteren historial o ramas.
