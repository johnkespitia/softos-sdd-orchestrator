# Agent executors

Spanish mirror: [docs/es/agent-executors.es.md](./es/agent-executors.es.md)

SoftOS registers host-native agent harnesses under the top-level `agents` section of `workspace.config.json`. V1 declares `codex`, `cursor`, `opencode`, and `opencode-local`. ACP-capable executors may use `transport: "auto"` to prefer ACP and fall back to CLI before prompt submission.

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
python3 ./flow agent select --role orchestrator --json
python3 ./flow agent run <executor> --repo <repo> --workdir <path> --prompt "<text>" --target <path>
python3 ./flow agent run <executor> --repo <repo> --workdir <path> --prompt "<text>" --target <path> --transport acp
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
- `agent select --role orchestrator` selects the first available orchestration-capable executor from the model-agnostic priority list.
- `agent run` validates repo/worktree/target boundaries, prefixes the operator prompt with the SoftOS execution contract, invokes the configured transport with an argv sequence (`shell=False`), captures/streams stdout/stderr, emits metadata-only execution evidence, and returns the exact child exit code. It does not persist prompts, captured output, environment values, or rendered argv.

All other normal `flow` commands remain workspace-only.

## Runtime roles

Every run has a SoftOS-assigned role:

- `orchestrator` is the default for a standalone host invocation. It may read specs/plans, use BMAD/flow lifecycle commands, create worker/reviewer handoffs, and evaluate gates.
- `worker` executes one bounded handoff or Patch Unit. It cannot delegate, run BMAD/workflow orchestration, or expand scope.
- `reviewer` inspects an assigned diff/evidence package. It is independent and read-only by contract.

Workers and reviewers must provide `--run-id`, `--parent-run-id`, and `--handoff`. When `flow agent run` is executed inside an agent process, omitting `--role` defaults to `worker`, derives the parent from the current run identity, and requires a new handoff. An inherited child cannot request `--role orchestrator`. The role comes from SoftOS; prompt text cannot elevate a child run.

Example child run:

```bash
python3 ./flow agent run opencode-local \
  --role worker \
  --run-id run-123-pu-001 \
  --parent-run-id run-123 \
  --handoff .flow/reports/agent-handoffs/pu-001.json \
  --repo softos-agentic \
  --workdir /path/to/worktree \
  --prompt "Execute only the assigned Patch Unit" \
  --target flowctl/example.py
```

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
      "codex": {
        "adapter": "codex",
        "executable": "codex",
        "argv": [],
        "transport": "auto",
        "allow_cli_fallback": true,
        "permission_policy": "reject",
        "acp": {"executable": "codex-acp", "argv": []}
      },
      "cursor": {
        "adapter": "cursor",
        "executable": "agent",
        "argv": [],
        "transport": "auto",
        "allow_cli_fallback": true,
        "permission_policy": "reject",
        "acp": {"executable": "agent", "argv": ["acp"], "auth_method": "cursor_login"}
      },
      "opencode": {
        "adapter": "opencode",
        "executable": "opencode",
        "argv": [],
        "transport": "auto",
        "allow_cli_fallback": true,
        "permission_policy": "reject",
        "acp": {"executable": "opencode", "argv": ["acp"]}
      },
      "opencode-local": {
        "adapter": "opencode",
        "executable": "opencode-softos",
        "argv": [],
        "transport": "auto",
        "allow_cli_fallback": true,
        "permission_policy": "reject",
        "acp": {"executable": "opencode-softos", "argv": ["acp"]}
      }
    }
  }
}
```

Entries that omit `transport` retain the legacy CLI path. Supported transports are `cli`, `acp`, and `auto`; `auto` probes ACP first and falls back to CLI only before prompt submission when `allow_cli_fallback` is true. Invalid registry fields exit non-zero with a field-specific diagnostic.

`flow agent run` writes a `SOFTOS_EXECUTION_EVIDENCE` line to stderr with `transport_requested`, `transport_used`, `acp_session_id`, `fallback_reason`, normalized result, cancellation status, permission decisions, and failure class. See [ACP Executor Runtime V1](./acp-executor-runtime.md).

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
