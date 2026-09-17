---
name: softos-coding-execution-supervisor
description: Supervises bounded SoftOS coding execution from an approved spec through slices, Patch Units, verification, independent review, and evidence. Use when coordinating implementation without a durable scheduler.
---

# SoftOS Coding Execution Supervisor

The harness that starts a feature run is the `orchestrator`. It owns routing,
decomposition, delegation, gate evaluation, and evidence. Every child run is
explicitly `worker` or `reviewer`; a child never inherits orchestration
authority from the parent conversation.

BMAD remains responsible for intake, spec authoring, planning, workflow choice,
and product lifecycle state. SoftOS runtime roles are a subordinate execution
layer:

```text
BMAD workflow -> approved spec and plan -> SoftOS orchestrator -> worker/reviewer runs
```

## Inputs and source order

Require an approved governing spec, current plan and assigned Product Slice,
explicit repository/worktree/base ref/write ownership, repository rules,
`workspace.config.json`, execution policy, verification requirements, and
reviewer constraints.

Resolve conflicts in this order: spec, approved plan/slice, repository rules,
workspace configuration, execution policy, current evidence. `.flow/**`,
Graphify output, Engram, and session summaries are never product truth.

Stop before execution when approval is absent, a required canonical artifact is
missing, ownership overlaps, or the requested work exceeds the assigned slice.
The supervisor cannot self-approve.

## Bounded process

1. Capture intake and immutable context fingerprints.
2. Resolve the approved plan into disjoint Product Slices and select only the assigned slice.
3. Convert that slice into execution tasks and an acyclic dependency DAG.
4. Decompose tasks into Patch Units with one objective, authorized targets, decided contract, prerequisites, expected diff, and focused verification.
5. Classify each unit and derive capabilities before selecting a resource.
6. Filter resources by tools, write access, context, architecture responsibility, data sensitivity, availability/auth, and capacity. Apply priority only after filtering.
7. Give each child a fresh, compact handoff containing canonical references, not copied mutable context.
8. Accept implementation only with zero exit plus an authorized non-empty diff, unless an explicit verified no-op is allowed.
9. Run focused verification per unit, then integrated verification after DAG prerequisites pass.
10. Obtain read-only independent review from an eligible identity distinct from the supervisor, implementer, and artifact producer.
11. Package final handoff and evidence without committing, pushing, merging, releasing, or publishing.

Patch Units retain real reasoning. Never reduce them to blind line replacements
or assign an oversized Product Slice to a bounded worker.

## Child handoff

Every worker or reviewer handoff includes the governing spec, plan, slice and
policy references, parent/child run ids, worktree/base fingerprint, authorized
targets, objective, prerequisites, selected resource, verification command,
attempt bound, stop conditions, and explicit prohibition on delegation, scope
expansion, commit, and push.

Treat unauthorized writes as `SCOPE_VIOLATION`; zero authorized diff without an
allowed verified no-op or explicit blocker as `INVALID_IMPLEMENTATION`.

## Failure decisions

- **fallback**: unchanged work, next capable resource after availability/auth/quota/provider/model/capacity failure
- **repair**: bounded correction preserving the same unit and contract
- **re-decomposition**: oversized, context-heavy, or separable work becomes smaller DAG nodes
- **escalation**: irreducible work needs stronger capability and evidence is sent upward

Do not loop indefinitely, blindly downgrade unchanged work, or escalate
reducible work before considering re-decomposition.

## Gates G0-G6

- **G0** intake, authority, repo, worktree, and ownership captured.
- **G1** approval, dependencies, rules, capabilities, resources, and fingerprints resolved.
- **G2** slice, DAG, Patch Units, verification intent, and disjoint ownership consistent before coding.
- **G3** child handoffs complete and authorized diff artifacts classified.
- **G4** focused and integrated verification evidence passes.
- **G5** independent read-only review passes.
- **G6** handoffs, fingerprints, outcomes, risks, and canonical state are consistent.

Never advance while the current gate is unsatisfied. Reviewers must record
before/after Git fingerprints and remain unchanged.

## Final evidence

Report completed scope, Patch Unit/DAG outcomes, selected resources, normalized
availability, modified files, diff fingerprints, focused/integrated/review
results, G0-G6 status, bounded failure decisions, residual risks, and the next
authorized gate. Redact credentials, environment values, and raw provider/auth
payloads.
