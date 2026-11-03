# Sprint 1 Documentation

This folder collects the required Sprint 1 artifacts for the Punto y Sal
backend. Content was produced on **2026-11-01** from actual verification of
the repository and the live database. Fields that require human input
(meetings, dates, GitHub activity, individual contributions) are marked
**Pending** — they are never fabricated.

## Artifact index

| #  | Artifact                                                       | Status                                                   |
|----|----------------------------------------------------------------|----------------------------------------------------------|
| 1  | [Sprint Goal](sprint-goal.md)                                  | ✅ Written                                               |
| 2  | [Sprint Backlog](sprint-backlog.md)                            | ✅ Stories/tasks written; owners/points marked Pending   |
| 3  | User stories and tasks                                         | ✅ Included in the Sprint Backlog                        |
| 4  | Responsibility assignments                                     | ⏳ Pending (team must assign owners)                     |
| 5  | [Architecture description](architecture.md)                    | ✅ Written                                               |
| 6  | [Testing evidence](test-results.md)                            | ✅ Real results recorded                                |
| 7  | [Daily Scrum records](daily-scrum.md)                          | ⏳ Template only — no meetings invented                  |
| 8  | [Sprint Review](sprint-review.md)                              | ⏳ Template — review event pending                       |
| 9  | [Sprint Retrospective](sprint-retrospective.md)                | ⏳ Template — retrospective event pending                |
| 10 | Individual contribution report                                 | ⏳ Pending per team member                               |
| +  | [Database verification](database-verification.md)              | ✅ Real read-only results recorded                       |
| +  | [Technical checklist](technical-checklist.md)                  | ✅ Verified items marked with evidence                   |
| +  | [Burndown data](burndown.md)                                   | ⏳ Template — no sprint dates invented                   |
| +  | [GitHub evidence checklist](github-evidence.md)                | ⏳ Pending — no pushes/PRs were made by this task        |
| +  | [Design change log](design-change-log.md)                      | ✅ Log of preparation-stage changes                     |

## Key facts for this sprint

- Repository: `Dev/Noe-Mejia` branch; nothing was committed or pushed.
- Branch decision (2026-11-01): **`development` is the team's integration
  branch** (authorized); the official guideline specifies `develop` — no
  branches were renamed or created (see [architecture.md](architecture.md)).
- Database: eight approved tables verified read-only; test data inserted
  2026-11-01 with team authorization (22 rows, idempotent re-run safe); no
  schema change executed.
- Code: three microservices + API Gateway + shared module implemented;
  **39 automated tests passing (39 unit incl. 6 opt-in skips, + 6 live
  integration)** — see [test-results.md](test-results.md) for exact reruns.
- **F-01 APPROVED (2026-11-01):** reservas resolves dish names from
  catalogo over HTTP; verified live against inserted test data
  (see [design-change-log.md](design-change-log.md)).
- Docker: **executed and verified 2026-11-01** — images built, 4/4
  containers healthy, health/routing/Swagger/controlled-failure checks
  passed (see [test-results.md](test-results.md) §4).
- Root `app/`: **preserved unchanged** as legacy/compatibility; the three
  services under `services/` are the official Sprint 1 microservices
  (decision in [architecture.md](architecture.md)).

## Conventions

- New technical code, identifiers and documentation in English.
- User-facing API messages may remain in Spanish.
- Database identifiers remain in Spanish to preserve the existing schema.
- Never record secrets, `.env` contents or real credentials in this folder.
