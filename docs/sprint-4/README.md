# Sprint 4 — README

## Contenido

| Archivo | Descripción |
|---------|-------------|
| `cierre-sprint-4.md` | Cierre del sprint: logros, estado de los gaps G1–G7 e integración |
| `api-inventory.md` | Inventario de las 5 APIs acumuladas enrutadas por el Gateway (incluye `/api/v1/disponibilidad` y `/api/v1/reportes`) |
| `test-results.md` | Resultados de pytest, verificación de enrutamiento por Gateway y validación RBAC / anti-IDOR |

Fuera de esta carpeta, entregable asociado del Sprint 4:

| Archivo | Descripción |
|---------|-------------|
| [`../postman/PuntoYSal-Sprint4.postman_collection.json`](../postman/PuntoYSal-Sprint4.postman_collection.json) | Colección Postman v2.1.0 (31 requests, 8 grupos) — cierre del gap **G7** |

## Resumen del sprint

- **Fecha de ejecución/verificación:** 2026-11-17
- **Rama:** `Dev/David-Avila` (cambios en el working tree, sin commit — el commit lo realiza el equipo)
- **Gaps cerrados:** G4 (reportes), G5 (`DELETE /api/v1/roles/{id}`), G6 (disponibilidad), G7 (Postman)
- **Gaps pendientes:** G1, G2, G3 — requieren DDL de triggers en la base de datos con aprobación
  del equipo; mitigaciones documentadas en
  [cierre-sprint-4.md](cierre-sprint-4.md)
- **Suite de pruebas:** 260 passed, 17 skipped, 1 failed (falla preexistente dependiente del
  entorno, ver [test-results.md](test-results.md)); `pip check` limpio

## Convenciones

- Documentación técnica en inglés; textos de cierre en español (consistencia con sprints previos).
- Nunca se registran secretos, contenidos de `.env` ni credenciales reales en esta carpeta
  (las contraseñas de prueba viven solo en el entorno local del equipo).
