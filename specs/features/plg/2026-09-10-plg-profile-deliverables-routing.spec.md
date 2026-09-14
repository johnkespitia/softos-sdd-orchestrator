---
schema_version: 3
name: "PLG profile deliverables routing"
description: "Route SoftOS process deliverables for PLG specs through a profile-owned artifact layout while preserving default SoftOS paths and legacy PLG artifact reads."
status: approved
owner: platform
single_slice_reason: ""
multi_domain: true
phases: []
depends_on:
  - specs/000-foundation/spec-as-source-operating-model.spec.md
  - specs/000-foundation/spec-driven-delivery-and-infrastructure.spec.md
  - specs/000-foundation/repo-routing-and-worktree-orchestration.spec.md
  - specs/features/softos-spec-approval-formal-gate.spec.md
  - specs/features/softos-plan-approval-formal-gate.spec.md
  - specs/features/softos-central-policy-check.spec.md
  - specs/features/softos-evidence-bundle-status.spec.md
required_runtimes: []
required_services: []
required_capabilities: []
stack_projects: []
stack_services: []
stack_capabilities: []
targets:
  - ../../profiles/plg.json
  - ../../profiles/README.md
  - ../../profiles/es/README.es.md
  - ../../flow
  - ../../flowctl/parser.py
  - ../../flowctl/features.py
  - ../../flowctl/ci.py
  - ../../flowctl/evidence.py
  - ../../flowctl/policy.py
  - ../../flowctl/agent_handoff.py
  - ../../flowctl/profiles.py
  - ../../flowctl/test_profiles.py
  - ../../flowctl/test_plan_approval_gate.py
  - ../../flowctl/test_ci_spec.py
  - ../../flowctl/test_evidence.py
  - ../../flowctl/test_policy_check.py
  - ../../flowctl/test_agent_handoff.py
  - ../../flowctl/test_slice_governance.py
  - ../../specs/features/plg/2026-09-10-plg-profile-deliverables-routing.spec.md
---

# PLG profile deliverables routing

## Objective

Create a PLG-specific profile contract for this harness so SoftOS process deliverables generated for PLG specs are written under PLG-scoped folders instead of being mixed with base SoftOS platform artifacts.

The new routing must be profile-based. `flow` may accept `--profile plg` and must infer `plg` from specs under `specs/features/plg/**` when that inference is unambiguous.

## Context

Root `specs/**` remains the canonical source of truth for product, platform, and orchestration behavior. `.flow/**` remains operational state. This spec changes where selected operational artifacts are written and read; it does not make `.flow/**` canonical.

Current SoftOS commands write most process artifacts to shared roots:

| Artifact family | Current default root |
| --- | --- |
| Plans | `.flow/plans` |
| Spec review reports | `.flow/reports` |
| CI reports | `.flow/reports/ci` |
| Evidence bundles | `.flow/reports/evidence` |
| Workflow reports and slice handoffs/verifications | `.flow/reports/**` |
| Runs/state | `.flow/runs` and `.flow/state` where present |

PLG product specs now live under `specs/features/plg/`. Generated process artifacts for those specs should be easier to consult as a PLG delivery stream without moving or deleting existing SoftOS artifacts.

## Foundations Aplicables

- `specs/000-foundation/spec-as-source-operating-model.spec.md`: preserves `specs/**` as canonical and `.flow/**` as operational output.
- `specs/000-foundation/spec-driven-delivery-and-infrastructure.spec.md`: governs `flow ci`, process reports, and release-blocking evidence.
- `specs/000-foundation/repo-routing-and-worktree-orchestration.spec.md`: keeps planning and slice execution routed through the root orchestrator.

## Domains Aplicables

No aplica domain porque this is a SoftOS process/platform routing feature. It does not introduce product domain entities or alter backend/frontend business behavior.

## Problem To Solve

Generated PLG delivery artifacts are mixed with base SoftOS platform artifacts in shared `.flow` roots. This makes later consultation harder and can make operators inspect unrelated plans, reports, evidence, runs, or state when they are trying to follow PLG product delivery.

The fix must not be manual relocation. It must be an explicit profile contract and a shared resolver used by commands that write or read process deliverables.

## Governing Decision

Use profile-based deliverable routing.

| Decision | Contract |
| --- | --- |
| Profile identity | The PLG profile id is `plg`. |
| Profile file | The profile is materialized as `profiles/plg.json`. |
| CLI flag | `--profile` is optional for profile-aware commands. When supplied, it takes precedence over auto-detection. |
| Auto-detection | Specs under `specs/features/plg/**` resolve to profile `plg` when no explicit profile is supplied. |
| Default behavior | Specs outside configured `spec_roots` continue to use existing shared `.flow` roots. |
| Backward compatibility | Read paths must search profile-scoped paths first, then legacy paths, unless a command is explicitly write-only. |
| Migration | No command manually moves existing `.flow` artifacts in this spec. Any future migration requires a separate explicit spec. |

Prohibited alternatives:

- Do not hardcode PLG path checks independently inside unrelated command bodies.
- Do not route by slug prefix alone.
- Do not require operators to manually move `.flow` files.
- Do not delete, rename, or rewrite existing legacy artifacts as part of routing.
- Do not change frontend or backend product code.

## Profile Contract

`profiles/plg.json` must be valid JSON with this minimum shape:

```json
{
  "id": "plg",
  "name": "PLG Platform",
  "spec_roots": [
    "specs/features/plg"
  ],
  "deliverables": {
    "plans": ".flow/plans/plg",
    "reports": ".flow/reports/plg",
    "ci_reports": ".flow/reports/ci/plg",
    "evidence": ".flow/evidence/plg",
    "runs": ".flow/runs/plg",
    "state": ".flow/state/plg"
  }
}
```

Required validation:

- `id` must be a non-empty lowercase slug.
- `spec_roots` must be non-empty, workspace-relative paths under `specs/**`.
- `deliverables` values must be workspace-relative paths under `.flow/**`.
- The profile may include extra metadata only if loaders ignore unknown keys safely.
- A missing or invalid explicit profile must fail with a clear error before writing artifacts.

## Profile Resolution Order

For each profile-aware command, resolve deliverable roots in this order:

1. If the command receives `--profile <id>`, load `profiles/<id>.json` or another documented profile lookup path implemented by the profile loader.
2. If no `--profile` is supplied and the command receives a spec path or slug, resolve the canonical spec path, then compare it to every configured profile `spec_roots`.
3. If exactly one profile matches the spec path, use that profile.
4. If no profile matches, use the existing default SoftOS roots.
5. If more than one profile matches, fail before writing and require explicit `--profile`.

Resolution must happen after `resolve_spec()` succeeds and before computing write/read artifact paths. Slug-only invocations are eligible for auto-detection only after the slug resolves to a unique spec path.

## Deliverable Path Contract

| Logical key | Default root | PLG root | Write behavior | Read behavior |
| --- | --- | --- | --- | --- |
| `plans` | `.flow/plans` | `.flow/plans/plg` | New PLG plans write JSON/MD to PLG root. | Search PLG root first, then default root. |
| `reports` | `.flow/reports` | `.flow/reports/plg` | PLG spec reviews, handoffs, and slice verification reports write to PLG root when implemented. | Report scanners search profile and default roots without duplicates. |
| `ci_reports` | `.flow/reports/ci` | `.flow/reports/ci/plg` | `flow ci spec <plg-spec>` writes JSON/MD to PLG CI root. | Evidence/report readers include both roots during transition. |
| `evidence` | `.flow/reports/evidence` | `.flow/evidence/plg` | PLG evidence bundles write to the profile evidence root. | Evidence status includes reports from profile and legacy report roots. |
| `runs` | `.flow/runs` | `.flow/runs/plg` | Profile-aware run writers use PLG root only when they already write runs. | Existing run readers keep default behavior unless they directly read per-spec runs. |
| `state` | `.flow/state` | `.flow/state/plg` | This spec defines the root but does not require state migration in the first implementation. | Approval/status commands must continue to read legacy state unless state routing is explicitly implemented and tested. |

The first implementation must support `plans`, `reports`, `ci_reports`, and `evidence` where those command surfaces already exist. `runs` and `state` are profile contract keys for forward compatibility; do not migrate state unless all approval/status callers are updated with profile-first plus legacy fallback.

## Executable Surface Inventory

| Surface | Mandatory change | Compatibility requirement |
| --- | --- | --- |
| `profiles/plg.json` | Add the PLG profile file with spec roots and deliverable roots. | Keep existing profile directory examples intact. |
| `flowctl/profiles.py` | Add shared profile loading, validation, spec-root matching, deliverable root construction, and fallback path helpers. | Loader must return default roots for non-PLG specs. |
| `flowctl/parser.py` | Add optional `--profile` to `flow plan`, `flow plan-approve`, `flow plan-approval-status`, `flow spec review`, `flow ci spec`, and `flow evidence status|bundle`. | Commands remain valid without the flag. |
| `flow` | Resolve profile context once per command wrapper and pass profile-aware roots to `flowctl` modules. | Do not duplicate PLG path logic in each wrapper. |
| `flowctl/features.py` | Route plan writes, plan approval reads, spec review writes, slice handoff/verification writes when those commands directly consume plan/report roots. | `plan-approval-status` and `slice start` search profile plan first then legacy plan. |
| `flowctl/ci.py` | Route `flow ci spec <spec>` reports to `ci_reports`; default/all/changed behavior remains stable. | Non-PLG specs keep `.flow/reports/ci`. |
| `flowctl/evidence.py` | Route evidence bundle writes and report scans through profile-aware roots. | Existing `.flow/reports/evidence/**` remains readable during transition. |
| `flowctl/policy.py` | Use the same resolved plan path/fallback as plan approval for plan-sensitive policy checks. | Legacy plan approvals remain valid. |
| `flowctl/agent_handoff.py` | Only update if handoff generation directly reads plan/report paths for the target spec. | Preserve current bundle shape and existing default paths for non-PLG specs. |
| Tests | Add unit coverage for profile resolution, deliverable construction, legacy fallback, and non-PLG defaults. | Tests must use temp directories, not the real `.flow` tree. |

## Algorithm

1. Add a profile loader that discovers JSON profile definitions from `profiles/*.json`.
2. Validate the loaded profile before returning it.
3. Add a profile context object with:
   - `profile_id`;
   - resolved workspace-relative deliverable roots;
   - default deliverable roots;
   - read candidates for fallback-enabled artifacts.
4. Add an optional `--profile` flag to profile-aware commands.
5. For commands that take a spec identifier:
   - resolve the spec path;
   - resolve the profile using the resolution order above;
   - choose write roots from the selected profile or default roots.
6. For plan reads:
   - construct candidate plan JSON paths as `[profile_plans/<slug>.json, default_plans/<slug>.json]` when profile is active;
   - remove duplicates while preserving order;
   - use the first existing candidate;
   - if no candidate exists, report missing plan and include both candidate paths in JSON payloads when helpful.
7. For report scans:
   - scan profile report root first and legacy report root second;
   - de-duplicate by resolved filesystem path;
   - do not treat duplicate legacy/profile reports as an error.
8. For writes:
   - create parent directories as needed;
   - write new PLG artifacts only to the profile root;
   - never move, copy, or delete legacy artifacts.

## Compatibility Matrix

| Scenario | Expected outcome |
| --- | --- |
| `flow plan specs/features/plg/<slug>.spec.md` | Writes `.flow/plans/plg/<slug>.json` and `.flow/plans/plg/<slug>.md`. |
| `flow plan --profile plg specs/features/plg/<slug>.spec.md` | Writes to the same PLG plan root. |
| `flow plan specs/features/non-plg.spec.md` | Writes `.flow/plans/<slug>.json` and `.flow/plans/<slug>.md`. |
| `flow plan-approval-status specs/features/plg/<slug>.spec.md --json` with both plan paths present | Reports the profile plan path. |
| Same status command with only legacy plan present | Reads `.flow/plans/<slug>.json` and does not return `missing_plan`. |
| `flow plan-approve` for PLG with only legacy plan present | May approve legacy plan during transition and must record the resolved plan path. |
| `flow spec review specs/features/plg/<slug>.spec.md --json` | Writes report to `.flow/reports/plg/<slug>-spec-review.md`. |
| `flow ci spec specs/features/plg/<slug>.spec.md --json` | Writes report pair under `.flow/reports/ci/plg/`. |
| `flow evidence bundle specs/features/plg/<slug>.spec.md --json` | Writes bundle outputs under `.flow/evidence/plg/` and can include legacy reports. |
| Any non-PLG equivalent command | Uses current default roots and payload paths. |

## Migration And Legacy Behavior

Already generated PLG artifacts in default locations remain valid transition inputs. This includes the temporal projection plan currently present as `.flow/plans/2026-09-10-backend-owned-temporal-projection-contract.*`.

Implementation must not require manual relocation for correctness. If both profile-scoped and legacy artifacts exist for the same slug, the profile-scoped artifact wins for reads because it represents the new contract. Legacy files are retained and ignored only when a profile-scoped counterpart exists.

No migration command is required by this spec. If a future migration is desired, it must be specified separately with explicit copy/move/delete rules, dry-run behavior, and rollback evidence.

## Stop Conditions

- Stop before implementation if this spec has not passed `flow spec review` and received human approval.
- Stop if profile resolution is ambiguous across two or more matching profiles.
- Stop before writing if an explicit `--profile` id is missing or invalid.
- Stop before changing `.flow/state` routing unless approval/status compatibility is fully specified and tested in the same change.
- Stop before touching frontend/backend product repositories; this spec is root harness process work only.
- Stop before deleting or relocating legacy `.flow` artifacts.

## Slice Breakdown

```yaml
- name: profile-contract-spec
  targets:
    - ../../profiles/plg.json
    - ../../profiles/README.md
    - ../../profiles/es/README.es.md
    - ../../specs/features/plg/2026-09-10-plg-profile-deliverables-routing.spec.md
  hot_area: profile contract and canonical spec
  depends_on: []
  slice_mode: governance
  surface_policy: required
  minimum_valid_completion: approved-ready spec and valid PLG profile shape are defined before implementation
  validated_noop_allowed: false
  acceptable_evidence:
    - python3 ./flow workspace exec -- python3 ./flow spec review specs/features/plg/2026-09-10-plg-profile-deliverables-routing.spec.md --json

- name: profile-loader-and-resolution
  targets:
    - ../../flow
    - ../../flowctl/parser.py
    - ../../flowctl/profiles.py
    - ../../flowctl/test_profiles.py
  hot_area: shared profile loader and CLI resolution
  depends_on:
    - profile-contract-spec
  slice_mode: implementation-heavy
  surface_policy: required
  minimum_valid_completion: shared resolver supports explicit profile, spec-root auto-detection, default fallback and ambiguity failure
  validated_noop_allowed: false
  acceptable_evidence:
    - python3 ./flow workspace exec -- python3 -m pytest -q flowctl/test_profiles.py

- name: plan-artifact-routing
  targets:
    - ../../flow
    - ../../flowctl/parser.py
    - ../../flowctl/features.py
    - ../../flowctl/policy.py
    - ../../flowctl/test_plan_approval_gate.py
    - ../../flowctl/test_policy_check.py
    - ../../flowctl/test_slice_governance.py
  hot_area: plan write/read and approval compatibility
  depends_on:
    - profile-loader-and-resolution
  slice_mode: implementation-heavy
  surface_policy: required
  minimum_valid_completion: PLG plan writes use profile root and plan-sensitive readers fall back to legacy root
  validated_noop_allowed: false
  acceptable_evidence:
    - python3 ./flow workspace exec -- python3 -m pytest -q flowctl/test_plan_approval_gate.py flowctl/test_policy_check.py flowctl/test_slice_governance.py

- name: report-and-ci-routing
  targets:
    - ../../flow
    - ../../flowctl/parser.py
    - ../../flowctl/features.py
    - ../../flowctl/ci.py
    - ../../flowctl/test_ci_spec.py
  hot_area: spec review and ci spec report routing
  depends_on:
    - profile-loader-and-resolution
  slice_mode: implementation-heavy
  surface_policy: required
  minimum_valid_completion: PLG spec review and ci spec reports write to profile report roots while non-PLG reports keep default roots
  validated_noop_allowed: false
  acceptable_evidence:
    - python3 ./flow workspace exec -- python3 -m pytest -q flowctl/test_ci_spec.py

- name: evidence-and-handoff-compatibility
  targets:
    - ../../flow
    - ../../flowctl/parser.py
    - ../../flowctl/evidence.py
    - ../../flowctl/agent_handoff.py
    - ../../flowctl/test_evidence.py
    - ../../flowctl/test_agent_handoff.py
  hot_area: evidence bundle and report scanner compatibility
  depends_on:
    - plan-artifact-routing
    - report-and-ci-routing
  slice_mode: implementation-heavy
  surface_policy: required
  minimum_valid_completion: evidence and handoff/report readers include profile-scoped and legacy artifacts without duplicate report entries
  validated_noop_allowed: false
  acceptable_evidence:
    - python3 ./flow workspace exec -- python3 -m pytest -q flowctl/test_evidence.py flowctl/test_agent_handoff.py
```

## Verification Matrix

```yaml
- name: spec-review-profile-routing
  level: custom
  command: python3 ./flow workspace exec -- python3 ./flow spec review specs/features/plg/2026-09-10-plg-profile-deliverables-routing.spec.md --json
  blocking_on:
    - review
    - approval
  environments:
    - local
  notes: proves the spec is approved-ready before implementation

- name: spec-ci-profile-routing
  level: custom
  command: python3 ./flow workspace exec -- python3 ./flow ci spec specs/features/plg/2026-09-10-plg-profile-deliverables-routing.spec.md --json
  blocking_on:
    - ci
  environments:
    - local
  notes: validates structure, dependencies, targets and slice governance after human approval

- name: flowctl-profile-routing-unit
  level: custom
  command: python3 ./flow workspace exec -- python3 -m pytest -q flowctl/test_*.py
  blocking_on:
    - ci
  environments:
    - local
  notes: proves profile resolution, artifact path construction, backward compatibility and non-PLG fallback
```

## Acceptance Criteria

- `profiles/plg.json` exists and validates against the profile contract in this spec.
- New PLG plans route to `.flow/plans/plg/`.
- Plan-sensitive readers can still read existing legacy PLG plans from `.flow/plans/` during transition.
- `flow spec review` for PLG specs writes reports under `.flow/reports/plg/`.
- `flow ci spec` for PLG specs writes CI reports under `.flow/reports/ci/plg/`.
- Default non-PLG specs continue using existing `.flow/plans`, `.flow/reports`, `.flow/reports/ci`, and `.flow/reports/evidence` paths.
- `plan-approval-status` resolves both profile-routed and legacy generated plans.
- Tests cover profile resolution, artifact path construction, backward compatibility, ambiguous-profile failure, and non-PLG fallback.
- `flow ci spec` passes for this spec after human approval.
- No manual `.flow` relocation is required for correctness.

## Test Plan

- Add `flowctl/test_profiles.py` for profile loading, validation, explicit profile selection, spec-root auto-detection, ambiguity failure, and default fallback.
- Extend `flowctl/test_plan_approval_gate.py` for profile-first plan lookup and legacy fallback.
- Extend `flowctl/test_ci_spec.py` for PLG CI report root and non-PLG default report root.
- Extend `flowctl/test_evidence.py` for profile evidence bundle root and legacy report inclusion.
- Extend `flowctl/test_policy_check.py` or `flowctl/test_slice_governance.py` where plan-sensitive policy/slice commands directly resolve plan paths.
- Run `python3 ./flow workspace exec -- python3 -m pytest -q flowctl/test_*.py` after implementation.

## Rollout

Roll out in the root harness only after this spec is approved. Existing commands must remain usable without `--profile`. Operators can start using PLG-scoped artifacts immediately for new PLG runs; legacy artifacts remain readable without migration.

## Rollback

Rollback is code-only: remove profile-aware routing changes and keep `profiles/plg.json` inert if necessary. Because this spec forbids moving or deleting `.flow` artifacts, rollback does not require data restoration.
