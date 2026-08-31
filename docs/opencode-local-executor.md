# OpenCode Local Executor for SoftOS

> Español: [OpenCode Local Executor](es/opencode-local-executor.es.md)

## 1. Purpose

This document records the current local OpenCode setup used to prepare `opencode-local` as a SoftOS implementation executor. It explains the responsibility boundaries, the Windows/WSL connectivity arrangement, the dedicated OpenCode worker, the evidence collected during diagnosis, the current SoftOS integration, and the work that remains.

The goal is a bounded local coding path for assignments that normally take minutes, not a one-second chat path. The changes reduced unnecessary OpenCode context and generic-agent behavior while preserving a strict architectural rule: SoftOS selects an executor/harness, but does not select or encode an OpenCode provider or model.

This is configuration and operational documentation. The OpenCode and shell files described below live outside the repository and must be managed separately on each workstation.

## 2. Architecture and responsibility boundaries

```text
SoftOS
  ↓
opencode-local
  ↓
OpenCode
  ↓
softos-local-worker
  ↓
LM Studio
  ↓
local model
```

The layers have deliberately separate responsibilities:

| Layer | Responsibility |
| --- | --- |
| SoftOS | Select the executor, define the repository/worktree/targets, deliver the assignment contract and boundaries, and verify results deterministically. |
| OpenCode | Operate the harness and manage its agents/profiles, including the bounded worker used for SoftOS assignments. |
| OpenCode/LM Studio configuration | Select the provider, model, endpoint, and model/runtime parameters. |
| LM Studio | Serve the local model through its OpenAI-compatible API. |

SoftOS must remain provider- and model-agnostic. The currently selected Granite model is an OpenCode/LM Studio concern and is not part of the SoftOS executor registry contract.

## 3. Environment

The validated topology is:

- LM Studio runs on Windows and exposes an OpenAI-compatible API at `http://127.0.0.1:1234/v1`.
- SoftOS and OpenCode run in WSL.
- WSL uses mirrored networking so that the Windows service is reachable from WSL through the stable loopback address.
- OpenCode reads its global configuration and agent definitions from `~/.config/opencode/`.
- The persistent WSL shell environment supplies `LM_STUDIO_BASE_URL` through `~/.bashrc`.

No dynamic `172.x.x.x` host address is part of the configuration. Such addresses are environment-dependent and should not be used as a durable endpoint.

## 4. WSL → LM Studio connectivity

The initial endpoint used from WSL was `http://host.docker.internal:1234/v1`. That path produced connectivity failures and contributed to an earlier `opencode-local` run stopping without output.

WSL was subsequently configured on Windows through `%USERPROFILE%\.wslconfig`:

```ini
[wsl2]
networkingMode=mirrored
```

After WSL was restarted, `127.0.0.1:1234` became directly reachable from WSL. The persistent shell variable in `~/.bashrc` is now:

```bash
export LM_STUDIO_BASE_URL="http://127.0.0.1:1234/v1"
```

Current inspection confirmed both that value in `~/.bashrc` and a successful response from `GET http://127.0.0.1:1234/v1/models`. The response advertised `granite-4.1-8b` and an embedding model.

To reconstruct this setup on another workstation, configure mirrored networking in the Windows-side `.wslconfig`, restart WSL, expose LM Studio on port `1234`, and set the WSL environment variable. Do not copy a transient WSL or Windows bridge IP.

## 5. OpenCode global configuration

The global configuration is `~/.config/opencode/opencode.json`. Current inspection established these non-secret settings:

- provider ID: `lmstudio`;
- provider implementation: `@ai-sdk/openai-compatible`;
- provider base URL: `{env:LM_STUDIO_BASE_URL}`;
- configured model ID: `lmstudio/granite-4.1-8b`;
- the generic `build` agent currently has `steps: 8` and `temperature: 0.1`.

The endpoint is resolved from the environment rather than duplicated in the repository. The provider and model are intentionally owned by OpenCode/LM Studio. Neither appears in the SoftOS executor schema.

The initial Granite context window was 8,192 tokens. OpenCode failed with:

```text
request (...) exceeds available context size (8192 tokens)
```

The Granite runtime context was then increased in LM Studio to approximately 16K, after which a local OpenCode call completed. This context setting belongs to LM Studio and is not represented in the repository.

Do not publish the complete workstation configuration when it contains credentials or unrelated providers. The values above are the minimum relevant, non-secret reconstruction facts.

## 6. Dedicated `softos-local-worker`

The generic OpenCode `build` agent was not suitable as the canonical SoftOS worker. A minimal no-tools response took approximately 22.04 seconds in one repository run, an earlier run invoked WebFetch unnecessarily, and a run from `/tmp/opencode-bench` took approximately 98.40 seconds. It also carried substantially more prompt context, reaching roughly 10.5K request tokens in the earlier measurement.

A dedicated primary agent named `softos-local-worker` therefore exists at:

```text
~/.config/opencode/agents/softos-local-worker.md
```

It was initially project-local at `.opencode/agents/softos-local-worker.md`. SoftOS Git worktrees did not discover that definition reliably, so the definition was moved to OpenCode's global agent directory. Current `opencode agent list` output identifies `softos-local-worker (primary)` from both the main workspace and an existing `.worktrees/**` checkout.

The worker instructions require it to:

- follow only the supervisor's explicit assignment;
- modify only explicitly authorized files and avoid scope expansion;
- avoid web browsing and subagent delegation;
- avoid plans, commits, pushes, pull requests, merges, and releases;
- prefer the smallest sufficient change and focused local checks;
- stop and report blockers caused by missing context, environment, permissions, platform issues, or out-of-scope requirements;
- return a concise change and verification summary.

The current agent front matter declares `steps: 6`. It explicitly allows `read`, `edit`, `glob`, `grep`, `list`, and `bash`, and explicitly denies `task`, `webfetch`, `websearch`, `todowrite`, `skill`, and `question`.

There is an important runtime nuance: `opencode agent list` reports merged permission entries, including OpenCode/project-level inherited rules such as an initial wildcard allow, followed by the worker's explicit allow/deny rules. The worker file's intent and explicit rules are verified, but this document does not infer undocumented precedence semantics from that merged list. When permission enforcement is security-critical, validate the behavior against the installed OpenCode version rather than relying only on the front matter.

## 7. Validation and benchmarks

The following measurements were collected during setup and diagnosis:

| Test | Result |
| --- | --- |
| Raw LM Studio `POST /v1/chat/completions` | `RAW_LM_OK`, ~1.02 s |
| OpenCode generic `build` run | `OPENCODE_LOCAL_OK`, ~22.04 s |
| OpenCode `build` from `/tmp/opencode-bench` | ~98.40 s |
| Local worker first run | ~39.84 s |
| Local worker warm run | ~12.55 s |
| Local worker instrumented run | ~10.26 s |
| Instrumented total tokens | 5,143 |
| Instrumented input tokens | 5,138 |
| Instrumented output tokens | 5 |
| Instrumented reasoning tokens | 0 |
| Instrumented cache write/read | 0 / 0 |

The instrumented worker result is materially smaller than the roughly 10.5K-token request observed with the earlier generic-agent path. These values are diagnostic evidence from particular runs, not an SLA or a guarantee for future tasks. Startup cost, repository context, prompt size, tool use, machine state, and OpenCode version can change the result.

The ~1.02-second raw completion demonstrates that LM Studio and Granite were not the main source of the much larger end-to-end delay in that comparison. The remaining time was predominantly in the OpenCode path, including startup and context/harness processing.

## 8. SoftOS executor integration

The current `workspace.config.json` registry contains exactly three executors:

| Executor | Adapter | Executable | Static `argv` |
| --- | --- | --- | --- |
| `codex` | `codex` | `codex` | `[]` |
| `cursor` | `cursor` | `agent` | `[]` |
| `opencode-local` | `opencode` | `opencode` | `[]` |

The registry schema in `flowctl/agent_executors.py` accepts only `adapter`, `executable`, and `argv` for an executor. It has no model, provider, or OpenCode profile field.

The current `OpenCodeAdapter` in `flowctl/agent_executor_adapters.py` constructs the equivalent of:

```text
opencode run --auto --dir <workdir> -- <delivered-prompt>
```

The executor registry itself does not encode an OpenCode agent/profile. However, selection of `softos-local-worker` has been **validated through per-process configuration** by passing `OPENCODE_CONFIG_CONTENT='{"default_agent":"softos-local-worker"}'` to the environment inherited by `flow agent run`. This keeps SoftOS provider/model agnostic while allowing OpenCode to own worker selection.

Adding `--agent` through `executor.argv` is not a current solution. Static OpenCode options are deliberately restricted, and `_build_positional_prompt_argv` places validated static arguments before the adapter-owned tail. The adapter has not been modified to select the worker.

This preserves the correct abstraction boundary but leaves the final harness-profile selection unresolved.

## 9. Operational validation

Run these checks from WSL. They are diagnostic commands; the OpenCode run invokes the local model but should not edit files because the prompt explicitly forbids tool use.

Check the LM Studio endpoint without using a dynamic IP:

```bash
curl http://127.0.0.1:1234/v1/models
```

Confirm that OpenCode discovers the global worker, both in the main checkout and from a SoftOS Git worktree:

```bash
opencode agent list
```

Exercise the dedicated worker directly:

```bash
opencode run --agent softos-local-worker \
  "Do not use any tools. Reply only with: OPENCODE_LOCAL_OK"
```

Confirm the SoftOS registry remains executor-only:

```bash
python3 ./flow agent list --json
```

Expected evidence is: the LM Studio model list includes Granite; the agent list includes `softos-local-worker (primary)`; the direct run returns only `OPENCODE_LOCAL_OK`; and the SoftOS list shows `codex`, `cursor`, and `opencode-local` without provider or model data.

## 10. Troubleshooting

### Connection refused or timeout to LM Studio

Confirm that LM Studio is running on Windows, its local server is started on port `1234`, and `curl http://127.0.0.1:1234/v1/models` works from WSL. Inspect `LM_STUDIO_BASE_URL` in the active shell and the persistent export in `~/.bashrc`. A changed shell file does not affect an already-running shell until it is reloaded or restarted.

### `host.docker.internal` versus localhost

The previously used `host.docker.internal` endpoint was unreliable in this WSL path. With WSL mirrored networking configured and WSL restarted, use `http://127.0.0.1:1234/v1`. Do not replace it with a discovered `172.x.x.x` address; that would reintroduce a transient dependency.

### 8,192-token context overflow

If OpenCode reports that the request exceeds 8,192 tokens, inspect the loaded Granite runtime in LM Studio and ensure its context is approximately 16K or otherwise large enough for the actual request. Changing the SoftOS registry is not the remedy: context size is an LM Studio/model runtime concern. Also keep the worker assignment narrow to avoid unnecessary input.

### Worker is not visible from a worktree

Run `opencode agent list` from the worktree. The canonical workstation definition should exist at `~/.config/opencode/agents/softos-local-worker.md`, not only at the main checkout's `.opencode/agents/`. A project-local agent file is not sufficient for sibling Git worktrees.

### OpenCode uses `build` instead of `softos-local-worker`

For a direct diagnostic call, pass `--agent softos-local-worker` or use the validated `opencode-softos` wrapper. The actual SoftOS path has also been validated with inherited `OPENCODE_CONFIG_CONTENT`: `flow agent run → opencode-local → OpenCodeAdapter → softos-local-worker → LM Studio → local model`.

### OpenCode executions are slow

Compare like-for-like warm and cold runs, record elapsed time and token counts, and check whether tools were invoked. The first worker run was slower than later runs. OpenCode startup, configuration loading, repository instructions, prompt construction, and harness behavior can dominate a tiny completion.

### Distinguishing LM Studio performance from OpenCode overhead

First send a minimal direct `POST /v1/chat/completions` request to LM Studio, then run an equivalent no-tools prompt through OpenCode. A fast raw completion with a slow OpenCode completion points to harness/startup/context overhead rather than model inference alone. The recorded comparison was ~1.02 seconds raw versus ~22.04 seconds through generic `build` and ~10.26 seconds for the instrumented dedicated worker.

## 11. Known limitations

- OpenCode still has measurable startup and context-loading overhead.
- The instrumented benchmark reported cache write `0` and cache read `0`; no cache benefit was demonstrated in that run.
- The executor registry does not permanently encode `softos-local-worker`; worker selection is currently validated through per-process configuration or the workstation-level `opencode-softos` wrapper.
- `flow agent run` does not currently provide a canonical timeout/cancel mechanism.
- Agent discovery proves availability, not that the current SoftOS adapter selected that agent.
- The global OpenCode agent and shell/provider configuration are workstation state outside the repository and must be reconstructed separately.
- These executor changes are not the future durable orchestrator state mechanism. Executor selection/profile wiring and durable orchestration state are separate concerns.

## 12. Pending integration

The remaining design decision is how to make the already validated worker-selection mechanism permanent and canonical for SoftOS-launched `opencode-local` processes without changing normal interactive OpenCode behavior.

One candidate is a per-process configuration override:

```bash
OPENCODE_CONFIG_CONTENT='{"default_agent":"softos-local-worker"}'
```

**This per-process override is validated.** It has been tested directly with OpenCode and through the actual `flow agent run` path. It is not yet encoded as permanent repository-level SoftOS configuration.

The final design may be:

- a per-process configuration override;
- a wrapper executable dedicated to `opencode-local`;
- an explicit adapter capability that remains profile-oriented and provider/model-agnostic;
- another equivalent mechanism that preserves the responsibility boundary.

The chosen mechanism must be tested through the actual `flow agent run` path, from a SoftOS worktree, and must demonstrate that only `opencode-local` selects the worker. It must not add provider or model fields to SoftOS.

The Orchestrator V0 replay was subsequently attempted with Codex as supervisor, `opencode-local` as implementer, an independent reviewer, and a repair budget of at most one. The run reached the implementer through the canonical `flow agent run` path but ended `BLOCKED` before deterministic verification. A later read-only tool-use diagnostic completed successfully, confirming that OpenCode could use `glob` and `read`, recover from an initially incorrect path, and find `command_repo_exec`. That diagnostic took roughly 75 seconds with about 8.7K input tokens, indicating that long silent periods can be caused by harness/model latency rather than a hard tool-calling deadlock.

## 13. Acceptance checklist

- [x] LM Studio accessible from WSL through localhost.
- [x] `LM_STUDIO_BASE_URL` persists in `~/.bashrc` as `http://127.0.0.1:1234/v1`.
- [x] Granite responds directly through the LM Studio OpenAI-compatible API.
- [x] Granite has sufficient context for the validated local OpenCode call (approximately 16K configured in LM Studio).
- [x] OpenCode recognizes `softos-local-worker`.
- [x] `softos-local-worker` is visible from a Git worktree.
- [x] A direct call with `--agent softos-local-worker` works.
- [x] The SoftOS registry remains model/provider agnostic.
- [x] A per-process SoftOS → `softos-local-worker` selection mechanism is validated through the actual `flow agent run` path.
- [x] The `opencode-softos` wrapper is validated as a workstation-level worker-selection mechanism.
- [ ] Permanent repository-level wiring for worker selection is defined.
- [ ] The Orchestrator V0 replay reaches deterministic verification and independent review without a platform blocker.

The checked items combine current file/command inspection with the recorded validation evidence above. The two unchecked items are intentionally pending and must not be inferred from direct OpenCode success.
