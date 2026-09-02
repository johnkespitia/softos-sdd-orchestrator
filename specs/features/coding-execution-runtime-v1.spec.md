---
schema_version: 3
name: "Coding Execution Runtime V1"
description: "Define portable OpenCode resource pools, Patch Unit execution policy, a reusable supervisor playbook, and one real full-run validation without introducing a durable scheduler."
status: approved
owner: platform
single_slice_reason: ""
multi_domain: false
phases: []
depends_on:
  - specs/000-foundation/spec-as-source-operating-model.spec.md
  - specs/000-foundation/repo-routing-and-worktree-orchestration.spec.md
  - specs/000-foundation/spec-driven-delivery-and-infrastructure.spec.md
  - specs/features/agent-executors.spec.md
  - specs/features/deterministic-repository-verification-hardening.spec.md
required_runtimes:
  - python
required_services: []
required_capabilities: []
stack_projects: []
stack_services: []
stack_capabilities: []
targets:
  - ../../workspace.config.json
  - ../../opencode.json
  - ../../flowctl/agent_resources.py
  - ../../flowctl/agent_executors.py
  - ../../flowctl/agent_process_execution.py
  - ../../flowctl/tests/test_agent_resources.py
  - ../../flowctl/tests/test_agent_process_execution.py
  - ../../docs/opencode-execution-resources.md
  - ../../policies/coding-execution-runtime-v1.json
  - ../../flowctl/coding_execution_policy.py
  - ../../flowctl/tests/test_coding_execution_policy.py
  - ../../.agents/skills/softos-coding-execution-supervisor/**
  - ../../workspace.skills.json
  - ../../docs/coding-execution-runtime-v1-full-run.md
---

# Coding Execution Runtime V1

## Objective

Close Coding Execution Runtime V1 with four observable outcomes:

1. the repository-owned OpenCode configuration selects `lmstudio/prism-ml/bonsai-27b` for the canonical `softos-local-worker` profile used by logical resource `opencode-local`;
2. SoftOS represents `opencode-local`, `opencode-free`, and `opencode-go` as logical execution resources with deterministic capability and availability semantics;
3. a portable machine-readable policy and reusable supervisor skill define the canonical Product Slice-to-independent-review process, including Patch Units and bounded failure handling; and
4. one real, evidence-producing validation runs the approved `git-scope-ignore-hygiene` slice through that process without asking Bonsai to execute the slice monolithically.

The V1 result is a bounded execution contract and playbook. It is not a durable scheduler.

## Semantic refinement (post-S1 audit)

A real S1 implementation audit found an execution-boundary defect in slice `opencode-resource-pools`: logical resources and dynamic Free/Go model resolution were correct in metadata and diagnostics, but the resolved model never reached the spawned OpenCode child process.

Current harness path:

```text
flow agent run
  -> command_agent_run()
  -> prepare_agent_run(executor_id)
  -> OpenCodeAdapter
  -> AgentAdapterInvocation(argv, stdin)
  -> execute_subprocess()
```

Observed defect: `opencode-free` and `opencode-go` referenced executor `opencode-local`, which launches `opencode-softos` with `default_agent=softos-local-worker` (the Bonsai profile). `resolve_free_model()` / `resolve_go_model()` affected diagnostics only; `execute_subprocess()` had no resource-specific environment overlay path.

This refinement returns the spec to `draft`. Prior approval and any generated plan are no longer authoritative. Human re-approval is required before planning or further implementation resumes.

## Context and existing conventions

- `workspace.config.json` already owns the versioned, model-agnostic executor registry. `flowctl/agent_executors.py` and `flowctl/agent_executor_adapters.py` keep invocation behind adapter contracts and reject generic model/provider flags. `flowctl/agent_process_execution.py` owns subprocess launch and must remain the process-environment boundary for resource overlays.
- `opencode.json` is the existing repository-owned OpenCode configuration distributed with the workspace. It is the canonical portable source for the `softos-local-worker` definition and its model selection; `~/.config/opencode/**`, wrapper scripts, authentication stores, and environment overrides are machine-local materialized state only.
- `.agents/skills/**` plus `workspace.skills.json` are the existing portable skill convention.
- `policies/**` contains versioned machine-readable or documented harness policy. `.flow/**` remains derived operational state and evidence, never product truth.
- `flow agent doctor` currently proves executable presence only. This feature may add resource-aware diagnostics but must preserve that existing meaning for executor diagnostics.
- `deterministic-repository-verification-hardening` is approved and defines the pending `git-scope-ignore-hygiene` slice with disjoint targets, focused tests, and independent review requirements.

No domain spec applies because the feature defines platform execution policy and harness resource semantics, not durable business entities. The three declared foundation specs govern canonical intent, worktree routing, and workspace execution boundaries.

## Problem

SoftOS can invoke host-native executors but cannot yet describe logical OpenCode resource pools, filter them by capability and runtime availability, or apply a portable decomposition and routing policy. The proven local worker exists only as machine-local configuration and historical documentation. Broad tasks can therefore accumulate too much context for a bounded local worker, and fallback, repair, re-decomposition, and escalation are not distinguished canonically.

## Scope

### Included

- Logical resources `opencode-local`, `opencode-free`, and `opencode-go` behind the existing `opencode` adapter.
- Repository-owned `softos-local-worker` configuration selecting `lmstudio/prism-ml/bonsai-27b`, reasoning enabled, conservative logical capacity `1`, and short fresh sessions.
- Runtime availability/auth/capacity states and dynamic model resolution for free and Go pools.
- A versioned Patch Unit and resource-selection policy with deterministic validation and focused unit tests.
- A reusable supervisor skill that reconstructs context from specs/plans/repo rules, performs decomposition and routing, packages handoffs, verifies results, and enforces independent review.
- One verification-only real run of approved slice `git-scope-ignore-hygiene`, with exact evidence and stop conditions.
- Documentation distinguishing canonical repository configuration from machine-local OpenCode auth and materialized state.

### Out of scope

- Durable run database, full or parallel scheduler, leases, failover, background workers, advanced observability, automatic merge, release, or publication.
- Installing or authenticating OpenCode, LM Studio, Codex, or Cursor; storing any token or secret; inventing `OPENCODE_GO_TOKEN` or another authentication interface.
- Hardcoding a temporary OpenCode free model or a permanent OpenCode Go model.
- Adding model/provider flags to generic `flow agent run` invocation.
- Routing supervision/orchestration to local models by default.
- Modifying or consuming the preserved historical worktrees `host-repo-exec-routing-alignment-host-repo-exec-routing` and `orchestration-v0-spike-render-status-fixture`.
- Implementing `git-scope-ignore-hygiene` during spec, planning, or review of this feature.

## Architecture boundaries

### Core, resource, and harness ownership

| Layer | Owns | Must not own |
| --- | --- | --- |
| SoftOS Core/policy | logical resource IDs, capabilities, availability state, cost tier, capacity, selection priority, failure semantics | hardcoded model/provider branches, provider credentials, machine-local auth |
| Executor/resource configuration | adapter, executable, resource pool, capability declarations, model-resolution policy, capacity, underlying executor references | tokens or claims that auth is configured without a runtime probe |
| Harness/process execution (`agent_executors.py`, `agent_process_execution.py`) | resource-aware selection before executor launch, logical-resource ID propagation, validated process-environment overlay merge at subprocess boundary | generic `--model` / `--provider` CLI flags, credential serialization, wholesale environment replacement |
| OpenCode repository config | portable `softos-local-worker` profile and canonical local model selection | secrets or machine-specific absolute paths |
| OpenCode machine-local state | authenticated providers, temporary model inventory, local LM Studio endpoint/materialization | canonical product policy |

The orchestration algorithm selects a logical resource before that resource resolves a model. Core branches may inspect resource metadata and normalized availability states, but never model or provider identity. `flowctl/agent_executor_adapters.py` remains model/provider agnostic; resource-specific OpenCode model selection is applied only through the harness process boundary and validated environment overlay, not adapter argv flags.

### Execution harness boundary

The V1 harness must close the gap between logical resource metadata and the spawned OpenCode process:

```text
requested logical resource ID
  -> generic resource lookup
  -> underlying executor lookup
  -> dynamic resource model resolution
  -> safe OpenCode process environment/config overlay
  -> subprocess execution
```

Harness behavior by resource:

| Resource | Underlying executor | Wrapper/profile | Model resolution effect |
| --- | --- | --- | --- |
| `opencode-local` | existing local executor (`executable: opencode-softos`) | repository-owned `softos-local-worker` | fixed Bonsai via portable OpenCode profile; capacity `1` |
| `opencode-free` | generic direct OpenCode cloud executor (`executable: opencode`) declared in workspace configuration | MUST NOT execute through a wrapper that forces Bonsai | dynamically resolved free model MUST affect the actual spawned OpenCode process |
| `opencode-go` | same generic direct OpenCode cloud executor as Free when auth evidence exists | MUST NOT execute through the local Bonsai wrapper | remains `AUTH_UNCONFIGURED` until supported runtime evidence exists; after valid evidence, dynamically resolved Go model MUST affect the actual process |

The logical resource ID must remain available through the harness boundary even when multiple logical resources share one underlying executor configuration.

Legacy invocation `flow agent run <executor-id> ...` must continue working. The resource layer may resolve a positional selection as a logical resource ID first and then its underlying executor, avoiding a new CLI/parser surface for V1. Do not add a `--resource` flag unless repository evidence proves it is necessary.

### Process environment overlay

The process execution boundary may receive a safe resource-specific environment overlay. The OpenCode resource layer may build `OPENCODE_CONFIG_CONTENT` for the selected process using the resolved model.

Overlay rules:

- process-local only; never persisted to Git or evidence
- contains no credentials and does not persist raw provider/auth payloads
- merges with the inherited process environment; must not replace the whole inherited environment accidentally
- preserves the bounded repository-owned worker contract for `opencode-local` while changing only the selected model for Free/Go
- must never make Free/Go inherit Bonsai accidentally unless that model were actually returned as the selected cloud candidate

`execute_subprocess()` must merge a validated overlay with the inherited process environment rather than replace it wholesale. Equivalent existing conventions are acceptable if they preserve this boundary. Do not modify `flowctl/agent_executor_adapters.py` unless later evidence proves unavoidable.

### Resource contract

The existing `agents` configuration must evolve compatibly rather than creating a parallel registry. Executor IDs remain harness identities. Logical resource records reference an existing executor/adapter and expose only validated fields needed by selection and diagnostics.

| Resource | Cost/tier | Capacity | Underlying executor | Model resolution | Initial/runtime availability |
| --- | --- | ---: | --- | --- | --- |
| `opencode-local` | local | 1 | local wrapper executor (`opencode-softos`) | fixed by repository-owned OpenCode profile to `lmstudio/prism-ml/bonsai-27b` | runtime probe; unavailable if executable/profile/model endpoint cannot be resolved |
| `opencode-free` | cloud/free | declared conservatively | generic direct OpenCode cloud executor (`executable: opencode`) | dynamically choose only from currently available OpenCode `*-free` candidates after capability filtering; deterministic ordering/tie-break is configuration-owned and testable; resolved model MUST reach subprocess overlay | runtime discovery; no matching candidate is `MODEL_UNAVAILABLE`; quota/provider errors map to normalized states |
| `opencode-go` | cloud/paid-low | declared conservatively | same generic direct OpenCode cloud executor as Free when authenticated | dynamic after OpenCode-managed authentication exposes the pool; no permanent model name; resolved model MUST reach subprocess overlay after valid auth evidence | `AUTH_UNCONFIGURED` until current OpenCode evidence proves authentication is configured |

The implementation must validate schema version, unique resource IDs, executor references, field types, supported policy values, and forbidden credential/model fields. Free and Go resolution must use an injectable discovery boundary so tests use fixtures, not network or real credentials.

### Availability states

The normalized V1 vocabulary is:

`AVAILABLE`, `BUSY`, `CAPACITY_EXHAUSTED`, `QUOTA_EXHAUSTED`, `AUTH_UNCONFIGURED`, `AUTH_FAILED`, `MODEL_UNAVAILABLE`, `PROVIDER_DOWN`, `COOLDOWN`, and `UNKNOWN`.

V1 needs deterministic parsing, filtering, diagnostics, and tests for these states; it does not need a scheduler that persists or transitions them. Unknown/unrecognized runtime evidence maps to `UNKNOWN` and cannot be selected as if available.

### Security and data policy

- No credential, token, auth response, prompt secret, or environment value is committed, logged, or serialized into policy/evidence.
- OpenCode authentication remains external and machine-local. `opencode-go` must not claim availability until an existing supported OpenCode diagnostic proves it.
- Cloud-resource metadata includes a data-sensitivity compatibility field/filter point. V1 must represent `local-only` versus `cloud-eligible` work without asserting privacy guarantees that current providers do not prove.
- Diagnostics redact provider output to normalized state and safe reason codes. Raw auth/provider payloads are not persisted.

## Canonical execution process

The policy and supervisor skill must encode this ordered process:

```text
Product Slice
  -> Execution Task
  -> Dependency DAG
  -> Classification
  -> Patch Unit decomposition
  -> Capability filter
  -> Execution policy / resource selection
  -> Execution
  -> Focused verification
  -> bounded repair OR re-decomposition OR escalation
  -> Integrated verification
  -> Independent review
```

Definitions:

- **Product Slice**: approved product/spec ownership unit and acceptance boundary.
- **Execution Task**: executable responsibility derived from the slice, with dependencies and verification intent.
- **Patch Unit**: smallest useful implementation assignment retaining real reasoning; it is not a line-number replacement recipe.
- **Dependency DAG**: acyclic ordering of execution tasks/Patch Units with explicit prerequisites and an integrated verification join.

### Patch Unit heuristics

A preferred Patch Unit has one authorized write target, one primary objective, few relevant symbols, decided architecture/contract, low architectural context, one focused verification, and a small bounded diff. These are heuristics, not hard numeric validity limits. Local work uses one fresh worker session per Patch Unit where practical. Before escalating reducible work, the supervisor considers re-decomposition.

### Classification and selection

Selection follows exactly:

```text
work -> decompose -> classify -> derive required capabilities
     -> filter unavailable/incompatible resources
     -> apply tier priority -> select logical resource
     -> resolve model inside the selected resource
```

Priority tables:

| Work class/role | Ordered candidates before filtering |
| --- | --- |
| Supervisor/orchestration | Codex, Cursor, `opencode-go` |
| High complexity / architecture / planning | Codex, Cursor, `opencode-go` |
| Medium-high | Cursor, `opencode-go`, `opencode-free`, `opencode-local` only after suitable Patch Unit decomposition |
| Medium-low | `opencode-local`, `opencode-free`, `opencode-go` |
| Micro / Patch Unit | `opencode-local`, `opencode-free`, `opencode-go` |
| Independent review | Codex, Cursor, `opencode-go` |

Capability filtering precedes priority. At minimum it considers tool calling, write permission, context suitability, architecture responsibility, data sensitivity, availability/auth, and capacity. Reviewer candidates are then filtered to exclude the supervisor, implementer, and any identity that produced the artifact under review. The current supervisor never self-reviews.

### Failure semantics

| Outcome | Meaning | Required next decision |
| --- | --- | --- |
| fallback | preferred capable resource is unavailable because of auth, quota, provider, model, cooldown, or capacity | select the next still-capable resource for unchanged work |
| repair | output is near-valid and a bounded correction preserves the same unit/contract | allow a configured small attempt bound, then stop |
| re-decomposition | work/output proves oversized, context-heavy, or separable | replace the unit with smaller DAG nodes and reclassify/filter |
| escalation | irreducible work requires stronger capability | route upward with evidence; never blindly downgrade unchanged work |

Implementation success requires both a zero executor exit and an authorized non-empty diff, unless the Patch Unit explicitly declares a verified no-op contract. For an implementation worker, exit `0` plus zero authorized diff plus no explicit blocker is `INVALID_IMPLEMENTATION`, not success. Any unauthorized write is `SCOPE_VIOLATION`. Structurally invalid or invented contracts are `INVALID_IMPLEMENTATION`.

Attempt bounds are policy data, small, finite, and testable. Exhaustion produces an explicit blocker/escalation package rather than an unbounded loop.

## Full-run validation contract

The `full-run-validation` slice validates the process with the approved `git-scope-ignore-hygiene` slice from `deterministic-repository-verification-hardening`.

Preconditions:

1. this spec and its generated plan have received human approval through canonical gates;
2. slices `opencode-resource-pools`, `patch-unit-execution-policy`, and `portable-coding-playbook` have passed focused verification and independent review;
3. the source spec remains approved and its `git-scope-ignore-hygiene` slice is still pending;
4. a dedicated `coding-execution-runtime-v1` validation/evidence worktree is materialized for this feature; it owns only this feature's allowed validation, documentation, and evidence changes and must not modify the source slice implementation targets;
5. a distinct cross-spec execution worktree is materialized for `deterministic-repository-verification-hardening` slice `git-scope-ignore-hygiene`; it is governed exclusively by that approved source spec/plan, owns `flowctl/gittools.py` and `flowctl/test_release_scope_drift.py`, and receives the Patch Unit implementation work;
6. neither preserved historical worktree is opened as an execution workdir or modified;
7. `opencode-local` reports `AVAILABLE`, or the evidence records a policy-valid fallback without pretending local execution occurred.

Required run shape:

1. capture the identities, base refs, clean Git fingerprints, allowed targets, and governing spec/plan hashes for both the V1 validation/evidence worktree and the separate cross-spec execution worktree;
2. derive execution tasks and an acyclic Patch Unit DAG from the approved slice, keeping `flowctl/gittools.py` and `flowctl/test_release_scope_drift.py` ownership explicit;
3. classify each Patch Unit, derive capabilities, and record the filtered candidate set and selected logical resource;
4. prefer `opencode-local` for suitable Patch Units, each in a fresh bounded worker session; never assign the whole slice monolithically to Bonsai;
5. after each unit, capture executor status, authorized diff inventory, focused verification, and any fallback/repair/re-decomposition/escalation decision;
6. run the approved slice's integrated verification only after all DAG prerequisites pass;
7. obtain read-only independent review from an eligible Codex, Cursor, or `opencode-go` identity that neither supervised nor implemented the reviewed artifacts;
8. prove reviewer Git state is identical before/after and package the final acceptance evidence;
9. prove the V1 validation/evidence worktree did not change `flowctl/gittools.py` or `flowctl/test_release_scope_drift.py`, the cross-spec execution worktree changed only files authorized by its source slice, and neither preserved historical worktree was used or modified.

The canonical full-run document must define an evidence schema/table containing: run ID; V1 validation/evidence worktree identity; cross-spec execution worktree identity; immutable source spec and plan hashes for both governing contexts; base refs and before/after Git fingerprints for both worktrees; allowed-target inventories; DAG and Patch Unit IDs; classifications; capabilities; resource candidates/selection; resolved model evidence held at the harness boundary; availability state; attempt outcome; diff fingerprint; focused/integrated command results; independent reviewer identity/result; before/after reviewer Git fingerprints; explicit proof that ownership did not cross between worktrees; proof that both preserved historical worktrees were unused and unmodified; and final PASS/BLOCKED status. It must redact secrets and raw auth/provider payloads.

Full-run PASS requires:

- at least one suitable Patch Unit actually executed through `opencode-local` with the canonical Bonsai worker;
- every implementation unit has an authorized non-empty diff or an explicitly permitted verified no-op (the target slice currently permits no no-op);
- focused verification passes per unit;
- no scope violation or invalid implementation remains unresolved;
- integrated verification from the approved target spec passes;
- independent review passes and changes no file;
- the final target slice diff stays within its approved targets;
- the V1 validation/evidence worktree contains only this feature's allowed validation, documentation, and evidence changes and does not modify the source slice implementation targets;
- the separate cross-spec execution worktree is governed by the approved `deterministic-repository-verification-hardening` source spec/plan and contains the `git-scope-ignore-hygiene` implementation changes;
- evidence records both worktree identities, both governing spec/plan hash pairs, and proves no ownership crossed between the worktrees;
- evidence proves the preserved worktrees were not execution workdirs and were not modified.

If local is unavailable before any local Patch Unit can run, the run may demonstrate fallback behavior but cannot satisfy this V1 full-run PASS gate; report `BLOCKED` and rerun after local availability is restored.

## Slice Breakdown

```yaml
- name: opencode-resource-pools
  repo: sdd-workspace-boilerplate
  targets:
    - ../../workspace.config.json
    - ../../opencode.json
    - ../../flowctl/agent_resources.py
    - ../../flowctl/agent_executors.py
    - ../../flowctl/agent_process_execution.py
    - ../../flowctl/tests/test_agent_resources.py
    - ../../flowctl/tests/test_agent_process_execution.py
    - ../../docs/opencode-execution-resources.md
  hot_area: portable OpenCode resource registry profile resolution diagnostics and harness process overlay
  depends_on: []
  execution_difficulty: high
  preferred_implementer: cursor
  preferred_reviewer: codex
  slice_mode: implementation-heavy
  surface_policy: required
  minimum_valid_completion: three validated logical resources with portable Bonsai local configuration dynamic free and Go resolution normalized availability states and resource-aware subprocess environment overlay that applies resolved cloud models without Bonsai wrapper leakage
  validated_noop_allowed: false
  acceptable_evidence:
    - schema and forbidden credential/model field tests
    - legacy executor selection still works through flow agent run
    - opencode-local still launches local wrapper/profile and resolves Bonsai with capacity one without adding generic model flags
    - opencode-free resolves to direct OpenCode cloud execution and process overlay contains the dynamically selected free model
    - opencode-go cannot launch while AUTH_UNCONFIGURED
    - authenticated Go fixture resolves dynamic model and process overlay uses it
    - Free/Go overlay never contains Bonsai unless that model were actually returned as the selected cloud candidate
    - environment overlay preserves inherited safe environment and credentials/auth payloads are never serialized
    - no generic model/provider CLI flags
    - existing executor/process tests remain green

- name: patch-unit-execution-policy
  repo: sdd-workspace-boilerplate
  targets:
    - ../../policies/coding-execution-runtime-v1.json
    - ../../flowctl/coding_execution_policy.py
    - ../../flowctl/tests/test_coding_execution_policy.py
  hot_area: Patch Unit decomposition capability filtering resource priority and bounded failure policy
  depends_on:
    - opencode-resource-pools
  execution_difficulty: high
  preferred_implementer: cursor
  preferred_reviewer: codex
  slice_mode: implementation-heavy
  surface_policy: required
  minimum_valid_completion: validated portable policy encodes the canonical process priorities reviewer independence and deterministic failure decisions without a scheduler
  validated_noop_allowed: false
  acceptable_evidence:
    - schema DAG and classification validation tests
    - capability filtering precedes priority and model resolution
    - local-first selection occurs only for suitable Patch Units
    - fallback repair re-decomposition and escalation tests are distinct and bounded
    - zero-diff scope-violation invalid-contract and reviewer-independence tests

- name: portable-coding-playbook
  repo: sdd-workspace-boilerplate
  targets:
    - ../../.agents/skills/softos-coding-execution-supervisor/**
    - ../../workspace.skills.json
  hot_area: reusable supervisor skill and portable registration
  depends_on:
    - patch-unit-execution-policy
  execution_difficulty: medium-high
  preferred_implementer: cursor
  preferred_reviewer: codex
  slice_mode: governance
  surface_policy: required
  minimum_valid_completion: a registered reusable skill reconstructs canonical context and executes the complete bounded process without giant ad-hoc prompts or machine-local-only state
  validated_noop_allowed: false
  acceptable_evidence:
    - complete SKILL.md with routing inputs outputs stop conditions and evidence handoff
    - workspace skill registry validates and sync dry-run remains deterministic
    - examples reference specs plans policies and repo rules rather than copying mutable context
    - supervisor and reviewer identities are explicitly separated

- name: full-run-validation
  repo: sdd-workspace-boilerplate
  targets:
    - ../../docs/coding-execution-runtime-v1-full-run.md
  hot_area: real git-scope-ignore-hygiene execution protocol and evidence package
  depends_on:
    - opencode-resource-pools
    - patch-unit-execution-policy
    - portable-coding-playbook
  execution_difficulty: high
  preferred_implementer: cursor
  preferred_reviewer: codex
  slice_mode: verification-only
  surface_policy: optional
  minimum_valid_completion: execute and document one complete non-monolithic local-first run of the approved git-scope-ignore-hygiene slice with focused integrated and independent-review evidence
  validated_noop_allowed: false
  acceptable_evidence:
    - both worktree identities both governing spec/plan hash pairs and clean-state fingerprints
    - proof the V1 worktree did not modify source-slice targets and the cross-spec worktree stayed within its own approved ownership
    - explicit execution-task and Patch Unit DAG
    - at least one real opencode-local Bonsai Patch Unit
    - focused verification and bounded decision record per unit
    - passing integrated target-slice verification
    - independent read-only reviewer PASS with identical before and after Git fingerprints
    - proof preserved historical worktrees were neither used nor modified
```

## Target ownership summary

Slice target sets are pairwise disjoint. The spec itself remains orchestrator-owned and is not a slice write target. `opencode-resource-pools` owns the resource registry, harness selection/overlay boundary (`agent_executors.py`, `agent_process_execution.py`), and their focused tests. `full-run-validation` owns only its canonical protocol/evidence document in the V1 validation/evidence worktree. Implementation changes for `git-scope-ignore-hygiene` occur only in a separate cross-spec execution worktree, remain governed exclusively by the already-approved `deterministic-repository-verification-hardening` source spec/plan, and retain that slice's ownership of `flowctl/gittools.py` and `flowctl/test_release_scope_drift.py`.

## Acceptance criteria

1. Exactly four slices preserve the four product outcomes and have pairwise-disjoint write ownership.
2. Core and generic adapter invocation contain no model/provider-specific routing branch or model flag; `flowctl/agent_executor_adapters.py` is not modified unless later evidence proves unavoidable.
3. `opencode-local` resolves the repository-owned `softos-local-worker` to `lmstudio/prism-ml/bonsai-27b`, reasoning on, bounded sessions, and logical capacity `1`, launching through the existing local wrapper executor.
4. `opencode-free` discovers currently available free models dynamically, executes through a direct OpenCode cloud executor without the Bonsai wrapper, and applies the resolved model to the spawned process via a validated environment overlay; no specific free model is a permanent contract.
5. `opencode-go` is representable, begins `AUTH_UNCONFIGURED`, cannot launch until supported auth evidence exists, and after valid evidence applies the dynamically resolved model to the spawned process; no token name, token value, or fake auth implementation is added.
6. The harness preserves logical resource ID through selection and subprocess launch even when Free and Go share one underlying executor.
7. `execute_subprocess()` merges validated resource overlays with inherited environment without wholesale replacement or credential serialization.
8. Legacy `flow agent run <executor-id> ...` continues working without a new `--resource` flag.
9. All ten availability states are validated and unavailable/incompatible resources are filtered before priority.
10. Product Slice, Execution Task, dependency DAG, and Patch Unit are distinct validated concepts.
11. The complete canonical process, priority table, capability filters, reviewer independence, and failure semantics are machine-readable and documented.
12. Repair and retry are bounded; reducible failures consider re-decomposition before stronger/paid escalation; unchanged work is never blindly downgraded after capability failure.
13. Implementation exit `0` with zero authorized diff and no explicit blocker is rejected; unauthorized writes and invented contracts receive required error classifications.
14. The reusable skill is repository-owned and registered through existing skill conventions.
15. The real full run satisfies every PASS condition or reports an evidence-backed `BLOCKED`; fallback-only evidence cannot masquerade as a local Bonsai validation.
16. No durable scheduler, lease, run database, parallel execution engine, secret store, automatic merge/release, or preserved-worktree mutation is introduced.
17. All focused tests, spec CI, root repo CI applicable to changed targets, integrated target-slice verification, and independent reviews pass before closeout.
18. No commit, push, PR, merge, release, or publication is authorized by this spec.

## Test Plan

This root-repo feature uses slice-owned test targets and slice-specific verification commands instead of feature-wide `[@test]` references, because the canonical planner propagates every feature-wide linked test to every slice in the same repo.

- `opencode-resource-pools` owns `flowctl/tests/test_agent_resources.py` and `flowctl/tests/test_agent_process_execution.py` and runs only those prospective resource/harness test targets for focused verification.
- `patch-unit-execution-policy` owns `flowctl/tests/test_coding_execution_policy.py` and runs only that prospective policy test target for focused verification.
- `portable-coding-playbook` owns no Python test target; its focused verification is the canonical skill registry validation and deterministic sync dry-run declared by its slice evidence contract.
- `full-run-validation` owns no implementation test target and inherits no prospective linked tests from earlier slices; it records the source slice's integrated verification as cross-spec execution evidence without acquiring ownership of those tests.

The two prospective test targets owned by `opencode-resource-pools` and the one owned by `patch-unit-execution-policy` are required outputs of their respective owning implementation slices. Each must exist before its owning slice is verified; absence is a failure, not a reason to broaden test discovery or ownership.

## Verification Matrix

```yaml
- name: spec-ci
  level: custom
  command: python3 ./flow workspace exec -- python3 ./flow ci spec specs/features/coding-execution-runtime-v1.spec.md --json
  blocking_on: [ci]
  environments: [local]
  notes: validates schema targets slice governance slice-local test ownership and execution contracts

- name: executor-resource-tests
  level: integration
  command: python3 ./flow workspace exec -- python3 -m pytest flowctl/tests/test_agent_resources.py flowctl/tests/test_agent_process_execution.py -q
  blocking_on: [ci]
  environments: [local]
  notes: focused verification owned only by opencode-resource-pools; proves resource metadata dynamic model resolution process overlay merge and legacy executor selection; uses fixtures and requires no vendor network credentials or local model runtime

- name: patch-unit-policy-tests
  level: integration
  command: python3 ./flow workspace exec -- python3 -m pytest flowctl/tests/test_coding_execution_policy.py -q
  blocking_on: [ci]
  environments: [local]
  notes: focused verification owned only by patch-unit-execution-policy

- name: existing-agent-executor-regression
  level: integration
  command: python3 ./flow workspace exec -- python3 -m pytest flowctl/tests/test_agent_executors.py flowctl/tests/test_agent_executor_adapters.py flowctl/tests/test_agent_process_execution.py -q
  blocking_on: [ci]
  environments: [local]
  notes: proves model-agnostic invocation containment and existing executor behavior remain intact

- name: skills-contract
  level: custom
  command: python3 ./flow workspace exec -- python3 ./flow skills doctor --json
  blocking_on: [ci]
  environments: [local]
  notes: validates the portable supervisor skill registration

- name: real-full-run
  level: integration
  command: follow docs/coding-execution-runtime-v1-full-run.md against approved slice git-scope-ignore-hygiene and attach its deterministic evidence package
  blocking_on: [ci]
  environments: [local]
  notes: manual supervisor gate because V1 intentionally does not add a durable scheduler; PASS requires real local Bonsai execution and independent review

- name: root-repo-ci
  level: custom
  command: python3 ./flow workspace exec -- python3 ./flow ci repo sdd-workspace-boilerplate --spec coding-execution-runtime-v1 --json
  blocking_on: [ci]
  environments: [local]
  notes: runs applicable root repository CI after all slices integrate
```

## Rollout

Roll out in dependency order. Resource configuration and diagnostics land first; policy then consumes only their logical contract; the skill consumes the validated policy; the real run starts last. Machine-local OpenCode/LM Studio state is checked but never committed. `opencode-go` remains non-selectable while auth is unconfigured.

## Rollback and cleanup

- Revert only the declared targets in reverse dependency order; preserve unrelated executor and OpenCode configuration.
- Removing the feature restores the previous three-executor behavior and does not delete or alter machine-local OpenCode auth/configuration.
- Clean only worktrees created for this feature and the future full run through canonical worktree inventory/cleanup commands after evidence is preserved.
- Never clean, reset, modify, or consume the two preserved historical worktrees named in Out of scope.
- Evidence under `.flow/**` may be archived/cleaned as operational state after canonical documentation retains required fingerprints; it never becomes product configuration.

## Stop conditions

- Stop and refine this spec before writing outside declared targets or introducing overlapping slice ownership.
- Stop if implementation requires model/provider branching or generic model flags in Core/adapters.
- Stop if Free/Go execution still routes through `opencode-softos` / `softos-local-worker` unless the selected cloud candidate is intentionally Bonsai.
- Stop if resolved Free/Go models affect diagnostics only and do not reach the spawned OpenCode process.
- Stop if `execute_subprocess()` replaces the inherited environment wholesale or serializes credentials/auth payloads into overlay or evidence.
- Stop if OpenCode's current repository-supported config cannot portably own the worker/profile; do not silently fall back to `~/.config` as canonical.
- Stop if free/Go model discovery cannot be tested through an injectable boundary without network/credentials.
- Stop if Go authentication cannot be distinguished from provider/model availability using existing OpenCode evidence; retain `AUTH_UNCONFIGURED` rather than inventing a contract.
- Stop if any secret or raw auth/provider payload appears in Git or evidence.
- Stop if policy enforcement requires durable scheduling, leases, failover, or a run database; defer that scope.
- Stop the full run if the approved source slice changes, a preserved worktree would be used, local Bonsai never executes, ownership is violated, focused/integrated verification fails beyond bounded repair, or an independent eligible reviewer is unavailable.
- Stop the full run if the V1 validation/evidence worktree and cross-spec execution worktree are not distinct, either worktree crosses its governing ownership boundary, or hashes for either governing spec/plan context cannot be recorded.
- Stop planning until a human re-approves this draft through the canonical spec gate; the planner must not self-approve.
