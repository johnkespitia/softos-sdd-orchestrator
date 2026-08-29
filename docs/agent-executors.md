# Agent executors

SoftOS registers host-native agent harnesses under the top-level `agents` section of `workspace.config.json`. V1 declares `codex`, `cursor`, and `opencode-local`; installing and authenticating those CLIs on WSL remains the operator's responsibility.

## Commands

Run these on the WSL host (they do not proxy into the workspace container):

```bash
python3 ./flow agent list
python3 ./flow agent doctor
python3 ./flow agent doctor codex
python3 ./flow agent run <executor> --repo <repo> --workdir <path> --prompt "<text>" --target <path>
```

- `agent list` validates the registry and prints each executor's id, adapter, and configured executable in lexical order.
- `agent doctor` resolves executables through host `PATH` (or checks absolute paths) and reports `ready` or `missing`. It does not inspect credentials or environment values.
- `agent run` validates repo/worktree/target boundaries, prefixes the operator prompt with the SoftOS execution contract, invokes the configured executable with an argv sequence (`shell=False`), captures stdout/stderr, and returns the exact child exit code. It does not persist prompts, captured output, environment values, or rendered argv.

All other normal `flow` commands remain workspace-only. Use `scripts/workspace_exec.sh python3 ./flow <command>` for the SoftOS control plane, `python3 ./flow repo exec <repo> --workdir <worktree> -- <command>` for repository runtimes inside the workspace container, and `python3 ./flow stack <command>` for Docker lifecycle.

## Registry shape

```json
{
  "agents": {
    "schema_version": 1,
    "executors": {
      "codex": {"adapter": "codex", "executable": "codex", "argv": []},
      "cursor": {"adapter": "cursor", "executable": "agent", "argv": []},
      "opencode-local": {"adapter": "opencode", "executable": "opencode", "argv": []}
    }
  }
}
```

Invalid registry fields exit non-zero with a field-specific diagnostic. Codex, Cursor, and OpenCode adapter execution is implemented in the `executor-adapters-and-tests` slice; `flow agent run` validates inputs but stops before launch for those adapters until that slice lands.

## Verification

```bash
scripts/workspace_exec.sh python3 ./flow ci integration --profile agent-executors --json
```
