# SoftOS Claude Code Context

Use this file as the operational contract for Claude Code in this workspace.

## Command harness (mandatory)

- `specs/**` is the source of truth.
- `.flow/**` is operational state only.
- Run workspace-managed commands in devcontainer via `python3 ./flow workspace exec -- <cmd>` or `scripts/workspace_exec.sh <cmd>`.
- Host `flow` execution is blocked by default (`FLOW_FORCE_WORKSPACE_EXEC=1`) unless using `flow stack ...` or explicit `flow workspace exec -- ...`.
- Keep host execution only for `flow stack ...` and explicit `flow workspace exec -- ...`.
- Run repo runtime commands in repo services with `python3 ./flow repo exec <repo> -- <cmd>`.

## Required context loading

- `AGENTS.md`
- `CURSOR.md`
- `OPENCODE.md`
- `.cursor/rules/softos.mdc`
- `.cursor/rules/softos-enforcement.mdc`
