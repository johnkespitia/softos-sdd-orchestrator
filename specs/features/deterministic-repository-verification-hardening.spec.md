---
schema_version: 3
name: "Deterministic Repository Verification Hardening"
description: "Resolve effective root Python test contracts and preserve Git ignore authority so linked tests and changed-file scope pass canonical slice verification deterministically."
status: approved
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
  - ../../flowctl/test_ci_repo_contracts.py
  - ../../flowctl/gittools.py
  - ../../flowctl/test_release_scope_drift.py
  - ../../flowctl/test_slice_verify.py
  - ../../specs/features/deterministic-repository-verification-hardening.spec.md
---

# Deterministic Repository Verification Hardening

## Objective

Make canonical repository verification deterministic by resolving the root repository's effective Python test-runner contract, executing only linked Python tests, and keeping Git-ignored files out of changed-file scope evidence.

This is platform verification hardening. It must remain repository-generic and must not add an exception for the feature or worktree that reproduced the defect.

## Lifecycle and current evidence

The historical draft with SHA-256 `71de31af2eddd8a6498e7adfdf9a8b605347e72806589162f1487c66328f2152` was deleted by commit `44d9209a99b9b6408e46658aa9aef88c183a533b` as lifecycle deferral for unresolved targets, not semantic rejection. Its historical PASS review is background only and is not approval authority for this reactivated specification.

A preserved `host-repo-exec-routing-alignment` implementation now demonstrates the runner defect through the real canonical path:

- implementation ownership passes;
- changed-file scope passes;
- focused Python tests pass (`22 passed`, plus `7 subtests`);
- canonical `flow slice verify` rejects both linked Python test files because `sdd-workspace-boilerplate` does not declare `test_runner`;
- no automatic test command is detected.

That result is a platform verification failure, not an implementation failure. The preserved worktree and its blocked outcome are evidence only and are outside this feature's write scope.

## Root cause and governing decisions

### Effective runner defect

Current slice verification uses two direct lookups:

```text
flow.validate_test_reference_patterns()
  -> repo_config(repo).get("test_runner", "none")
  -> flowctl.testing.validate_test_file_for_runner()

flow.detect_test_command()
  -> repo_config(repo).get("test_runner", "none")
  -> flowctl.testing.detect_test_command()
```

The root repo entry declares neither `runtime` nor `test_runner`, while `runtimes/python.runtime.json` declares `test_runner: pytest`. Slice verification does not resolve that effective runtime contract. `flow` remains the smallest current wiring boundary because it owns `repo_config`, runtime-pack access, test-reference validation, command detection, and slice-verification dependency injection. `flowctl/runtimes.py` already resolves runtime packs and is not a write target unless implementation proves the existing resolver cannot be consumed unchanged.

The effective runner algorithm is:

1. If a repo declares a non-empty `test_runner`, use it.
2. Otherwise, if the repo declares a runtime, resolve that existing runtime pack and use its `test_runner`.
3. The root repo must declare the canonical Python runtime contract needed to inherit `pytest`, unless an explicit root `test_runner` is intentionally chosen instead.
4. Missing, `none`, or unsupported effective runners fail with a deterministic diagnostic.
5. Runner resolution must be shared by linked-test validation and linked-test command detection so they cannot disagree.

Explicit repo configuration always overrides runtime defaults. No global language inference from file extensions is permitted.

### Git ignore authority defect

`flowctl/gittools.py::git_changed_files()` currently reads `git status --porcelain`, then recursively expands any reported directory with `Path.rglob()`. That filesystem traversal can reintroduce ignored `__pycache__/*.pyc` paths that Git omitted.

Git must enumerate reportable untracked files individually. SoftOS may normalize Git-reported paths, but it must not recursively rediscover files behind Git's ignore decision and must not introduce a second ignore policy.

## Scope

### Included

- Declare the root repo's effective Python runtime/test-runner contract in `workspace.config.json`.
- Resolve one effective runner with explicit repo override precedence over runtime-pack defaults.
- Reuse the existing runtime-pack resolver; do not duplicate runtime catalog parsing.
- Validate Python test files under the effective Python/pytest contract.
- Detect a Python/pytest command that includes only linked, materialized test paths.
- Preserve deterministic rejection for absent, `none`, or unsupported runners.
- Preserve PHP, pnpm, and Go validation and command construction.
- Replace recursive untracked-directory filesystem expansion with Git-authoritative enumeration.
- Preserve scoped path normalization, nested paths, spaces, renames, and quoted Git paths.
- Add focused runner-contract, Git scope-drift, and combined slice-verification regressions in existing canonical test files.

### Non-goals

- No replay, modification, cleanup, or closure of the preserved host-routing worktree.
- No feature-specific exception or allowlist.
- No unrestricted root-repository pytest run; only linked/materialized paths may execute.
- No duplicate runtime manifest parser or second Git ignore implementation.
- No orchestration, scheduler, executor registry, model/provider configuration, Docker topology, infrastructure, deployment, or release change.
- No plan generation, approval, implementation, commit, push, PR, merge, release, or publication as part of specification definition.

## Executable surface inventory

| Slice | Target | Current responsibility | Required outcome |
| --- | --- | --- | --- |
| `root-python-test-contract` | `workspace.config.json` | Root repo contract | Declare the root Python runtime/test contract without changing unrelated repo configuration. |
| `root-python-test-contract` | `flow` | Effective runner wiring for validation and execution | Resolve override-first effective runner once and supply it consistently to existing testing helpers. |
| `root-python-test-contract` | `flowctl/testing.py` | Linked-test structural validation and command construction | Add bounded Python/pytest validation and linked-path execution while preserving existing runners. |
| `root-python-test-contract` | `flowctl/test_ci_repo_contracts.py` | Existing repository-contract regressions | Prove runtime default inheritance, explicit override precedence, missing/unsupported failure, and linked-only Python commands. |
| `git-scope-ignore-hygiene` | `flowctl/gittools.py` | Git diff/status normalization and changed-file inventory | Make Git authoritative for ignored and untracked file enumeration; remove filesystem re-expansion. |
| `git-scope-ignore-hygiene` | `flowctl/test_release_scope_drift.py` | Existing changed-scope/release-drift regressions | Prove ignored bytecode exclusion, non-ignored untracked inclusion, and scoped path normalization. |
| `slice-verification-regression` | `flowctl/test_slice_verify.py` | Existing canonical slice-verification regressions | Prove effective runner, linked execution, Git ignore semantics, and final verification outcome together. |
| Orchestrator | This spec | Canonical intent and evidence contract | Remain the approved canonical intent and evidence contract unless refined through lifecycle governance. |

All listed implementation and test targets currently exist. The historical nonexistent `flowctl/test_gittools.py` target is intentionally removed. Exclusive write ownership does not overlap between slices.

## Compatibility and invariants

- Root `specs/**` and the approved plan remain canonical after later lifecycle gates.
- Explicit repo-level `test_runner` overrides the runtime-pack default.
- Runtime inheritance uses the existing runtime catalog and cannot infer a runtime from test filenames.
- Validation and command detection consume the same effective runner.
- Python commands include only linked, materialized test paths in deterministic order.
- PHP, pnpm, and Go behavior remains observably unchanged.
- Missing, `none`, or unsupported runner contracts fail; they never silently pass validation.
- Git is the only ignore authority. Filesystem traversal cannot reintroduce ignored paths.
- Non-ignored untracked files remain visible to scope checking.
- Worktree, nested repo, spaces, quoted paths, renames, and prefix normalization remain supported.
- Reviewer identity differs from implementer identity for every slice.
- The final integration slice starts only after both implementation slices pass focused verification and independent review.

## Slice Breakdown

```yaml
- name: root-python-test-contract
  repo: sdd-workspace-boilerplate
  targets:
    - ../../workspace.config.json
    - ../../flow
    - ../../flowctl/testing.py
    - ../../flowctl/test_ci_repo_contracts.py
  hot_area: effective root runner resolution and bounded linked Python test execution
  depends_on: []
  execution_difficulty: bounded-local
  preferred_implementer: opencode-local
  preferred_reviewer: cursor
  slice_mode: implementation-heavy
  surface_policy: required
  minimum_valid_completion: resolve one override-first effective Python runner contract and prove linked-only validation and execution without changing existing runner behavior
  validated_noop_allowed: false
  acceptable_evidence:
    - root runtime default resolves pytest for linked Python tests
    - explicit repo test_runner overrides the runtime default
    - missing none and unsupported runners fail deterministically
    - detected pytest command contains only linked materialized paths
    - PHP pnpm and Go regressions remain green
    - independent cursor review leaves Git state unchanged

- name: git-scope-ignore-hygiene
  repo: sdd-workspace-boilerplate
  targets:
    - ../../flowctl/gittools.py
    - ../../flowctl/test_release_scope_drift.py
  hot_area: Git-authoritative changed-file enumeration and ignored artifact scope hygiene
  depends_on: []
  execution_difficulty: bounded-local
  preferred_implementer: cursor
  preferred_reviewer: codex
  slice_mode: implementation-heavy
  surface_policy: required
  minimum_valid_completion: enumerate reportable untracked files through Git without recursive filesystem expansion and prove ignored artifacts cannot create false scope drift
  validated_noop_allowed: false
  acceptable_evidence:
    - ignored __pycache__ and pyc files are absent from changed-file evidence
    - non-ignored untracked nested files remain present
    - spaces quoting renames prefixes and nested paths normalize correctly
    - no SoftOS-specific ignore list is introduced
    - independent codex review leaves Git state unchanged

- name: slice-verification-regression
  repo: sdd-workspace-boilerplate
  targets:
    - ../../flowctl/test_slice_verify.py
  hot_area: combined canonical slice-verification regression coverage
  depends_on:
    - root-python-test-contract
    - git-scope-ignore-hygiene
  execution_difficulty: bounded-local
  preferred_implementer: opencode-local
  preferred_reviewer: codex
  slice_mode: implementation-heavy
  surface_policy: required
  minimum_valid_completion: prove canonical slice verification accepts linked Python tests executes only those paths and ignores Git-ignored bytecode after both prerequisite fixes
  validated_noop_allowed: false
  acceptable_evidence:
    - canonical verification accepts linked Python tests under the effective runner
    - detected execution includes only linked materialized paths
    - post-test bytecode remains absent from changed scope
    - combined verification reports no test-link test-runner or Git-scope failure
    - both prerequisite slices are complete and independently reviewed
    - independent codex review leaves Git state unchanged
```

## Deterministic behavior matrix

| Condition | Required result |
| --- | --- |
| Repo has explicit supported `test_runner` | Use it, even when runtime default differs. |
| Repo has no explicit runner and has a supported runtime | Use the runtime pack's `test_runner`. |
| Effective runner is `pytest` and linked paths are valid Python tests | Validate them and construct a command containing only those paths. |
| Effective runner is missing, `none`, or unsupported | Fail with a stable diagnostic before claiming tests executable. |
| Git reports an ignored file nowhere | Never add it through filesystem traversal. |
| Git reports a non-ignored untracked nested file | Include it after normal scoped-path normalization. |
| Focused tests pass but canonical verification cannot resolve a runner | Treat as a platform verification failure; do not blame implementation. |

## Acceptance Criteria

1. The specification produces exactly three slices with disjoint targets and declared dependencies.
2. Every implementation and test target exists at review time; no unresolved target remains.
3. Root Python linked tests validate and execute through one effective runner contract.
4. Explicit repo-level `test_runner` overrides runtime-pack defaults.
5. Runtime fallback uses the existing runtime-pack resolver and the root repo's declared Python runtime contract.
6. Python/pytest execution is limited to linked, materialized paths and never broadens to an unrestricted root test run.
7. Missing, `none`, and unsupported runners fail deterministically.
8. PHP, pnpm, and Go validation and command construction remain unchanged.
9. Git enumerates reportable untracked files without recursive filesystem expansion.
10. Ignored `__pycache__/*.pyc` files remain absent while non-ignored nested files remain visible.
11. Scoped paths, spaces, quoting, renames, prefixes, and worktree inspection remain correct.
12. Focused tests owned by slices 1 and 2 pass before slice 3 starts.
13. Combined slice verification accepts the same class of linked Python files proven by the preserved host-routing evidence.
14. Each implementation receives independent read-only review from its declared reviewer, with identical Git state before and after review.
15. No feature-specific exception, duplicate runtime resolver, duplicate ignore policy, model/provider configuration, infrastructure change, or production behavior is introduced.
16. Applicable spec CI and repo CI pass before closeout.
17. No commit, push, PR, merge, release, or publication is authorized by this spec.

## Test Plan

- [@test] ../../flowctl/test_ci_repo_contracts.py
- [@test] ../../flowctl/test_release_scope_drift.py
- [@test] ../../flowctl/test_slice_verify.py

## Verification Matrix

```yaml
- name: spec-ci
  level: custom
  command: python3 ./flow workspace exec -- python3 ./flow ci spec specs/features/deterministic-repository-verification-hardening.spec.md --json
  blocking_on: [ci]
  environments: [local]
  notes: validates the approved canonical contract

- name: focused-contract-tests
  level: integration
  command: python3 ./flow workspace exec -- python3 -m pytest flowctl/test_ci_repo_contracts.py flowctl/test_release_scope_drift.py -q
  blocking_on: [ci]
  environments: [local]
  notes: proves independent effective-runner and Git-ignore contracts before combined verification

- name: combined-slice-verification-tests
  level: integration
  command: python3 ./flow workspace exec -- python3 -m pytest flowctl/test_slice_verify.py -q
  blocking_on: [ci]
  environments: [local]
  notes: proves the two prerequisite fixes through canonical slice-verification behavior

- name: repo-ci
  level: custom
  command: python3 ./flow workspace exec -- python3 ./flow ci repo sdd-workspace-boilerplate --spec deterministic-repository-verification-hardening --json
  blocking_on: [ci]
  environments: [local]
  notes: runs applicable root repository CI without widening slice ownership
```

## Evidence package and delivery contract

Closure requires:

- focused test command and result for each implementation slice;
- combined `flowctl/test_slice_verify.py` result after both prerequisites;
- canonical `flow slice verify` report for each slice;
- changed-file inventory proving exclusive target ownership;
- independent reviewer result and before/after Git-state identity for each slice;
- spec CI and repo CI reports linked from final closeout evidence.

The preserved host-routing failure is baseline evidence only. It must not be edited, cleaned, or presented as post-fix proof. Post-fix evidence must come from newly materialized worktrees for this feature.

## Stop conditions

- Stop if implementation requires a target not declared by this spec.
- Stop if effective runner resolution would require a duplicate runtime catalog parser instead of the existing resolver.
- Stop if Python execution cannot remain limited to linked/materialized paths.
- Stop if Git ignore behavior would be duplicated in a SoftOS-specific ignore list.
- Stop if any slice needs overlapping write ownership.
- Stop if PHP, pnpm, or Go behavior changes without prior spec refinement.
- Stop if the solution adds a feature-specific exception, executor routing, model/provider configuration, orchestration, infrastructure, or release behavior.

## Rollback and cleanup

Rollback is limited to the root runner declaration/resolution, bounded Python test behavior, Git changed-file enumeration, and focused regressions introduced by the declared targets. Restore prior behavior without altering unrelated workspace configuration. Preserve evidence before cleaning only this feature's future worktrees through canonical worktree commands. The host-routing evidence worktree is not part of this feature's cleanup authority.
