# Workflow Next Step: 2026-09-10-backend-owned-temporal-projection-contract

- Stage: `verification`
- Spec: `specs/features/plg/2026-09-10-backend-owned-temporal-projection-contract.spec.md`
- Frontmatter status: `approved`
- State status: `slice-started`

## Summary

Las slices ya tienen worktrees; el siguiente paso es verificar cada slice y cerrar CI.

## Recommended BMAD workflow

- `quick-dev`: `_bmad/bmm/workflows/bmad-quick-flow/quick-dev/workflow.md`
- Why: Cada slice ya puede delegarse a un ejecutor con contexto cerrado.

## Next flow commands

- `python3 ./flow slice verify 2026-09-10-backend-owned-temporal-projection-contract backend-broader-schedule-surfaces --json`
- `python3 ./flow slice verify 2026-09-10-backend-owned-temporal-projection-contract dashboard-render-backend-temporal-fields --json`
- `python3 ./flow slice verify 2026-09-10-backend-owned-temporal-projection-contract hub-render-backend-temporal-fields --json`
- `python3 ./flow slice verify 2026-09-10-backend-owned-temporal-projection-contract temporal-contract-integration-review --json`
- `python3 ./flow ci spec 2026-09-10-backend-owned-temporal-projection-contract --json`
- `python3 ./flow ci repo --all --json`

## Suggested subagents

- `backend-temporal-projection-core` -> repo=`plg-platform-backend`, worktree=`/workspace/.worktrees/plg-platform-backend-2026-09-10-backend-owned-temporal-projection-contract-backend-temporal-projection-core`, started=no, workflow=`_bmad/bmm/workflows/bmad-quick-flow/quick-dev/workflow.md`
- `diagnostic-class-backend-contract` -> repo=`plg-platform-backend`, worktree=`/workspace/.worktrees/plg-platform-backend-2026-09-10-backend-owned-temporal-projection-contract-diagnostic-class-backend-contract`, started=no, workflow=`_bmad/bmm/workflows/bmad-quick-flow/quick-dev/workflow.md`
- `backend-broader-schedule-surfaces` -> repo=`plg-platform-backend`, worktree=`/workspace/.worktrees/plg-platform-backend-2026-09-10-backend-owned-temporal-projection-contract-backend-broader-schedule-surfaces`, started=yes, workflow=`_bmad/bmm/workflows/bmad-quick-flow/quick-dev/workflow.md`
- `dashboard-render-backend-temporal-fields` -> repo=`dashboard-frontend`, worktree=`/workspace/.worktrees/dashboard-frontend-2026-09-10-backend-owned-temporal-projection-contract-dashboard-render-backend-temporal-fields`, started=yes, workflow=`_bmad/bmm/workflows/bmad-quick-flow/quick-dev/workflow.md`
- `hub-render-backend-temporal-fields` -> repo=`hub-frontend`, worktree=`/workspace/.worktrees/hub-frontend-2026-09-10-backend-owned-temporal-projection-contract-hub-render-backend-temporal-fields`, started=yes, workflow=`_bmad/bmm/workflows/bmad-quick-flow/quick-dev/workflow.md`
- `temporal-contract-integration-review` -> repo=`plg-platform-harness`, worktree=`/workspace/.worktrees/plg-platform-harness-2026-09-10-backend-owned-temporal-projection-contract-temporal-contract-integration-review`, started=yes, workflow=`_bmad/bmm/workflows/bmad-quick-flow/quick-dev/workflow.md`
