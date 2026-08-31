---
schema_version: 3
name: "Host Repo Exec Routing Alignment"
description: "Align host execution enforcement with the existing canonical repo-exec host-to-container delegation path."
status: approved
owner: platform
single_slice_reason: "Host allowance and its focused delegation regressions form one atomic command-routing correction."
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
  - ../../flowctl/tooling.py
  - ../../flowctl/test_tooling.py
  - ../../flowctl/tests/test_agent_host_routing.py
  - ../../specs/features/host-repo-exec-routing-alignment.spec.md
---

# Host Repo Exec Routing Alignment

## Objective

Permit only the canonical `flow repo exec` command family through host execution enforcement so its existing repository/workspace service delegation can run unchanged.

The correction must reuse `command_repo_exec`; it must not introduce a second routing system or permit repository runtime commands to execute directly on the host.

## Root cause and problem statement

SoftOS documentation, agent execution contracts, and slice handoffs prescribe:

```bash
python3 ./flow repo exec <repo> --workdir <worktree> -- <command>
```

`command_repo_exec` already maps the repository or worktree into the configured container service. However, global host enforcement rejects the `repo` family before that delegation code is reached when `FLOW_FORCE_WORKSPACE_EXEC=1`.

This is a routing contradiction, not a missing delegation implementation. No domain spec applies because the change affects internal command routing and worktree safety rather than product behavior.

## Scope

### Included

- Permit exactly the `repo exec` command family through host execution enforcement.
- Route allowed invocations into the existing `command_repo_exec` implementation.
- Preserve configured repository/workspace compose-service selection.
- Preserve `--workdir` mapping for recognized Git worktrees.
- Fail missing, invalid, or unmappable workdirs before executing the child command.
- Add focused global host-routing and tooling/worktree delegation regressions.

### Non-goals

- No blanket allowance for every current or future `repo` subcommand.
- No fallback to direct host execution of repository runtime commands.
- No second delegation mechanism, wrapper, or command family.
- No changes to agent adapters, executor registry, or executor selection.
- No concrete model/provider selection, configuration, or routing.
- No orchestration, planner, scheduler, durable state, parallel execution, dashboard, MCP, Hermes, or live agent-preflight implementation.
- No Docker topology, service definition, infrastructure, deployment, or release change.
- No commit, push, pull request, merge, release, or publication authority.

## Repository and exact target surfaces

| Repository | Target | Responsibility |
| --- | --- | --- |
| `sdd-workspace-boilerplate` | `flowctl/tooling.py` | Narrow host allowance and existing repo-exec delegation boundary. |
| `sdd-workspace-boilerplate` | `flowctl/test_tooling.py` | Repo/service and worktree delegation regression tests. |
| `sdd-workspace-boilerplate` | `flowctl/tests/test_agent_host_routing.py` | End-to-end global host-enforcement regressions. |
| `sdd-workspace-boilerplate` | This spec | Canonical scope and evidence contract; remains orchestrator-owned. |

## Compatibility and invariants

- BMAD, this canonical spec, and its approved plan remain the planning authority.
- Only the exact command prefix `repo exec` becomes host-allowlisted.
- Every other workspace-only/control-plane command remains blocked on the host.
- Existing `command_repo_exec` service selection, workdir translation, and command passthrough remain the sole delegation implementation.
- Host allowance does not imply direct host runtime execution.
- Missing, invalid, or unmappable workdirs fail before child command execution.
- Repo/worktree containment and service routing boundaries are not weakened.
- Review is independent: `reviewer != implementer`.

## Slice Breakdown

```yaml
- name: host-repo-exec-routing
  repo: sdd-workspace-boilerplate
  targets:
    - ../../flowctl/tooling.py
    - ../../flowctl/test_tooling.py
    - ../../flowctl/tests/test_agent_host_routing.py
  hot_area: host command enforcement and canonical repo runtime delegation
  depends_on: []
  execution_difficulty: bounded-local
  preferred_implementer: opencode-local
  preferred_reviewer: codex
  slice_mode: implementation-heavy
  surface_policy: required
  minimum_valid_completion: allow only repo exec through host enforcement and prove existing service/worktree delegation remains safe
  validated_noop_allowed: false
  acceptable_evidence:
    - host repo exec reaches existing container delegation
    - worktree mapping and configured service routing remain correct
    - missing invalid and unmappable workdirs fail before execution
    - unrelated control-plane commands remain host-blocked
    - independent codex review with no self-review
```

## Acceptance Criteria

1. The spec produces exactly one implementation slice in `sdd-workspace-boilerplate`.
2. Host `flow repo exec` is not rejected by global host enforcement.
3. Allowed calls use the existing `command_repo_exec` container delegation path.
4. `--workdir` maps recognized Git worktrees into the configured repository/workspace service.
5. Missing, invalid, or unmappable workdirs fail before child command execution.
6. Other workspace-only/control-plane commands remain blocked on the host.
7. No other `repo` subcommand is allowlisted.
8. Repository runtime commands never fall back to direct host execution.
9. Current repo/service routing and worktree safety boundaries remain intact.
10. Focused host-routing tests, focused tooling/worktree delegation tests, applicable spec CI, and applicable repo CI pass.
11. `opencode-local` implements and `codex` independently reviews; no self-review is permitted.
12. No unrelated host-execution widening occurs.
13. No commit, push, PR, merge, release, or publication is authorized.

## Test Plan

- [@test] ../../flowctl/test_tooling.py
- [@test] ../../flowctl/tests/test_agent_host_routing.py

## Verification Matrix

```yaml
- name: spec-ci
  level: custom
  command: python3 ./flow workspace exec -- python3 ./flow ci spec specs/features/host-repo-exec-routing-alignment.spec.md --json
  blocking_on: [ci]
  environments: [local]
  notes: validates the approved canonical routing contract

- name: focused-routing-tests
  level: integration
  command: python3 ./flow workspace exec -- python3 -m pytest flowctl/test_tooling.py flowctl/tests/test_agent_host_routing.py -q
  blocking_on: [ci]
  environments: [local]
  notes: proves narrow host allowance service delegation worktree mapping and preserved host blocking

- name: repo-ci
  level: custom
  command: python3 ./flow workspace exec -- python3 ./flow ci repo sdd-workspace-boilerplate --spec host-repo-exec-routing-alignment --json
  blocking_on: [ci]
  environments: [local]
  notes: runs applicable root repository CI without changing routing scope
```

## Stop conditions

- Stop if the fix requires a new delegation path instead of `command_repo_exec`.
- Stop if every `repo` subcommand would need host allowance.
- Stop if any repository runtime command would execute directly on the host.
- Stop if worktree mapping or other workspace-only host blocking must be weakened.
- Stop if implementation expands into orchestration, executor routing, live probing, or infrastructure changes.

## Rollback and cleanup

Rollback removes only the narrow `repo exec` host allowance and its focused tests, restoring the previous global block while leaving `command_repo_exec` unchanged. Clean only slice worktrees through canonical worktree commands after evidence is preserved. No deployment, release, commit, push, PR, or merge is part of rollback.
