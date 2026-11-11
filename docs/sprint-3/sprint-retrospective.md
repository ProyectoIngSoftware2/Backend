# Sprint Retrospective — Sprint 3 (Template)

**Fecha:** 11 de noviembre de 2026
**Facilitador:** Equipo Punto y Sal

## ¿Qué salió bien?

- El backend de Sprint 2 estaba sólido y funcionando (JWT, bcrypt, 4 CRUD recursos, CI verde).
- Se implementaron los 2 nuevos recursos API requeridos para Sprint 3.
- Se corrigieron los bugs del login (rol/role, redirecciones).
- Se creó documentación completa de Sprint 3.

## ¿Qué se puede mejorar?

- La migración de base de datos debe aplicarse antes de que los nuevos APIs funcionen en producción.
- Se necesitan pruebas unitarias específicas para los nuevos endpoints.
- La evidencia de GitHub (pushes, PRs, revisiones entre pares) debe completarse para todos los miembros.
- Se necesita configurar CORS con el origen real del frontend.

## Acciones para el próximo sprint

1. Aplicar migración `database/sprint3_core_tables.sql` a la base de datos.
2. Agregar pruebas unitarias para horarios, bloqueos, usuarios, roles y detalle de platillos.
3. Configurar CORS con el origen de frontend confirmado.
4. Completar evidencia de GitHub para todos los miembros del equipo.
5. Implementar las pantallas restantes del diseño (mesas, platillos, reportes).

## Preguntas sin resolver

- ¿Cuál es la versión aprobada del documento de diseño?
- ¿Cuántas APIs cuentan hacia el acumulado de 4 en Sprint 3?
- ¿Se implementa el rol de recepción?
