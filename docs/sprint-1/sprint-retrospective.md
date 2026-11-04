# Sprint Retrospective — Sprint 1

> **Status: content confirmed by the team.** The retrospective began as a
> personal reflection by Noé, who shared it with the team; the four members
> agreed with it. **This was not a formal facilitated meeting** — no Scrum
> Master was designated and no meeting date was recorded. Do not present it
> as a formal event that did not occur.

## Event

| Field | Value |
|---|---|
| Date | Not recorded in the team's information; the reflection was shared with the team and accepted by all four members |
| Participants | All four team members (agreed with the reflection) |
| Origin | Personal reflection by Noé Mejía, shared with the team |
| Facilitator | None designated (no Scrum Master — see [equipo-scrum](../gestion-del-proyecto/equipo-scrum.md)) |

> Dato faltante: fecha exacta de la retrospectiva y si hubo una reunión
> posterior para tratarla. No se inventa.

## What went well (confirmed)

| # | Item |
|---|------|
| 1 | Backend developed and integrated (PR #1 merged into `development`) |
| 2 | Organization of individual branches |
| 3 | Integration through Pull Requests |
| 4 | Communication and support among members |

## What did not go well (confirmed)

| # | Item |
|---|------|
| 1 | Time required to complete the activities |
| 2 | GitHub permissions |
| 3 | Cleaning and organization of files to work locally |

## Improvements proposed (confirmed; owners and due dates not assigned)

| # | Improvement |
|---|-------------|
| 1 | Keep more constant communication |
| 2 | Improve synchronization |
| 3 | Coordinate activities in advance |
| 4 | Better organization and tracking of tasks |

> These observations were proposed by Noé and accepted by all four members.
> No owners or due dates were recorded — do not assign them retroactively.

## Process observations (factual, updated 2026-11-03)

- Docker **was executed and verified** on 2026-11-01 (4/4 containers
  healthy) — earlier drafts of this template said it was unavailable; that
  is now resolved (see [test-results.md](test-results.md) §4).
- The `venv/` directory had been committed by mistake in an earlier commit;
  it was later untracked (commit `ec792e4`) but remains in Git history,
  which makes the repository heavy to clone.
- Branch naming differs from the official document (`development` vs
  `develop`); the team decision to keep `development` is recorded in
  [architecture.md](architecture.md).
- Test-data insertion **was completed** on 2026-11-01 with team
  authorization (22 rows, idempotent) — the approval blocker is resolved.
- No formal Daily Scrum or task board was used; coordination happened by
  chat and point-meetings on Discord (2026-10-30, 2026-11-02).
