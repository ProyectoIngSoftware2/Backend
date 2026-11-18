# Design Decisions and Deviations — Sprint 3

## Technical baseline
The live implementation (BIGINT identifiers, 2 roles: administrador/cliente, reservation states: pendiente/aprobada/confirmada/rechazada/cancelada/completada) is used as the compatibility baseline. Design documents were not updated to match; deviations are recorded here.

## Deviations from design v1.0

| Element | Design v1.0 | Live implementation | Decision |
|---------|-------------|---------------------|----------|
| Primary key type | UUID | BIGINT identity | Use BIGINT to match live database |
| Roles | 3 (cliente, recepción, administrador) | 2 (cliente, administrador) | Keep 2 roles; recepción not implemented |
| Reservation states | SOLICITADA, CONFIRMADA, RECHAZADA, CANCELADA, COMPLETADA, NO_ASISTIO | pendiente, aprobada, confirmada, rechazada, cancelada, completada | Use live implementation vocabulary |
| Roles table | Exists (`roles` table) | Not in live DB | Created `roles` table via migration |
| API count | 11 APIs defined | 4 CRUD resources + auth | 2 new APIs added for Sprint 3 |

## Decisions made (engineering defaults)

1. **Preserve existing schema:** No destructive changes to live NeonDB. New tables use BIGINT.
2. **Keep 2 roles:** No `recepción` role added without explicit team/instructor decision.
3. **Preserve 4 existing CRUD resources:** Not removed or hidden to force artificial cumulative count.
4. **Horarios y bloqueos as one API grouping:** Per design catalog §7.1, counted as one API resource with two entity types.
5. **Detalle platillos as separate API:** Per design catalog §7.1, listed as separate row with complete CRUD.
6. **Prices from catalogo service:** Reservation dish details always source prices from catalogo over HTTP (F-01 rule), never from client.

## Items requiring instructor confirmation

1. Which design version is the approved baseline?
2. Does "4 APIs acumuladas" count the 4 existing CRUD resources?
3. Should the `recepción` role be implemented?
4. Does the buggy login prototype count as a functional screen?
