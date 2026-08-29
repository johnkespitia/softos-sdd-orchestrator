# Agent executors

SoftOS registers host-native agent harnesses under the top-level `agents` section of `workspace.config.json`. V1 declares `codex`, `cursor`, and `opencode-local`.

## Host prerequisites

Install, authenticate, and configure each CLI on the WSL host before using `flow agent run`:

- **Codex CLI** (`codex`): operator installs and authenticates Codex on WSL.
- **Cursor Agent CLI** (`agent`): operator installs Cursor CLI and signs in on WSL.
- **OpenCode CLI** (`opencode`): operator installs OpenCode and configures provider/model selection in OpenCode itself.

SoftOS does not install CLIs, mount credentials, validate authentication, or select models/providers. `flow agent doctor` checks only that the configured executable resolves on the host (`PATH` lookup or an absolute executable file). A `ready` status does not mean credentials are valid.

## WSL host vs Docker control plane

Agent harness CLIs always run on the WSL host, never inside the workspace container.

| Command family | Where it runs |
| --- | --- |
| `python3 ./flow agent ...` | WSL host |
| `scripts/workspace_exec.sh python3 ./flow <command>` | Workspace container (control plane) |
| `python3 ./flow repo exec <repo> --workdir <worktree> -- <command>` | Repository runtime in container |
| `python3 ./flow stack <command>` | Docker lifecycle from host |

Repository runtime instructions are embedded in the SoftOS execution contract delivered to each harness. SoftOS does not run repository build/test commands on the host on an agent's behalf.

## Commands

Run these on the WSL host (they do not proxy into the workspace container):

```bash
python3 ./flow agent list
python3 ./flow agent doctor
python3 ./flow agent doctor codex
python3 ./flow agent run <executor> --repo <repo> --workdir <path> --prompt "<text>" --target <path>
```

### Examples

```bash
# List configured executors
python3 ./flow agent list

# Check whether host executables resolve
python3 ./flow agent doctor

# Run Codex against a worktree with one target file
python3 ./flow agent run codex \
  --repo softos-agentic \
  --workdir /path/to/worktree \
  --prompt "Implement the requested change" \
  --target src/example.py

# Run Cursor Agent CLI in the repo root
python3 ./flow agent run cursor \
  --repo workspace-root \
  --workdir /path/to/repo \
  --prompt "Review the diff" \
  --target .

# Run OpenCode locally (provider/model come from OpenCode config)
python3 ./flow agent run opencode-local \
  --repo softos-agentic \
  --workdir /path/to/worktree \
  --prompt "Add tests for the adapter" \
  --target flowctl/agent_executor_adapters.py
```

- `agent list` validates the registry and prints each executor's id, adapter, and configured executable in lexical order.
- `agent doctor` resolves executables through host `PATH` (or checks absolute paths) and reports `ready` or `missing`. It does not inspect credentials, call vendor APIs, or prove authentication works.
- `agent run` validates repo/worktree/target boundaries, prefixes the operator prompt with the SoftOS execution contract, invokes the configured executable with an argv sequence (`shell=False`), captures stdout/stderr, and returns the exact child exit code. It does not persist prompts, captured output, environment values, or rendered argv.

All other normal `flow` commands remain workspace-only.

## Adapter command shapes

SoftOS builds argv deterministically from the registry entry. Static `executor.argv` values are validated with a conservative allow-by-known-safe-options policy before launch; empty `argv` arrays are canonical in V1. Unsafe structural tokens (subcommands, `--help`, `--version`, `--`, adapter-owned flags, model/provider routing flags, and positional text) are rejected deterministically and never echoed in diagnostics.

The complete SoftOS execution contract plus the unchanged user prompt is always one discrete final argv element (`<PROMPT>` below). Positional-prompt CLIs use the parser-supported end-of-options delimiter `--` so contract markers beginning with `---` cannot be parsed as flags.

| Adapter | Registry executable | argv shape |
| --- | --- | --- |
| `codex` | `codex` | `codex [<validated static argv>] exec --approve-for-me -- <PROMPT>` |
| `cursor` | `agent` | `agent [<validated static argv>] --trust -p -- <PROMPT>` |
| `opencode` | `opencode` | `opencode [<validated static argv>] run --auto -- <PROMPT>` |

SoftOS never adds `--model`, `--provider`, `--full-auto`, or similar vendor routing flags. Arbitrary static argv is not supported; only explicitly reviewed global options that do not alter adapter-owned execution semantics may be allowlisted per adapter. Subprocess `cwd` is the validated workdir; adapters do not create worktrees or run Docker.

### Static argv policy (V1)

- Canonical registry entries use `"argv": []`.
- SoftOS validates static argv before building the final invocation and rejects unsafe tokens instead of silently dropping or reordering them.
- Rejected categories include subcommands (`exec`, `run`), help/version flags, `--`, adapter-owned approval/trust/prompt/auto flags, model/provider selection flags, and positional arguments.
- Diagnostics name the adapter and failure class only; secret-bearing argv values are never echoed.

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

Invalid registry fields exit non-zero with a field-specific diagnostic.

## Troubleshooting

| Symptom | Likely cause | What to check |
| --- | --- | --- |
| `doctor` reports `missing` | Executable not on host `PATH` or absolute path not executable | Install the CLI on WSL; confirm `which codex` / `which agent` / `which opencode` |
| `doctor` is `ready` but run fails inside vendor CLI | Authentication or vendor config | Re-authenticate outside SoftOS; SoftOS does not validate credentials |
| `Executor desconocido` | Registry ID typo | `flow agent list` |
| Workdir/target errors | Path outside assigned repo/worktree | Use a registered repo root or Git worktree; keep targets inside workdir |
| Non-zero exit with stdout/stderr | Child harness failed | Inspect forwarded streams; SoftOS returns the exact child exit code |
| Control-plane command blocked on host | Non-agent `flow` commands are workspace-only | Use `scripts/workspace_exec.sh python3 ./flow <command>` |

## Verification

```bash
scripts/workspace_exec.sh python3 ./flow ci integration --profile agent-executors --json
```
