# Sprint Review — Sprint 3 (Template)

**Fecha:** 11 de noviembre de 2026
**Presentado por:** Equipo Punto y Sal
**Asistentes:** Noé Mejía, David Ávila, Marina Valladares, Sebastián Rivera

## Resumen del sprint

Se implementaron los requisitos del Sprint 3: dos nuevos recursos API con CRUD completo (horarios y bloqueos, detalle de platillos de reserva), la API de usuarios y roles pendiente de Sprint 2, y cuatro pantallas funcionales conectadas al backend a través del API Gateway.

## Demostración

- [ ] Login funcional con JWT y redirección por rol
- [ ] Gestión de usuarios y roles (administrador)
- [ ] Gestión de horarios y bloqueos (administrador)
- [ ] Reserva del cliente con platillos (cliente)
- [ ] Documentación Swagger en Gateway /docs

## Lo que se completó

- API de usuarios y roles: CRUD completo, autenticación JWT, autorización por rol
- API de horarios y bloqueos: CRUD completo, validaciones de tiempo
- API de detalle de platillos de reserva: CRUD completo, precios desde catalogo
- Cuatro pantallas funcionales en el frontend
- Pruebas unitarias backend: 187 pasadas, 17 omitidas

## Lo que no se completó

- Migración SQL aplicada a la base de datos live NeonDB (preparada pero no ejecutada)
- Pruebas unitarias específicas para los nuevos endpoints
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
