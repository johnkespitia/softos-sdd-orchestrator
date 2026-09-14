from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


GIT_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")


def resolve_submodule_gitlink(workspace_root: Path, repo_path: str) -> str:
    normalized_path = repo_path.strip()
    if not normalized_path:
        raise ValueError("Submodule repo path is empty.")

    commands = [
        ["git", "ls-tree", "HEAD", "--", normalized_path],
        ["git", "ls-files", "--stage", "--", normalized_path],
    ]
    last_error = "git ls-tree failed"
    for command in commands:
        result = subprocess.run(
            command,
            cwd=workspace_root,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            last_error = result.stderr.strip() or last_error
            continue
        fields = result.stdout.strip().split(maxsplit=3)
        if command[1] == "ls-tree":
            valid_gitlink = len(fields) >= 3 and fields[0] == "160000" and fields[1] == "commit"
            gitlink_sha = fields[2].lower() if valid_gitlink else ""
        else:
            valid_gitlink = len(fields) >= 2 and fields[0] == "160000"
            gitlink_sha = fields[1].lower() if valid_gitlink else ""
        if valid_gitlink:
            if not GIT_SHA_PATTERN.fullmatch(gitlink_sha):
                raise ValueError(f"Invalid submodule gitlink SHA for '{normalized_path}'.")
            return gitlink_sha

    if last_error != "git ls-tree failed":
        raise ValueError(f"Could not resolve gitlink for '{normalized_path}': {last_error}.")
    raise ValueError(
        f"No submodule gitlink found at '{normalized_path}' in HEAD or the index."
    )


def load_runtime_pack_map(workspace_root: Path) -> dict[str, dict[str, object]]:
    runtimes_registry: dict[str, object] = {}
    runtimes_index: dict[str, dict[str, object]] = {}
    runtimes_file = workspace_root / "workspace.runtimes.json"
    if runtimes_file.exists():
        try:
            runtimes_registry = json.loads(runtimes_file.read_text(encoding="utf-8")).get("runtimes", {})
        except Exception:
            runtimes_registry = {}

    def load_runtime_pack(runtime_name: str) -> dict[str, object]:
        if not runtime_name:
            return {}
        if runtime_name in runtimes_index:
            return runtimes_index[runtime_name]
        source = ""
        entry = runtimes_registry.get(runtime_name, {})
        if isinstance(entry, dict):
            source = str(entry.get("source", "")).strip()
        candidates = []
        if source:
            candidates.append(Path(source))
        candidates.append(workspace_root / "runtimes" / f"{runtime_name}.runtime.json")
        for candidate in candidates:
            if not candidate.is_file():
                continue
            try:
                payload = json.loads(candidate.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    runtimes_index[runtime_name] = payload
                    return payload
            except Exception:
                continue
        runtimes_index[runtime_name] = {}
        return {}

    repos = {}
    workspace_config = json.loads((workspace_root / "workspace.config.json").read_text(encoding="utf-8"))
    raw_repos = workspace_config.get("repos", {})
    if isinstance(raw_repos, dict):
        repos = raw_repos
    for repo_cfg in repos.values():
        if not isinstance(repo_cfg, dict):
            continue
        load_runtime_pack(str(repo_cfg.get("runtime", "")).strip())
    return runtimes_index


def infer_tools(runtime_name: str, repo_cfg: dict[str, object], runtime_pack: dict[str, object]) -> tuple[bool, bool, bool, bool]:
    runner = str(repo_cfg.get("test_runner", runtime_pack.get("test_runner", ""))).strip().lower()
    ci_cfg = repo_cfg.get("ci")
    if not isinstance(ci_cfg, dict):
        ci_cfg = runtime_pack.get("ci", {})
    tokens: list[str] = []
    if isinstance(ci_cfg, dict):
        for step in ("install", "lint", "test", "build"):
            cmd = ci_cfg.get(step)
            if isinstance(cmd, list):
                tokens.extend(str(part).strip().lower() for part in cmd if isinstance(part, str))
    runtime_lower = runtime_name.lower()
    token_set = set(tokens)
    needs_node = (
        runner == "pnpm"
        or any(item in token_set for item in {"pnpm", "npm", "npx", "node"})
        or "node" in runtime_lower
    )
    needs_php = (
        runner == "php"
        or any(item in token_set for item in {"php", "composer", "phpunit", "artisan"})
        or "php" in runtime_lower
    )
    needs_go = (
        runner == "go"
        or "go" in token_set
        or runtime_lower.startswith("go")
        or runtime_lower.endswith("-go")
    )
    needs_python = (
        runner == "pytest"
        or any(item in token_set for item in {"python", "python3", "pip", "pip3", "pytest", "uv"})
        or "python" in runtime_lower
    )
    return needs_node, needs_php, needs_go, needs_python


def build_repo_ci_matrices(
    workspace_config: dict[str, object],
    runtime_packs: dict[str, dict[str, object]],
    workspace_root: Path | None = None,
) -> dict[str, object]:
    generic: list[dict[str, object]] = []
    delegated: list[dict[str, object]] = []
    repos = workspace_config.get("repos", {})
    if not isinstance(repos, dict):
        return {
            "generic": {"include": []},
            "delegated": {"include": []},
            "has_generic": False,
            "has_delegated": False,
        }

    for repo_name in sorted(repos):
        repo_cfg = repos.get(repo_name, {})
        if not isinstance(repo_cfg, dict):
            continue
        if str(repo_cfg.get("kind", "")).strip().lower() == "root":
            continue

        runtime_name = str(repo_cfg.get("runtime", "")).strip()
        runtime_pack = runtime_packs.get(runtime_name, {})
        needs_node, needs_php, needs_go, needs_python = infer_tools(runtime_name, repo_cfg, runtime_pack)
        ci_cfg = repo_cfg.get("ci", {})
        if not isinstance(ci_cfg, dict):
            ci_cfg = {}
        ci_mode = str(ci_cfg.get("mode", "")).strip().lower() or "inline"
        repo_path = str(repo_cfg.get("path", repo_name)).strip() or repo_name
        entry = {
            "repo": repo_name,
            "path": repo_path,
            "runtime": runtime_name or "unknown",
            "needs_node": needs_node,
            "needs_php": needs_php,
            "needs_go": needs_go,
            "needs_python": needs_python,
        }
        if ci_mode == "workflow-dispatch":
            workflow_ref = str(ci_cfg.get("ref", "")).strip()
            source_sha = str(ci_cfg.get("source_sha", "")).strip().lower()
            if str(repo_cfg.get("repo_strategy", "")).strip().lower() == "submodule":
                if workspace_root is None:
                    raise ValueError(
                        f"Workspace root is required to resolve submodule gitlink for '{repo_name}'."
                    )
                source_sha = resolve_submodule_gitlink(workspace_root, repo_path)
            if not workflow_ref:
                raise ValueError(
                    f"Repo '{repo_name}' declares delegated CI but has no workflow ref."
                )
            if GIT_SHA_PATTERN.fullmatch(workflow_ref.lower()):
                raise ValueError(
                    f"Repo '{repo_name}' delegated CI workflow ref must be a branch or tag, not a SHA."
                )
            if not GIT_SHA_PATTERN.fullmatch(source_sha):
                raise ValueError(
                    f"Repo '{repo_name}' delegated CI has no valid source SHA."
                )
            delegated.append(
                {
                    **entry,
                    "workflow": str(ci_cfg.get("workflow", "")).strip(),
                    "workflow_repository": str(ci_cfg.get("workflow_repository", "")).strip(),
                    "trigger_mode": str(ci_cfg.get("trigger_mode", "")).strip() or "workflow_dispatch_only",
                    "inputs": ci_cfg.get("inputs", {}) if isinstance(ci_cfg.get("inputs", {}), dict) else {},
                    "workflow_ref": workflow_ref,
                    "source_sha": source_sha,
                }
            )
            continue
        generic.append(entry)

    return {
        "generic": {"include": generic},
        "delegated": {"include": delegated},
        "has_generic": bool(generic),
        "has_delegated": bool(delegated),
    }
