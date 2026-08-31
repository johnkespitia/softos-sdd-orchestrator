---
schema_version: 3
name: "Deterministic Repository Verification Hardening"
description: "Harden root Python test-runner resolution and Git-aware scope detection so linked tests and ignored artifacts produce deterministic slice verification."
status: draft
owner: platform
single_slice_reason: ""
multi_domain: false
phases: []
depends_on:
  - specs/000-foundation/spec-as-source-operating-model.spec.md
  - specs/000-foundation/repo-routing-and-worktree-orchestration.spec.md
  - specs/000-foundation/spec-driven-delivery-and-infrastructure.spec.md
required_runtimes:
  - python
required_services: []
required_capabilities: []
stack_projects: []
stack_services: []
stack_capabilities: []
targets:
  - ../../workspace.config.json
  - ../../flow
  - ../../flowctl/testing.py
  - ../../flowctl/gittools.py
  - ../../flowctl/test_slice_verify.py
  - ../../flowctl/test_gittools.py
  - ../../specs/features/deterministic-repository-verification-hardening.spec.md
---

# Deterministic Repository Verification Hardening

## Objective

Make repository verification deterministic and reusable by establishing a canonical Python test contract for the root repository and by keeping Git-ignored files out of changed-file scope evidence.

This is a SoftOS platform hardening change. It must not contain an exception tied to any individual feature or spike.

## Root cause and problem statement

Two platform defects were proven by a bounded execution:

1. Slice verification reads the root repository's `test_runner` as `none`. A valid linked Python unittest-compatible file is therefore rejected, even when its explicit deterministic command passes.
2. `git status --porcelain` can collapse an untracked directory to one entry. `git_changed_files` recursively expands that directory through the filesystem and thereby reintroduces ignored `__pycache__/*.pyc` files that Git correctly omitted.

Together, these defects make a correct implementation fail the canonical `flow slice verify` gate. No domain spec applies because this hardening changes internal verification mechanics, not business vocabulary or durable product behavior.

## Scope

### Included

- Define how the root repository declares or inherits its Python runtime and test-runner contract.
- Preserve explicit per-repository `test_runner` as authoritative over runtime defaults.
- Accept linked Python unittest-compatible test files under the Python runner contract.
- Execute only linked, materialized Python test paths with configured interpreter/runtime semantics.
- Preserve deterministic failure for absent or unsupported runner contracts.
- Make Git enumerate reportable untracked files individually.
- Remove recursive filesystem expansion that can bypass Git ignore semantics.
- Preserve scoped path normalization, nested paths, spaces, and quoted Git paths.
- Add focused regression coverage for runner resolution, test execution, ignored bytecode, and slice scope verification.

### Non-goals

- No production feature or application behavior changes.
- No exception for `orchestration-v0-spike` or any other feature.
- No replay or modification of the blocked spike, its spec, plan, worktree, or fixture.
- No orchestration, planner, scheduler, durable execution state, parallel execution, dashboard, MCP, or Hermes implementation.
- No executor registry or execution-policy changes.
- No concrete model/provider selection, configuration, or routing.
- No Docker, service, infrastructure, deployment, or release change.
- No commit, push, pull request, merge, release, or publication authority.

## Repository and exact target surfaces

| Repository | Target | Responsibility |
| --- | --- | --- |
| `sdd-workspace-boilerplate` | `workspace.config.json` | Declare the root repo's canonical runtime/test contract without changing unrelated configuration. |
| `sdd-workspace-boilerplate` | `flow` | Resolve the effective runner consistently at slice verification entry points. |
| `sdd-workspace-boilerplate` | `flowctl/testing.py` | Validate and execute linked Python tests while preserving existing runners. |
| `sdd-workspace-boilerplate` | `flowctl/gittools.py` | Report changed files according to Git ignore and scope semantics. |
| `sdd-workspace-boilerplate` | `flowctl/test_slice_verify.py` | Prove root Python test and post-test scope behavior. |
| `sdd-workspace-boilerplate` | `flowctl/test_gittools.py` | Prove ignored/untracked path behavior directly. |
| `sdd-workspace-boilerplate` | This spec | Canonical behavior and evidence contract; remains orchestrator-owned. |

## Compatibility and invariants

- BMAD, this canonical spec, and its approved plan remain the planning authority.
- Explicit repo-level `test_runner` wins over an inherited runtime-pack default.
- Existing PHP, pnpm, and Go validation and command construction remain observably unchanged.
- Python execution is limited to linked/materialized paths; it must not broaden into an unrestricted repository test run.
- Missing or unsupported runner configuration fails with a deterministic diagnostic and does not silently accept a test.
- Git remains the authority for ignored files. Python filesystem traversal must not reintroduce ignored paths.
- Non-ignored nested files remain visible to scope checking.
- Path normalization continues to support scoped repositories, spaces, nested paths, and Git quoting.
- Review must be independent: `reviewer != implementer` for every slice.
- All three slices have disjoint write ownership. The final regression slice starts only after both implementation slices complete.

## Slice Breakdown

```yaml
- name: root-python-test-contract
  repo: sdd-workspace-boilerplate
  targets:
    - ../../workspace.config.json
    - ../../flow
    - ../../flowctl/testing.py
  hot_area: root repository test-runner resolution and linked Python test execution
  depends_on: []
  execution_difficulty: bounded-local
  preferred_implementer: opencode-local
  preferred_reviewer: cursor
  slice_mode: implementation-heavy
  surface_policy: required
  minimum_valid_completion: resolve the root Python runner contract, execute only linked Python tests, and preserve all existing runner behavior with focused tests
  validated_noop_allowed: false
  acceptable_evidence:
    - linked unittest-compatible Python files validate and execute through the configured runner
    - explicit repo test_runner overrides runtime defaults
    - missing or unsupported runner fails deterministically
    - PHP pnpm and Go regression tests remain green
    - independent cursor review with no self-review

- name: git-scope-ignore-hygiene
  repo: sdd-workspace-boilerplate
  targets:
    - ../../flowctl/gittools.py
    - ../../flowctl/test_gittools.py
  hot_area: Git changed-file enumeration and ignored artifact scope hygiene
  depends_on: []
  execution_difficulty: bounded-local
  preferred_implementer: cursor
  preferred_reviewer: codex
  slice_mode: implementation-heavy
  surface_policy: required
  minimum_valid_completion: enumerate reportable untracked files through Git without filesystem expansion and prove ignored bytecode cannot create false scope drift
  validated_noop_allowed: false
  acceptable_evidence:
    - ignored __pycache__ and pyc files are absent from changed-file evidence
    - non-ignored nested files remain present
    - scoped normalization spaces and nested paths remain correct
    - independent codex review with no self-review

- name: slice-verification-regression
  repo: sdd-workspace-boilerplate
  targets:
    - ../../flowctl/test_slice_verify.py
  hot_area: end-to-end slice verification regression coverage
  depends_on:
    - root-python-test-contract
    - git-scope-ignore-hygiene
  execution_difficulty: bounded-local
  preferred_implementer: opencode-local
  preferred_reviewer: codex
  slice_mode: implementation-heavy
  surface_policy: required
  minimum_valid_completion: prove the combined root Python test contract and Git ignore hygiene through focused slice verification regressions
  validated_noop_allowed: false
  acceptable_evidence:
    - linked Python unittest-compatible tests validate and execute in slice verification
    - Python test execution followed by slice scope verification ignores bytecode and passes
    - both prerequisite slices are complete before this slice starts
    - independent codex review with no self-review
```

## Acceptance Criteria

1. The spec produces exactly three independently testable implementation slices in one repository with disjoint write ownership.
2. The root repo can declare or inherit a canonical Python runtime/test-runner contract.
3. Explicit per-repo `test_runner` remains authoritative over runtime defaults.
4. Linked Python unittest-compatible files validate and only linked/materialized paths execute.
5. Missing or unsupported runners fail deterministically.
6. Existing PHP, pnpm, and Go runner behavior remains unchanged.
7. Git enumerates untracked files individually and does not recursively reintroduce ignored files.
8. Ignored `__pycache__/*.pyc` files do not appear as changed scope; non-ignored nested files do.
9. Scoped path normalization supports spaces, quoting, and nested paths.
10. Focused deterministic tests, applicable spec CI, and applicable repo CI pass.
11. `slice-verification-regression` depends on both preceding slices and proves their combined behavior.
12. Each slice is independently reviewed by the declared reviewer, and no executor reviews its own implementation.
13. No production feature behavior changes and no spike-specific exception is introduced.
14. Replay of `orchestration-v0-spike` is not part of this spec.
15. No commit, push, PR, merge, release, or publication is authorized.

## Test Plan

- [@test] ../../flowctl/test_slice_verify.py
- [@test] ../../flowctl/test_gittools.py

## Verification Matrix

```yaml
- name: spec-ci
  level: custom
  command: python3 ./flow workspace exec -- python3 ./flow ci spec specs/features/deterministic-repository-verification-hardening.spec.md --json
  blocking_on: [ci]
  environments: [local]
  notes: validates the approved canonical spec and both slice contracts

- name: focused-verification-tests
  level: integration
  command: python3 ./flow workspace exec -- python3 -m pytest flowctl/test_slice_verify.py flowctl/test_gittools.py -q
  blocking_on: [ci]
  environments: [local]
  notes: proves runner resolution linked execution Git ignore semantics and scope hygiene

- name: repo-ci
  level: custom
  command: python3 ./flow workspace exec -- python3 ./flow ci repo sdd-workspace-boilerplate --spec deterministic-repository-verification-hardening --json
  blocking_on: [ci]
  environments: [local]
  notes: runs applicable root repository CI without widening implementation scope
```

## Stop conditions

- Stop if either slice requires a target not declared by this spec.
- Stop if Python execution cannot remain limited to linked/materialized paths.
- Stop if Git ignore behavior must be duplicated in a separate SoftOS ignore list.
- Stop if existing PHP, pnpm, or Go behavior changes without explicit spec refinement.
- Stop if implementation attempts to add orchestration, parallel scheduling, executor routing, or feature-specific exceptions.

## Rollback and cleanup

Rollback is limited to the runner-resolution, Python test execution, Git changed-file enumeration, configuration, and focused tests introduced by these targets. Restore the prior runner and changed-file behavior without altering unrelated workspace configuration. Clean only slice worktrees through canonical worktree commands after evidence is preserved. No production deployment, migration, release, commit, push, PR, or merge is part of rollback.
