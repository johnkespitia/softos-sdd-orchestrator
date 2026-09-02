# OpenCode Execution Resources

This document describes the SoftOS logical OpenCode execution resources introduced by Coding Execution Runtime V1 slice `opencode-resource-pools`.

## Architecture

SoftOS keeps three responsibility layers separate:

```text
SoftOS Core / policy
  -> logical resource IDs, capabilities, availability, tier, capacity
Executor harness
  -> adapter + executable invocation only (model/provider agnostic)
OpenCode repository + machine-local state
  -> worker profile, provider auth, model catalog materialization
```

Logical resources are declared in `workspace.config.json` under `agent_resources`. They reference existing executor harness IDs from `agents.executors` and never add generic model/provider CLI flags to SoftOS.

| Logical resource | Role | Executor harness | Tier |
| --- | --- | --- | --- |
| `opencode-local` | Bounded local Patch Unit worker | `opencode-local` (`opencode-softos`) | local |
| `opencode-free` | Dynamic OpenCode free-model pool | `opencode-cloud` (`opencode`) | cloud/free |
| `opencode-go` | Dynamic OpenCode Go pool after auth | `opencode-cloud` (`opencode`) | cloud/paid-low |

`flow agent run <selector>` resolves a logical resource ID first when it matches `agent_resources.resources`. Otherwise the selector is treated as a legacy executor ID. Free and Go share the direct cloud harness while local keeps the repository-owned `opencode-softos` wrapper.

## Execution harness boundary

```text
requested selector
  -> resolve logical resource when selector is a resource ID
  -> resolve underlying executor
  -> resolve resource model / availability
  -> build process-local OpenCode config overlay (Free/Go only)
  -> spawn executor with merged inherited environment
```

Free and Go apply the dynamically resolved model through process-local `OPENCODE_CONFIG_CONTENT` merged at `execute_subprocess()`. The overlay selects a dedicated cloud worker (`softos-cloud-worker`) as `default_agent` and binds the resolved model to that worker so repository-owned `softos-local-worker` / Bonsai settings in `opencode.json` cannot win precedence. Local execution does not require a cloud overlay because `opencode-softos` forces `softos-local-worker` and repository-owned Bonsai selection.

## Canonical vs machine-local state

| Surface | Canonical in Git | Machine-local only |
| --- | --- | --- |
| `opencode.json` | `softos-local-worker`, local model `lmstudio/prism-ml/bonsai-27b`, reasoning, bounded steps | LM Studio endpoint reachability |
| `workspace.config.json` | logical resource metadata, capacity, capabilities, resolution mode, executor references | none |
| `~/.config/opencode/**` | never canonical | provider auth, merged agents, temporary catalogs |
| environment / wrappers | never canonical | `LM_STUDIO_BASE_URL`, `opencode-softos`, auth stores |
| `OPENCODE_CONFIG_CONTENT` | never persisted | process-local overlay for Free/Go model selection |

Repository-owned `opencode.json` is the portable source of truth for the local worker and its model selection. Machine-local OpenCode configuration may still exist for interactive use, but it must not override the repository contract for SoftOS resource resolution.

## `opencode-local` and Bonsai

`opencode-local` resolves the repository-owned worker `softos-local-worker` from `opencode.json`.

Current canonical local model:

```text
lmstudio/prism-ml/bonsai-27b
```

Requirements encoded in repository config:

- `default_agent: softos-local-worker`
- agent profile selects the Bonsai model explicitly
- `reasoning: true`
- conservative logical capacity `1`
- short bounded session settings (`steps: 6`)

SoftOS Core does not branch on Bonsai-specific names. The harness remains model/provider agnostic; only the OpenCode repository config and the resource resolver expose the local model contract.

## `opencode-free` dynamic resolution

`opencode-free` never hardcodes a permanent free model.

Resolution rules:

1. inspect the injectable OpenCode model catalog boundary (`OpencodeCliModelCatalogDiscovery` in production, fixtures in tests)
2. keep only `opencode` provider-namespace candidates matching `*-free`
3. apply deterministic lexicographic tie-breaking
4. return `MODEL_UNAVAILABLE` when no candidate matches
5. when selectable, serialize the resolved model into `OPENCODE_CONFIG_CONTENT` for the child process with:
   - top-level `model` set to the resolved candidate
   - `default_agent: softos-cloud-worker`
   - `agent.softos-cloud-worker.model` set to the same resolved candidate

Production discovery runs `opencode models` and parses one model ID per stdout line (for example `opencode/nemotron-3.5-lightning-free`). Provider readiness is probed with `opencode models <provider_namespace>`; exit `0` means the provider is available for catalog inspection, while messages such as `Provider not found: opencode-go` normalize to `AUTH_UNCONFIGURED`. Unit tests use fixtures/mocks and require no network access or provider credentials.

Resource metadata includes `data_sensitivity: cloud-eligible` as a future filtering point. This does not claim provider privacy guarantees.

## `opencode-go` lifecycle

`opencode-go` is representable now even when the current workstation does not expose a Go pool.

Default normalized availability:

```text
AUTH_UNCONFIGURED
```

Rules:

- no `OPENCODE_GO_TOKEN` or other invented credential contract is part of SoftOS
- no token/secret values belong in Git, diagnostics, overlays, or policy evidence
- OpenCode-managed authentication stays machine-local
- after supported auth/catalog evidence exists, Go model selection is dynamic and is not permanently hardcoded
- the resolved model reaches the child process through the same `OPENCODE_CONFIG_CONTENT` overlay path as Free

Go candidates are discovered from the `opencode-go` provider namespace in the injected catalog after supported auth or provider-probe evidence exists (`opencode models opencode-go` exit `0` normalizes to `AVAILABLE`). Unauthenticated resources refuse execution before subprocess launch.

## Authentication and secrets boundary

SoftOS must not:

- commit credentials, tokens, auth responses, or raw provider payloads
- serialize secrets into `workspace.config.json`, `agent_resources`, overlays, or `.flow/**` evidence
- claim that `OPENCODE_GO_TOKEN` is a native SoftOS/OpenCode contract

Diagnostics redact to normalized availability states and safe reason codes only.

## Normalized availability states

V1 vocabulary:

- `AVAILABLE`
- `BUSY`
- `CAPACITY_EXHAUSTED`
- `QUOTA_EXHAUSTED`
- `AUTH_UNCONFIGURED`
- `AUTH_FAILED`
- `MODEL_UNAVAILABLE`
- `PROVIDER_DOWN`
- `COOLDOWN`
- `UNKNOWN`

Unknown or unrecognized runtime evidence maps to `UNKNOWN` and is not selectable as if available.

`opencode-local` may report runtime probe failures through these states during doctor/selection flows. `opencode-go` begins at `AUTH_UNCONFIGURED` until supported OpenCode evidence proves auth and catalog availability.

## Troubleshooting / doctor expectations

`flow agent doctor` continues to validate executor executable presence only. It does not prove model availability, cloud auth, or resource-pool readiness.

For resource-aware diagnostics, use the resource layer in `flowctl/agent_resources.py`:

- load `workspace.config.json` `agent_resources`
- resolve the selected logical resource
- emit normalized `availability`, `reason`, and `selectable`
- never print secrets or raw provider payloads

Typical outcomes:

| Symptom | Expected normalized state |
| --- | --- |
| no free `*-free` model in catalog | `MODEL_UNAVAILABLE` |
| Go auth not configured locally | `AUTH_UNCONFIGURED` |
| local worker/model missing from `opencode.json` | resolver error / non-selectable resource |
| logical capacity already consumed | `CAPACITY_EXHAUSTED` |
| unrecognized probe output | `UNKNOWN` |

## Safe machine setup still required

This slice does not install OpenCode, LM Studio, or cloud auth. A workstation still needs:

1. LM Studio or equivalent endpoint for local Bonsai execution
2. `LM_STUDIO_BASE_URL` available to OpenCode at runtime
3. OpenCode CLI/wrapper (`opencode-softos` for local, `opencode` for cloud pools) on `PATH` for harness doctor checks
4. machine-local OpenCode auth before `opencode-go` can become selectable

None of those values belong in Git.

## Implementation references

- resource registry: `workspace.config.json` → `agent_resources`
- resolver/diagnostics/overlay: `flowctl/agent_resources.py`
- harness selection and subprocess overlay merge: `flowctl/agent_process_execution.py`
- focused tests: `flowctl/tests/test_agent_resources.py`, `flowctl/tests/test_agent_process_execution.py`
- local OpenCode profile: `opencode.json`
