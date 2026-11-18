# Sprint 1 — Evidencias técnicas

> Índice de evidencias verificables que respaldan el cierre del Sprint 1.
> Solo se enlazan documentos existentes (sin duplicar contenido); cada
> evidencia indica qué respalda y cuándo fue verificada.

## Evidencias del repositorio y GitHub

| Evidencia | Qué respalda | Verificación |
|---|---|---|
| Commit `1c6e0f3` (50 archivos, +3376 líneas) | Entrega completa del Sprint 1 | `git show 1c6e0f3` — 2026-11-02 |
| Push a `origin/Dev/Noe-Mejia` | Publicación de la rama individual | `git ls-remote` / `git log origin/Dev/Noe-Mejia` — 2026-11-02 |
| [PR #1 "Sprint 1 - Backend de Punto y Sal"](https://github.com/ProyectoIngSoftware2/Backend/pull/1) | Integración por flujo de ramas y PR hacia `development` | GitHub: fusionado 2026-11-03, merge commit `91e071a` (2 commits) |
| Historial `origin/development` = `91e071a` | El commit del Sprint 1 forma parte de `development` | `git merge-base --is-ancestor 1c6e0f3 origin/development` → verdadero (tras `git fetch origin`, 2026-11-03) |
| Historial preservado (`3e018c8`, `7b40f81` de davidavila1-web) | Commits de compañeros intactos | `git log` |

## Evidencias de pruebas

| Evidencia | Resultado | Documento |
|---|---|---|
| Suite unitaria (2026-11-03) | **39 passed, 6 skipped** | [test-results.md](../test-results.md) |
| Suite de integración opt-in, solo lectura (2026-11-03) | **6 passed** | [test-results.md](../test-results.md) |
| `pip check` | Sin dependencias rotas | verificado en la auditoría 2026-11-03 |
| End-to-end por Gateway (2026-11-03) | 4 rutas HTTP 200 con filas: clientes 3, reservas 2, mesas 4, platillos 5 | verificado en la auditoría 2026-11-03 |

## Evidencias de Docker

| Evidencia | Resultado | Documento |
|---|---|---|
| `docker compose ps` (2026-11-03) | **4/4 contenedores healthy** (gateway, clientes, reservas, catalogo) | [test-results.md](../test-results.md) §4 |
| `/health` y `/health/services` | Gateway ok; downstream: clientes/reservas/catalogo ok | verificado en la auditoría 2026-11-03 |

## Evidencias de base de datos

| Evidencia | Resultado | Documento |
|---|---|---|
| 8 tablas aprobadas, constraints, función y triggers | Verificados solo lectura | [database-verification.md](../database-verification.md) |
| Datos de prueba (autorización del equipo, 2026-11-01) | 22 filas insertadas; re-ejecución idempotente insertó 0 | [test-results.md](../test-results.md) §5 |
| Integridad del esquema (2026-11-03) | 8 tablas, 23 índices, 8 triggers, `generar_codigo_reserva()` presente | verificado en la auditoría 2026-11-03 |

## Evidencias de decisiones técnicas

| Evidencia | Documento |
|---|---|
| Registro de decisiones F-01…F-07 (F-01 aprobada) | [design-change-log.md](../design-change-log.md) |
| Arquitectura, mapa de rutas y layout | [architecture.md](../architecture.md) |
| Checklist técnico con evidencia por ítem | [technical-checklist.md](../technical-checklist.md) |
| Aceptación del equipo (2026-11-03) | [sprint-review.md](../sprint-review.md) |

## Evidencias de seguridad

| Evidencia | Resultado |
|---|---|
| `.env` ignorado por Git | `.gitignore:13` (`git check-ignore`) |
| `.env` nunca trackeado ni en historial | 0 coincidencias en `git ls-files` y `git log --all` |
| `.env.example` no trackeado | 0 (excluido del commit del Sprint 1) |
| Secretos en documentación (barrido por patrones) | 0 archivos con cadenas de conexión, hosts reales o claves privadas |

## Dato faltante

- No hay capturas de pantalla ni artefactos de CI (el proyecto no tiene
  integración continua configurada). Las verificaciones son de ejecución
  local y se registraron en `test-results.md`.
