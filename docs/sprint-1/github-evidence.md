# GitHub Individual Evidence Checklist

> **Status: pending.** The Sprint 1 implementation in this repository has
> **not been committed or pushed** (safety rule: no Git mutations without
> authorization). Each team member must complete this checklist with their
> own real evidence. Do not claim pushes, pull requests or reviews that
> have not happened.

## Per team member

| Evidence | Where | Status |
|----------|-------|--------|
| Personal branch exists on GitHub | `github.com/ProyectoIngSoftware2/Backend` | ⏳ Verify |
| Sprint 1 work committed to personal branch | link to commit(s) | ⏳ Pending (working tree not committed yet) |
| Push to origin visible | link to branch | ⏳ Pending |
| Pull Request to `development` created | link to PR | ⏳ Pending |
| PR reviewed / merged | link | ⏳ Pending |
| Commits authored by me (>= N quality commits) | link | ⏳ Pending |
| Individual contribution report submitted | [folder] | ⏳ Pending |

## Commit guidance for the pending commit (suggested grouping)

When the team authorizes committing the current working tree, consider
logical commits such as:

1. `feat(services): add clientes, reservas and catalogo microservices`
2. `feat(gateway): add API Gateway with HTTP routing and health aggregation`
3. `feat(shared): add shared database module and helpers`
4. `feat(docker): add Dockerfiles, docker-compose and .dockerignore`
5. `test: add pytest suite (unit + live integration)`
6. `docs(sprint-1): add Sprint 1 documentation and database scripts`

## Notes

- The repository must keep `main` / `development` protected: merge only via PR.
- Branch naming decision (2026-11-01): the team authorized **`development`
  as the integration branch**; the official guideline specifies `develop`.
  No branches were renamed or created — do not "fix" this without team
  coordination.
