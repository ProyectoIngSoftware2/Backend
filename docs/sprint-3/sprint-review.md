# Sprint Review — Sprint 3 (Template)

**Fecha:** 11 de noviembre de 2026
**Presentado por:** Equipo Punto y Sal
**Asistentes:** Noé Mejía, David Ávila, Marina Valladares, Sebastián Rivera

## Resumen del sprint

Se implementaron los requisitos del Sprint 3: **tres** nuevos recursos API con CRUD completo (usuarios y roles, horarios y bloqueos, detalle de platillos de reserva), conectados al API Gateway con autenticación JWT y autorización por rol.

## Demostración

- [x] Login funcional con JWT y redirección por rol
- [x] Gestión de usuarios y roles (administrador)
- [x] Gestión de horarios y bloqueos (administrador)
- [x] Reserva del cliente con platillos (cliente)
- [x] Documentación Swagger en Gateway `/docs`

## Lo que se completó

- API de usuarios y roles: CRUD completo, autenticación JWT, autorización por rol
- API de horarios y bloqueos: CRUD completo, validaciones de tiempo
- API de detalle de platillos de reserva: CRUD completo, precios desde catalogo
- Pruebas unitarias backend: 230 pasadas, 17 omitidas (incluyendo 43 nuevas para Sprint 3)

## Lo que no se completó

- Migración SQL aplicada a la base de datos live NeonDB (preparada pero no ejecutada)
- Configuración de CORS con origen de frontend confirmado
- Evidencia de GitHub: pushes en días diferentes para todos los miembros, PR individual para Marina y Sebastián, revisión entre pares para todos los miembros
- Documentación Scrum completa (burndown, dailies, actas de review y retrospectiva)
- Reportes individuales por integrante

## Impedimentos

- No se pudo aplicar la migración a la base de datos live sin credenciales de producción
- No se pudo confirmar el origen de desarrollo del frontend para CORS
- No se obtuvieron revisiones de PR de otros miembros del equipo

## Decisiones tomadas

- Se usaron identificadores BIGINT para nuevas tablas (coinciden con la BD live)
- Se mantuvieron los 2 roles existentes (administrador, cliente)
- Se preservaron los 4 recursos CRUD existentes sin modificarlos
- Se agregaron 3 nuevos recursos API: usuarios y roles, horarios y bloqueos, detalle de platillos de reserva
