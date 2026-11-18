# Sprint 1 Documentation

This folder collects the required Sprint 1 artifacts for the Punto y Sal
backend. Technical content was produced from actual verification of the
repository and the live database (2026-11-01, re-verified 2026-11-03);
Scrum management content is based on information confirmed by the team
(2026-11-03). Fields with no confirmed data are marked explicitly as
**missing data** — they are never fabricated.

## Artifact index

| #  | Artifact                                                       | Status                                                   |
|----|----------------------------------------------------------------|----------------------------------------------------------|
| 1  | [Sprint Goal](sprint-goal.md)                                  | ✅ Confirmed at planning (2026-10-21)                     |
| 2  | [Sprint Planning](sprint-planning.md)                          | ✅ Registered (2026-10-21)                                |
| 3  | [Sprint Backlog](sprint-backlog.md)                            | ✅ Stories/tasks; general owners recorded, individual split pending; points not assigned |
| 4  | [Responsibility assignments](../gestion-del-proyecto/equipo-scrum.md) | ✅ General responsibilities confirmed (per-story split pending) |
| 5  | [Architecture description](architecture.md)                    | ✅ Written                                               |
| 6  | [Testing evidence](test-results.md)                            | ✅ Real results recorded (re-run 2026-11-03)              |
| 7  | [Activity log](registro-actividades.md)                        | ✅ Registered — confirmed activities + Git evidence       |
| 8  | [Daily Scrum records](daily-scrum.md)                          | ✅ Confirmed: **no formal Daily Scrum held** (nothing invented) |
| 9  | [Sprint Review](sprint-review.md)                              | ✅ Held 2026-11-03 — backend accepted                     |
| 10 | [Sprint Retrospective](sprint-retrospective.md)                | ✅ Content confirmed (Noé's reflection, agreed by the team) |
| 11 | [Burndown](burndown.md)                                        | ⚠️ No data (no Story Points, no daily tracking) — no chart generated |
| 12 | [Sprint closure](cierre-sprint-1.md)                           | ✅ Closed 2026-11-03                                      |
| 13 | Individual contribution report                                 | ⏳ Pending per team member (missing data)                 |
| +  | [Database verification](database-verification.md)              | ✅ Real read-only results recorded                       |
| +  | [Technical checklist](technical-checklist.md)                  | ✅ Verified items marked with evidence                   |
| +  | [GitHub evidence checklist](github-evidence.md)                | ✅ Commit, push and PR #1 verified (2026-11-03)           |
| +  | [Design change log](design-change-log.md)                      | ✅ Log of preparation-stage changes                       |
| +  | [Technical evidence index](evidencias/README.md)               | ✅ Index of verifiable evidence for the closure           |

Project-level management documents (team, working agreements,
communication): [`docs/gestion-del-proyecto/`](../gestion-del-proyecto/equipo-scrum.md).

## Key facts for this sprint

- **Git delivery (verified 2026-11-03):** commit `1c6e0f3` (50 files,
  +3376) pushed to `origin/Dev/Noe-Mejia` on **2026-11-02**; **PR #1
  "Sprint 1 - Backend de Punto y Sal"** (`Dev/Noe-Mejia` → `development`)
  **merged 2026-11-03** (merge commit `91e071a`); `1c6e0f3` confirmed as
  part of `origin/development` after `git fetch origin`.
- Branch decision (2026-11-01): **`development` is the team's integration
  branch** (authorized); the official guideline specifies `develop` — no
  branches were renamed or created (see [architecture.md](architecture.md)).
- Database: eight approved tables verified read-only; test data inserted
  2026-11-01 with team authorization (22 rows, idempotent re-run safe); no
  schema change executed.
- Code: three microservices + API Gateway + shared module implemented;
  **39 unit + 6 live integration tests passing** (re-run **2026-11-03**) —
  see [test-results.md](test-results.md).
- **F-01 APPROVED (2026-11-01):** reservas resolves dish names from
  catalogo over HTTP; verified live against inserted test data
  (see [design-change-log.md](design-change-log.md)).
- Docker: **4/4 containers healthy** (verified 2026-11-01 and re-checked
  2026-11-03; see [test-results.md](test-results.md) §4).
- Root `app/`: **preserved unchanged** as legacy/compatibility; the three
  services under `services/` are the official Sprint 1 microservices
  (decision in [architecture.md](architecture.md)).
- **Sprint 1 accepted by the team on 2026-11-03** at the review; no
  additional corrections requested (see [sprint-review.md](sprint-review.md)).
- No formal Daily Scrum meetings and no Story Points/time estimates were
  used (confirmed team decisions — see [daily-scrum.md](daily-scrum.md) and
  [burndown.md](burndown.md)).

## Conventions

- New technical code, identifiers and documentation in English.
- User-facing API messages may remain in Spanish.
- Database identifiers remain in Spanish to preserve the existing schema.
- Never record secrets, `.env` contents or real credentials in this folder.
