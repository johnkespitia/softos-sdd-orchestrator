---
name: softos-coding-execution-supervisor
description: Supervises bounded SoftOS coding execution from an approved spec through slices, Patch Units, verification, independent review, and evidence. Use when any host agent (Cursor, Codex, OpenCode, Claude Code) is acting as SoftOS orchestrator or coding supervisor without a durable scheduler.
---

# SoftOS Coding Execution Supervisor

The harness that starts a feature run is the `orchestrator`. It owns routing,
decomposition, delegation, gate evaluation, and evidence. Every child run is
explicitly `worker` or `reviewer`; a child never inherits orchestration
authority from the parent conversation.

This skill is **vendor-agnostic**. It applies whenever the current session is the
SoftOS `orchestrator`, including:

- Cursor (IDE Agent / CLI) loading `AGENTS.md` + this skill
- Codex using `AGENTS.md` as primary contract
- OpenCode started via `flow agent run` (`OPENCODE.md`)
- Claude Code using `CLAUDE.md` → `AGENTS.md`

BMAD remains responsible for intake, spec authoring, planning, workflow choice,
and product lifecycle state. SoftOS runtime roles are a subordinate execution
layer:

```text
BMAD workflow -> approved spec and plan -> SoftOS orchestrator -> worker/reviewer runs
```

## SoftOS executor routing (mandatory for orchestrators)

Canonical assignment matrix and success semantics live in:

- `specs/features/coding-execution-runtime-v1.spec.md` (Priority tables + INVALID_IMPLEMENTATION)
- `workspace.config.json` → `agents.executors` + `agent_resources`
- `docs/agent-executors.md` / `docs/es/agent-executors.es.md`
- `docs/opencode-execution-resources.md` / `docs/es/opencode-execution-resources.es.md`

### Hard rules

1. **Delegate implementation/review only through SoftOS host executors**:
   `python3 ./flow agent run <executor|resource> ...` on the **WSL host**
   (not inside `flow workspace exec`; `flow agent doctor` must show `ready`).
2. **Do not** use IDE-native Task/subagent panels, ad hoc vendor “spawn agent”,
   or in-chat pretend-workers as SoftOS workers/reviewers.
3. Before routing, run `python3 ./flow agent doctor` and
   `python3 ./flow agent select --role orchestrator --json` when selecting who
   may own the orchestrator seat.
4. Worker/reviewer runs require `--role worker|reviewer`, `--run-id`,
   `--parent-run-id`, `--handoff`, `--repo`, `--workdir`, and repeatable
   `--target` paths inside that workdir.
5. Classify work, then **filter by capability/availability**, then apply the
   Priority table (never priority-first).

### Priority table (compact copy; SoT = coding-execution-runtime-v1)

| Work class/role | Ordered candidates before filtering |
| --- | --- |
| Supervisor/orchestration | Codex, Cursor, `opencode-go` |
| High complexity / architecture / planning | Codex, Cursor, `opencode-go` |
| Medium-high | Cursor, `opencode-go`, `opencode-free`, `opencode-local` only after suitable Patch Unit decomposition |
| Medium-low | `opencode-local`, `opencode-free`, `opencode-go` |
| Micro / Patch Unit | `opencode-local`, `opencode-free`, `opencode-go` |
| Independent review | Codex, Cursor, `opencode-go` |

Logical OpenCode resources use `agent_resources.selection_priority`
(local `10` → free `20` → go `30`) after capability filtering.
`opencode-local` has logical capacity **1**: one fresh bounded session per
suitable Patch Unit; never assign a whole Product Slice monolithically to local.

### Accept implementation only when

- executor exit code is `0`, **and**
- there is an authorized non-empty diff, **or**
- the unit explicitly allows a verified no-op and evidence states `NOOP`/`APPLIED`

Otherwise treat as `INVALID_IMPLEMENTATION`. Transport/`result=success` with empty
stdout and zero authorized diff is **not** success (especially under ACP
`permission_policy: reject`). Prefer fallback / re-decomposition / Cursor-class
executor over pretending local applied.

### Prefer for `opencode-local`

Micro Patch Units: one primary objective, one or two write targets, closed
contract, concrete verify command, no cross-worktree discovery in the prompt.
Keep handoffs problem/constraints/`done_when` — do not dictate the exact edit
token.

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
6. Filter resources by tools, write access, context, architecture responsibility, data sensitivity, availability/auth, and capacity. Apply priority only after filtering (Priority table above).
7. Launch the selected SoftOS executor via `flow agent run` (mandatory routing rules above). Give each child a fresh, compact handoff containing canonical references, not copied mutable context.
8. Accept implementation only with zero exit plus an authorized non-empty diff, unless an explicit verified no-op is allowed.
9. Run focused verification per unit, then integrated verification after DAG prerequisites pass.
10. Obtain read-only independent review from an eligible SoftOS identity distinct from the supervisor, implementer, and artifact producer (`flow agent run --role reviewer ...`).
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
