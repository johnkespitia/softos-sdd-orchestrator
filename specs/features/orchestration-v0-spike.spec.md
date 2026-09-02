---
schema_version: 3
name: "Orchestration V0 Spike"
description: "Create a tiny test-only Python fixture used solely to validate the bounded Orchestration V0 supervisor control loop."
status: approved
owner: platform
single_slice_reason: "The fixture and its deterministic unit test form one atomic, single-repository implementation task."
multi_domain: false
phases: []
depends_on:
  - specs/000-foundation/spec-as-source-operating-model.spec.md
  - specs/000-foundation/repo-routing-and-worktree-orchestration.spec.md
required_runtimes: []
required_services: []
required_capabilities: []
stack_projects: []
stack_services: []
stack_capabilities: []
targets:
  - ../../flowctl/tests/orchestration_v0/__init__.py
  - ../../flowctl/tests/orchestration_v0/status_fixture.py
  - ../../flowctl/tests/orchestration_v0/test_status_fixture.py
  - ../../specs/features/orchestration-v0-spike.spec.md
---

# Orchestration V0 Spike

## Objective

Create a deliberately tiny, isolated, test-only Python fixture that can safely prove the Orchestration V0 execution loop:

`supervisor -> implementation worker -> deterministic verification -> independent review -> maximum one repair -> READY_TO_PR or BLOCKED`

The feature is an execution fixture, not a production SoftOS capability. Its only observable behavior is the output of one pure function exercised by deterministic unit tests.

## Context

The workspace already keeps Python control-plane tests under `flowctl/tests/**`. A dedicated package at `flowctl/tests/orchestration_v0/**` follows that test-only convention while preventing the fixture from entering production command routing or runtime behavior. A new top-level fixture or test root is intentionally avoided because it would require workspace routing changes unrelated to the spike.

The applicable foundations govern canonical spec authority and single-repository worktree routing. No domain spec applies because this fixture introduces no business entity, durable domain vocabulary, or product behavior.

## Problem

The supervisor control loop needs one real but harmless implementation task with deterministic evidence. Existing approved plans are already completed or are too broad to serve as an isolated base spike.

## Scope

### Included

- Create `flowctl/tests/orchestration_v0/__init__.py` only as the test package marker.
- Create `flowctl/tests/orchestration_v0/status_fixture.py` containing exactly one public pure function:

```python
def render_status(name, passed):
    ...
```

- Implement these exact results:
  - `render_status("cursor", True) == "cursor: PASS"`
  - `render_status("opencode", False) == "opencode: FAIL"`
- Create `flowctl/tests/orchestration_v0/test_status_fixture.py` with deterministic tests covering both required calls.
- Use the fixture to exercise one bounded implementation worker, deterministic verification, one independent reviewer, and at most one repair cycle.

### Non-goals

- No production SoftOS behavior, command, API, package initialization, or runtime integration.
- No Docker, devcontainer, infrastructure, service, deployment, release, or environment changes.
- No executor registry changes and no model or provider configuration or selection.
- No BMAD, planner, orchestrator, workflow engine, or scheduler implementation.
- No MCP capability or integration.
- No network access, credentials, secrets, persistence, telemetry, or external service calls.
- No commit, merge, push, pull request, release, or publication.
- No changes outside the declared targets.

## Repository and target surfaces

| Repository | Target | Responsibility |
| --- | --- | --- |
| `sdd-workspace-boilerplate` | `flowctl/tests/orchestration_v0/__init__.py` | Empty package marker only. |
| `sdd-workspace-boilerplate` | `flowctl/tests/orchestration_v0/status_fixture.py` | Test-only pure function. |
| `sdd-workspace-boilerplate` | `flowctl/tests/orchestration_v0/test_status_fixture.py` | Deterministic tests for both required outcomes. |
| `sdd-workspace-boilerplate` | This spec | Canonical scope and evidence contract; remains orchestrator-owned. |

The implementation worker owns only the three paths under `flowctl/tests/orchestration_v0/**`. It must not modify this canonical spec or any other file.

## Functional contract

- `render_status(name, passed)` returns `name` unchanged, followed by `": "`, followed by `"PASS"` when `passed` is truthy and `"FAIL"` when it is falsy.
- The function performs no I/O, mutation, logging, environment lookup, subprocess execution, or network access.
- The implementation must remain independent of executor ID, harness, model, and provider.
- No additional production-facing function, command, or integration point is required or permitted.

## Orchestration constraints

- Any executor registered and reported ready by `flow agent doctor` must be able to perform the slice from the same bounded prompt and targets.
- Execution policy and executor choice belong to the supervisor. Model/provider selection remains outside this spec.
- The independent reviewer must not modify the worktree. The supervisor must compare Git state before and after review and treat reviewer mutation as `BLOCKED`.
- The original implementation worker may receive at most one repair invocation.
- After implementation and after any permitted repair, deterministic verification must run again.
- The spike terminates as `READY_TO_PR` only when tests, target-boundary verification, and independent review pass. Otherwise it terminates as `BLOCKED`.
- `READY_TO_PR` is evidence-only terminology for this spike; it does not authorize or create a PR.

## Slice Breakdown

```yaml
- name: render-status-fixture
  repo: sdd-workspace-boilerplate
  targets:
    - ../../flowctl/tests/orchestration_v0/__init__.py
    - ../../flowctl/tests/orchestration_v0/status_fixture.py
    - ../../flowctl/tests/orchestration_v0/test_status_fixture.py
  hot_area: isolated orchestration-v0 test fixture
  depends_on: []
  slice_mode: implementation-heavy
  surface_policy: required
  minimum_valid_completion: implement the pure render_status function and both deterministic tests within the three declared test-only paths
  validated_noop_allowed: false
  acceptable_evidence:
    - both required render_status examples pass through unittest
    - git diff contains only the three slice-owned targets
    - independent review reports no blocking finding and leaves the worktree unchanged
    - repair count is zero or one
```

## Acceptance Criteria

1. The implementation worker modifies only the three declared slice targets under `flowctl/tests/orchestration_v0/**`.
2. `render_status("cursor", True)` returns exactly `"cursor: PASS"`.
3. `render_status("opencode", False)` returns exactly `"opencode: FAIL"`.
4. Deterministic tests cover both cases and pass without network, Docker, credentials, or external executables.
5. The task is executable by any registered ready executor from the same target-bounded contract.
6. Model and provider configuration or selection remains outside this spec and outside the fixture.
7. No production behavior or production runtime import is added or changed.
8. No commit, merge, push, PR, release, or publication is performed as part of the spike.
9. The spike validates only the declared supervisor control loop, including independent review and a maximum of one repair.
10. The final supervisor outcome is exactly `READY_TO_PR` or `BLOCKED` and does not itself mutate Git state.

## Test Plan

- [@test] ../../flowctl/tests/orchestration_v0/test_status_fixture.py

## Verification Matrix

```yaml
- name: spec-ci
  level: custom
  command: python3 ./flow workspace exec -- python3 ./flow ci spec specs/features/orchestration-v0-spike.spec.md --json
  blocking_on: [ci]
  environments: [local]
  notes: validates the approved canonical spec before slice execution

- name: fixture-unit-tests
  level: custom
  command: python3 ./flow repo exec --workdir <slice-worktree> sdd-workspace-boilerplate -- python3 -m unittest flowctl.tests.orchestration_v0.test_status_fixture
  blocking_on: [ci]
  environments: [local]
  notes: the supervisor replaces <slice-worktree> with the recognized worktree path and requires both deterministic cases to pass

- name: target-boundary
  level: custom
  command: python3 ./flow workspace exec -- python3 ./flow slice verify orchestration-v0-spike render-status-fixture
  blocking_on: [ci]
  environments: [local]
  notes: verifies the diff and linked test remain within slice ownership
```

## Stop conditions

- Stop as `BLOCKED` if implementation requires any undeclared file.
- Stop as `BLOCKED` if the fixture would be imported by production runtime code.
- Stop as `BLOCKED` after a second implementation or verification failure; only one repair is permitted.
- Stop as `BLOCKED` if independent review changes the worktree or cannot be performed by a different executor.
- Do not broaden the feature to implement orchestration, scheduling, model routing, MCP, infrastructure, or release behavior.

## Rollback and cleanup

Because the fixture is isolated and test-only, cleanup consists of removing the spike worktree through the canonical worktree-clean flow after evidence is captured. If the unmerged implementation must be abandoned, discard only the isolated worktree; do not modify the base checkout. No production rollback, migration, deployment, release, commit, or push is required or authorized.
