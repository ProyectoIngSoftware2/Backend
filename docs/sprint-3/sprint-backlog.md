# Sprint Backlog — Sprint 3

## Historias de usuario seleccionadas (del Product Backlog del diseño)

| ID | Historia | Prioridad | Puntos | Responsable |
|----|----------|-----------|--------|-------------|
| HU-02 | Como administrador, quiero gestionar usuarios internos para controlar quién accede al sistema. | Must | 5 | Noé Mejía |
| HU-03 | Como administrador, quiero asignar roles para limitar las operaciones de cada usuario. | Must | 3 | Noé Mejía |
| HU-16 | Como administrador, quiero configurar horarios de operación para ofrecer reservas únicamente en franjas válidas. | Must | 5 | Noé Mejía |
| HU-07 | Como cliente, quiero asociar platillos a mi reserva para adelantar mis preferencias de consumo. | Could | 5 | Noé Mejía |

## Tareas de implementación

| Tarea | Descripción | Área | Estado | Responsable |
|-------|-------------|------|--------|-------------|
| T-01 | API de usuarios y roles (CRUD usuarios, roles) | Backend / clientes | Completado | Noé Mejía |
| T-02 | API de horarios y bloqueos (CRUD) | Backend / catalogo | Completado | Noé Mejía |
| T-03 | API de detalle de platillos de reserva (CRUD) | Backend / reservas | Completado | Noé Mejía |
| T-04 | Migración SQL para tablas horarios, bloqueos_horario, roles | Backend / database | Preparado (pendiente aplicación en DB) | Noé Mejía |
| T-05 | Corrección OpenAPI/Swagger en Gateway | Backend / gateway | Completado | Noé Mejía |
| T-06 | Corrección schema usuarios: eliminar nombre_completo (no pertenece a tabla usuarios) | Backend / clientes | Completado | Noé Mejía |
| T-07 | Corrección schema roles: validar rol contra CHECK constraint de BD | Backend / clientes | Completado | Noé Mejía |
| T-08 | Pruebas unitarias para nuevas APIs (43 pruebas) | Backend / tests | Completado | Noé Mejía |
| T-09 | Documentación Scrum (objetivo, backlog, tablero, burndown, dailies, review, retrospectiva) | Backend / docs | Parcial | Equipo |
| T-10 | Reportes individuales | Backend / docs | Parcial | Equipo |

## Estimación total

Puntos de historia comprometidos: 13 (Must: 13, Could: 5)
