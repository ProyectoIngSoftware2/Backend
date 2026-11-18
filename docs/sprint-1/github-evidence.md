# GitHub Evidence Checklist — Sprint 1

> **Status: delivery evidence verified on 2026-11-03.** The Sprint 1 work
> was committed, pushed and integrated through a Pull Request. Per-member
> evidence that GitHub does not provide automatically is still pending.
> Do not claim evidence that has not been verified.

## Sprint 1 delivery (verified)

| Evidence | Value | How it was verified |
|----------|-------|---------------------|
| Personal branch on GitHub | `Dev/Noe-Mejia` → `origin/Dev/Noe-Mejia` = `1c6e0f3` | `git ls-remote origin` (2026-11-03) |
| Sprint 1 commit | `1c6e0f3b353f1de30ed9e3f694d7e71d85c34a15` — "feat(sprint-1): microservices backend, gateway, Docker and documentation" (50 files, +3376) | `git show 1c6e0f3` |
| Push to origin | Performed **2026-11-02** (together with the pre-existing `ec792e4`) | `git log origin/Dev/Noe-Mejia`, push record |
| Pull Request | **PR #1 "Sprint 1 - Backend de Punto y Sal"** — `Dev/Noe-Mejia` → `development`, 2 commits, opened by nmskydream | [github.com/…/pull/1](https://github.com/ProyectoIngSoftware2/Backend/pull/1) (2026-11-03) |
| PR merged | **Merged 2026-11-03** into `development`, merge commit `91e071a` | GitHub + `git log origin/development` after `git fetch origin` |
| Commit present in `development` | `git merge-base --is-ancestor 1c6e0f3 origin/development` → **true** | local verification 2026-11-03 |
| PR review | **No formal review recorded** ("No reviews" on GitHub); the team accepted the backend at the Sprint Review of 2026-11-03 | GitHub PR page + team confirmation |

## Per team member (still pending)

| Evidence | Where | Status |
|----------|-------|--------|
| Personal branch exists on GitHub | `github.com/ProyectoIngSoftware2/Backend` | ✅ Verified for `Dev/Noe-Mejia`; `Dev/David-Avila` exists on the remote |
| Sprint 1 work committed to personal branch | commit `1c6e0f3` | ✅ (Noé) · ⏳ per other members |
| Push to origin visible | `origin/Dev/Noe-Mejia` | ✅ (Noé) · ⏳ per other members |
| Pull Request to `development` created | PR #1 | ✅ (Noé, merged 2026-11-03) |
| PR reviewed / merged | PR #1 merged; **no formal review** | ✅ merged · ⏳ review evidence not available |
| Commits authored by me (≥ N quality commits) | `git log --format='%h %an %s'` | ⏳ Each member must attach their own list |
| Individual contribution report submitted | per member | ⏳ Pending (see [cierre-sprint-1](cierre-sprint-1.md)) |

## Commit history of the repository (read-only summary)

| Commit | Author | Date | Subject |
|--------|--------|------|---------|
| `3e018c8` | davidavila1-web | 2026-10-27 | feat: commit inicial del proyecto backend |
| `7b40f81` | davidavila1-web | 2026-10-27 | configuracion de venv, gitignore y fastapi |
| `ec792e4` | nmskydream | 2026-10-28 | chore: remove virtual environment from repository |
| `1c6e0f3` | nmskydream | 2026-11-02 | feat(sprint-1): microservices backend, gateway, Docker and documentation |
| `91e071a` | nmskydream | 2026-11-03 | Merge pull request #1 … into `development` |

## Notes

- The repository keeps `main` / `development` protected: merge only via PR
  (the Sprint 1 integration followed this flow).
- Branch naming decision (2026-11-01): the team authorized **`development`
  as the integration branch**; the official guideline specifies `develop`.
  No branches were renamed or created — do not "fix" this without team
  coordination.
- The suggested multi-commit grouping proposed earlier in this file was
  superseded by a single approved Sprint 1 commit (`1c6e0f3`); it is
  recorded here for traceability only.
