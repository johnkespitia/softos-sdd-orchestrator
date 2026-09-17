---
name: softos-code-graph-playbook
description: Eager/auto-apply skill for code graph navigation via Graphify MCP. Use proactively before broad file searches when a code graph exists — navigate codebases, locate symbols/classes/routes, impact analysis, refactoring, debugging cross-file dependencies, SoftOS orchestration, implementation slices, and any time flow code-graph or Graphify MCP could help.
---

## Outcomes

- Agents query structural code context via Graphify before blind grepping; graphs stay consultive; specs/Git remain source of truth.

## Default workflow at task start

For any implementation/orchestration/navigation work:

1. `python3 ./flow code-graph doctor --json` — non-blocking if missing
2. `python3 ./flow code-graph status --json` (or `--repo <repo>`)
3. If status is missing/stale for the active repo: `python3 ./flow code-graph refresh <repo> --json`
4. Prefer running via `python3 ./flow workspace exec -- ...` when on host with FLOW_FORCE_WORKSPACE_EXEC

## Query path

1. Prefer Graphify MCP tools when available (Cursor/OpenCode/Codex).
2. Root MCP default graph: `/workspace/graphify-out/graph.json`
3. Per-repo graphs: `/workspace/<repo-path>/graphify-out/graph.json`  
   - hub-frontend
   - dashboard-frontend
   - plg-platform-backend
4. If MCP exposes `project_path` / alternate servers, use the repo-specific graph for that task.

## When to refresh

After large code moves, new submodule registration, or status stale/missing.

## Boundaries

- Never treat `graphify-out` as source of truth; never commit `graphify-out`.
- Engram is complementary memory (`softos-agent-memory-playbook`); Graphify reflects current-code structure only.

## Minimal commands cheat-sheet

| Action | Command |
|--------|---------|
| Diagnose graph health | `python3 ./flow code-graph doctor --json` |
| Check status | `python3 ./flow code-graph status --json [--repo <repo>]` |
| Refresh graph | `python3 ./flow code-graph refresh <repo> --json` |
| Host execution | `python3 ./flow workspace exec -- <command>` |
| Root graph path | `/workspace/graphify-out/graph.json` |
| Per-repo paths | `/workspace/<repo-path>/graphify-out/graph.json` |
