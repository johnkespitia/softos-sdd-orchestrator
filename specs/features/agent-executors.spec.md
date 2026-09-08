---
schema_version: 3
name: "Agent Executors"
description: "Add host-native, model-agnostic agent executor registration, diagnostics, and bounded process execution."
status: approved
owner: platform
single_slice_reason: ""
multi_domain: false
phases: []
depends_on:
  - specs/000-foundation/spec-as-source-operating-model.spec.md
  - specs/000-foundation/repo-routing-and-worktree-orchestration.spec.md
  - specs/000-foundation/spec-driven-delivery-and-infrastructure.spec.md
required_runtimes: []
required_services: []
required_capabilities: []
stack_projects: []
stack_services: []
stack_capabilities: []
targets:
  - ../../flow
  - ../../flowctl/**
  - ../../workspace.config.json
  - ../../flowctl/tests/**
  - ../../docs/**
  - ../../specs/features/agent-executors.spec.md
---

# Agent Executors

## Objective

Add a first-class, model-agnostic executor layer that lets SoftOS invoke Codex CLI, Cursor Agent CLI, and OpenCode from the WSL host while the SoftOS control plane remains in Docker.

`codex`, `cursor`, and `opencode-local` identify harnesses/executors, not models. Orchestration must not depend on model names or provider-specific model semantics.

## Context and architecture decision

- Codex CLI, Cursor Agent CLI, and OpenCode are installed, authenticated, and configured by the operator on the WSL host.
- This feature must not install those CLIs in the workspace container or mount host credentials into it.
- Only the `flow agent` command family intentionally runs on the WSL host. Existing workspace-only enforcement remains unchanged for all normal SoftOS control-plane commands.
- Agents read and edit files directly in their assigned repository/worktree.
- Repository runtime commands use `python3 ./flow repo exec <repo> --workdir <worktree> -- <command>`.
- SoftOS control-plane commands use `scripts/workspace_exec.sh python3 ./flow <command>`.
- Docker lifecycle commands use `python3 ./flow stack <command>`.

No domain spec applies because this feature defines a workspace execution boundary and CLI capability, not a durable business entity. The declared foundations govern canonical specs, repo/worktree routing, and infrastructure execution.

## Problem

SoftOS has no canonical registry or safe process boundary for external agent harnesses. Ad hoc invocation cannot consistently prove availability, constrain paths, inject repository rules, capture failures, or prevent model/vendor coupling.

## Scope

### Included

- Top-level `agents` registry in the existing root `workspace.config.json`, with the initial IDs `codex`, `cursor`, and `opencode-local`.
- Host-native `flow agent list`, `flow agent doctor`, and `flow agent run <executor>`.
- A common adapter interface that converts a configured harness into argv and subprocess options.
- One repository/worktree, one prompt, and one or more bounded targets per run.
- A deterministic execution contract with repo, worktree, targets, boundaries, and canonical commands.
- Exit-code, stdout, and stderr capture with exact child failure propagation.
- Deterministic tests using fake executables, with no vendor CLI, credentials, network, Docker lifecycle, or interactive terminal dependency.
- Operator documentation for prerequisites, configuration, use, output, and troubleshooting.

### Non-scope

- Installing, upgrading, authenticating, or configuring agent CLIs on host or container.
- Selecting, configuring, routing, pricing, or evaluating models.
- Changing BMAD, its assets/contracts, or the current workflow orchestrator and lifecycle.
- Multi-agent scheduling, retry, timeout, cancellation, background execution, streaming protocols, remote execution, or PTY emulation.
- Access outside the validated workspace/worktree or target boundary.
- Persisting prompts, stdout, stderr, environment variables, credentials, tokens, or secret-bearing argv in reports.
- Running repository build/test/runtime commands directly on the host on an agent's behalf.

## Target surfaces

| Surface | Required responsibility |
| --- | --- |
| `flow` | Recognize `agent` as the sole host-native family; preserve other host blocking. |
| `flowctl/**` | Parse commands, validate config/paths, build contracts, adapt harnesses, invoke processes, render results. |
| `workspace.config.json` | Preserve existing workspace configuration and declare V1 executors under its top-level `agents` section without credentials or model routing. |
| `flowctl/tests/**` | Cover registry, routing, containment, subprocess, adapters, failures, and secret non-persistence. |
| `docs/**` | Document boundaries, host prerequisites, config, examples, and remediation. |
| This spec | Remain canonical; implementation must not broaden targets without refinement. |

## Registry contract

The existing `workspace.config.json` owns the versioned registry under a top-level `agents` section. The excerpt below is additive to the existing document; implementation must preserve all unrelated configuration:

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

- Top-level `agents` must be present in `workspace.config.json`; no separate agent-registry file is introduced.
- `agents.schema_version` must equal `1`.
- `agents.executors` is a non-empty object with unique IDs matching `^[a-z0-9][a-z0-9-]*$`.
- Each entry has exactly a supported `adapter`, non-empty executable name or absolute path, and string `argv` array.
- V1 adapters are `codex`, `cursor`, and `opencode`; registry ID, adapter, and model are independent concepts.
- `argv` contains static operator arguments only. Dynamic prompt/workdir behavior belongs to the adapter and never uses shell interpolation.
- Unknown fields, wrong types, unsupported versions/adapters, and duplicate JSON keys are errors.
- Credential fields are forbidden; host CLI authentication remains external to SoftOS.
- Invalid configuration exits non-zero with a field-specific diagnostic and launches no process.

## Functional contract

Commands are invoked from WSL as `python3 ./flow agent ...` (or the same root entry point directly) and do not proxy into the container.

### `flow agent list`

- Validates the registry and prints one record per executor in lexical ID order.
- Each record exposes ID, adapter, and executable only; it neither probes availability nor prints environment/authentication data.
- A valid registry returns zero; an empty or invalid registry returns non-zero.

### `flow agent doctor [executor]`

- Checks all executors in lexical order, or only the named executor.
- Resolves a bare executable through host `PATH`; an absolute path must be an executable regular file.
- Reports each as `ready` or `missing`, including the configured executable but no environment values.
- Returns zero only when every checked executor is ready. Missing executables, unknown IDs, and invalid config return non-zero.
- Checks availability only; it must not launch authentication, mutate configuration, use the network, or claim credentials are valid.

### `flow agent run <executor>`

Required options:

- `--repo <repo>`: a repo registered in `workspace.config.json`, with `workspace-root` reserved for root;
- `--workdir <path>`: an existing registered repo root or recognized worktree;
- `--prompt <text>`: non-empty operator prompt;
- one or more `--target <path>`: existing or prospective paths resolving inside the workdir.

Algorithm:

1. Validate registry, executor, repo, workdir, targets, and prompt before launch.
2. Canonicalize paths, following symlinks for existing ancestors, and reject containment escapes.
3. Prefix the unchanged user prompt with the execution contract below and a stable delimiter.
4. Ask the adapter for argv and prompt transport. An adapter may use stdin or one discrete argv element according to its CLI, never a command string.
5. Invoke with an argv sequence, `cwd` equal to canonical workdir, `shell=False`, captured stdout/stderr, and no retry.
6. Forward captured stdout to caller stdout and captured stderr to caller stderr.
7. Return the exact child exit code after a successful launch. Validation/launch errors use deterministic non-zero SoftOS codes.

Success must never be reported unless the child launched and returned zero.

## Execution contract

Every delivered prompt begins with a SoftOS-owned contract containing only:

- executor ID, repository ID, canonical workspace root, and canonical workdir;
- repository-relative allowed targets, normalized and lexically sorted;
- reads/writes limited to the assigned repo/worktree and writes limited to targets;
- `python3 ./flow repo exec <repo> --workdir <worktree> -- <command>` for repo runtime commands;
- `scripts/workspace_exec.sh python3 ./flow <command>` for control-plane commands;
- `python3 ./flow stack <command>` for Docker lifecycle commands;
- notice that normal control-plane commands remain workspace-only and `flow agent` is host-native;
- notice that BMAD and workflow orchestration are outside the run's authority.

The contract uses actual validated values and contains no credentials or inherited environment values. Adapters may vary transport syntax but must deliver identical logical content.

## Security and containment

- Workspace root is the root containing `flow` and `workspace.config.json`.
- Workdir is valid only if its canonical path is the selected registered repo root beneath the workspace or a worktree associated with that repo through existing SoftOS/Git worktree mechanisms.
- String-prefix containment is forbidden; use canonical path-component/common-path semantics.
- Relative targets resolve from workdir. For prospective paths, the canonical existing ancestor plus normalized suffix must remain inside workdir. Reject `..`, absolute, and symlink escapes.
- Reject empty targets, repo/worktree mismatch, missing/file workdir, and unknown repo/executor before launch.
- `shell=True`, `os.system`, shell pipes/redirection, and evaluated string commands are prohibited.
- SoftOS adds no credentials to argv, prompt, report, or environment. The child may inherit host environment for existing CLI authentication, but SoftOS never serializes or displays it.
- V1 persists no prompt or captured output. If generic infrastructure requires metadata, it is limited to executor ID, repo, canonical workdir, normalized targets, timestamps, and exit code; prompt/output/environment/rendered argv are forbidden.
- Tests use synthetic secrets to prove errors and metadata do not echo environment values or prompt secrets.

## Error contract

| Condition | Result |
| --- | --- |
| Invalid registry, unknown executor/repo/adapter | Non-zero diagnostic; no launch. |
| Missing executable or process creation failure | Non-zero actionable launch diagnostic; never success. |
| Invalid workdir/target, escape, or repo mismatch | Non-zero containment diagnostic; no launch. |
| Empty prompt or target set | Non-zero usage error; no launch. |
| Child exits non-zero | Exact child exit code; stdout/stderr preserved on corresponding streams. |
| Child exits zero | Zero and preserved streams; no claim about model quality or task completion. |

## Invariants and stop conditions

- Non-agent workspace-only enforcement remains observably unchanged.
- `flow agent` works with the workspace container stopped; deterministic tests prove this with fake executables.
- Shared orchestration sees executor ID and common request/result types only; executor behavior stays behind adapters.
- No branch may inspect a model name, provider, or capability.
- Do not modify BMAD, workflow orchestration, Docker/devcontainer config, host CLI config, credential stores, or files outside targets.
- If a CLI cannot receive the common contract non-interactively through argv/stdin without a shell, stop that adapter and report incompatibility; never weaken execution or containment.
- This spec stays `draft`; refinement does not approve it.

## Slice Breakdown

```yaml
- name: agent-registry-and-cli
  targets:
    - ../../flow
    - ../../flowctl/**
    - ../../workspace.config.json
    - ../../flowctl/tests/**
    - ../../docs/**
  hot_area: workspace agent registry and command routing
  depends_on: []
  slice_mode: implementation-heavy
  surface_policy: required
  minimum_valid_completion: validated registry plus deterministic list/doctor, with agent host-native and other enforcement preserved
  validated_noop_allowed: false
  acceptable_evidence:
    - malformed registry and schema tests
    - ordered list and ready/missing doctor tests with fake PATH executables
    - agent versus non-agent host-routing regression tests

- name: agent-process-execution
  targets:
    - ../../flow
    - ../../flowctl/**
    - ../../flowctl/tests/**
    - ../../docs/**
  hot_area: bounded subprocess execution and contract construction
  depends_on:
    - agent-registry-and-cli
  slice_mode: implementation-heavy
  surface_policy: required
  minimum_valid_completion: validate repo/worktree/targets, invoke argv without shell, capture streams, and propagate child status
  validated_noop_allowed: false
  acceptable_evidence:
    - path and symlink containment tests
    - argv and shell prohibition tests
    - stream and exact exit-code tests
    - secret non-persistence tests

- name: executor-adapters-and-tests
  targets:
    - ../../flowctl/**
    - ../../workspace.config.json
    - ../../flowctl/tests/**
    - ../../docs/**
  hot_area: codex cursor and opencode adapter parity
  depends_on:
    - agent-process-execution
  slice_mode: implementation-heavy
  surface_policy: required
  minimum_valid_completion: three adapters deliver the same logical contract through non-shell invocation with fake-CLI tests and docs
  validated_noop_allowed: false
  acceptable_evidence:
    - adapter contract tests for all initial IDs
    - fake-CLI integration tests independent of vendor installations
    - host prerequisite and canonical-command documentation review
```

## Rollout

1. Land the additive `workspace.config.json` `agents` registry validation and command routing after the normal spec approval gate, preserving all unrelated workspace configuration.
2. Enable list/doctor for the defaults; a missing host CLI affects doctor status only, not unrelated SoftOS commands.
3. Enable run only after containment, subprocess, stream, status, and redaction tests pass with fake executables.
4. Manually smoke each real host CLI only after the operator confirms host authentication; this supplements but never replaces CI.
5. Do not alter BMAD or workflow orchestration.

## Rollback

- Revert only the agent parser/routing, executor modules, `workspace.config.json` `agents` section, `flowctl/tests/**` coverage, and docs introduced here; preserve all pre-existing workspace configuration.
- Remove only the `agent` host exception to restore prior enforcement; do not weaken other enforcement.
- Do not remove/alter host CLI installations, configuration, credentials, repos, worktrees, or user changes.
- V1 has no prompt/output data migration. Metadata-only operational history may remain inert.

## Verification Matrix

All automation uses fake executables and fixed temporary fixtures; it requires no real CLI, network, credentials, interactive terminal, or running Docker stack.

```yaml
- name: spec-review
  level: custom
  command: scripts/workspace_exec.sh python3 ./flow spec review specs/features/agent-executors.spec.md
  blocking_on: [approval]
  environments: [local]
  notes: validates readiness without approving the draft

- name: spec-ci
  level: custom
  command: scripts/workspace_exec.sh python3 ./flow ci spec specs/features/agent-executors.spec.md
  blocking_on: [ci]
  environments: [local]
  notes: validates the canonical spec through the workspace control plane

- name: agent-executor-tests
  level: integration
  command: scripts/workspace_exec.sh python3 ./flow ci integration --profile agent-executors --json
  blocking_on: [ci]
  environments: [local]
  notes: runs fake registry routing containment adapter stream status and secret tests

- name: diff-check
  level: custom
  command: git diff --check -- specs/features/agent-executors.spec.md
  blocking_on: [approval, ci]
  environments: [local]
  notes: detects whitespace defects in the refinement target
```

## Acceptance Criteria

- The top-level `agents` registry in the existing `workspace.config.json` validates at schema version 1 and declares exactly `codex`, `cursor`, and `opencode-local`, with no credential/model fields; no separate registry file or top-level tests directory is introduced.
- The `cursor` registry entry uses the host executable `agent`.
- With a fixed valid registry, list returns zero and emits every executor once in lexical order with ID, adapter, and executable.
- With fake executables on `PATH`, doctor reports ready and returns zero; an absent checked executable reports missing and returns non-zero.
- Unknown executor doctor/run requests return non-zero and launch nothing.
- Run rejects missing prompt/target, unknown repo, repo/worktree mismatch, missing/file workdir, traversal, and symlink escape before launch.
- A valid run sets canonical workdir and delivers repo, worktree, sorted targets, boundaries, and all three canonical command forms.
- Tests prove every adapter passes an argv sequence with `shell=False` and performs no shell interpolation.
- A fake child writing distinct stdout/stderr markers and exiting `0`, `1`, and `37` yields separated streams and exact statuses.
- No validation, launch, or non-zero child failure is labeled successful or returns zero.
- Synthetic environment/prompt secrets never appear in persistent metadata, and prompt, streams, environment, and rendered argv are not persisted.
- All three harnesses use adapters behind a common request/result contract; shared orchestration does not inspect/select a model.
- Tests prove non-agent commands remain workspace-only while agent list/doctor/fake run operate host-native without a container.
- Docs assign CLI installation/authentication to the host operator and state the three canonical command forms.
- BMAD assets and workflow-orchestrator behavior remain unchanged.
- Spec status remains `draft`; refinement performs no approval action.
