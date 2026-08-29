from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional, Sequence

from flowctl.agent_executor_adapters import (
    AdapterExecutionNotImplementedError,
    AgentAdapterInvocation,
    AgentRunRequest,
    build_execution_contract,
    resolve_adapter,
)
from flowctl.agent_executors import AgentExecutor, AgentRegistryError, load_agent_registry


class AgentRunError(Exception):
    def __init__(self, message: str, *, exit_code: int = 1) -> None:
        self.message = message
        self.exit_code = exit_code
        super().__init__(message)


@dataclass(frozen=True)
class AgentRunMetadata:
    executor_id: str
    repo: str
    workdir: str
    targets: tuple[str, ...]
    started_at: str
    finished_at: str
    exit_code: int


def path_is_contained(child: Path, parent: Path) -> bool:
    parent_canonical = parent.resolve()
    try:
        child.resolve().relative_to(parent_canonical)
        return True
    except (ValueError, OSError):
        return False


def list_registered_worktree_paths(
    repo_root: Path,
    *,
    run_git: Callable[..., object] = subprocess.run,
) -> frozenset[Path]:
    completed = run_git(
        ["git", "-C", str(repo_root), "worktree", "list", "--porcelain"],
        capture_output=True,
        check=False,
    )
    if int(getattr(completed, "returncode", 1)) != 0:
        raise AgentRunError(
            "No pude consultar los worktrees registrados de git para el repo seleccionado."
        )
    stdout = getattr(completed, "stdout", b"")
    if isinstance(stdout, bytes):
        text = stdout.decode("utf-8", errors="replace")
    else:
        text = str(stdout or "")
    paths: list[Path] = []
    for line in text.splitlines():
        if line.startswith("worktree "):
            paths.append(Path(line[len("worktree "):].strip()).resolve())
    return frozenset(paths)


def resolve_repo_id(raw_repo: str, *, repos: dict[str, object], root_repo: str) -> str:
    candidate = raw_repo.strip()
    if not candidate:
        raise AgentRunError("Debes indicar `--repo`.")
    if candidate in repos:
        return candidate
    if candidate == "workspace-root":
        return root_repo
    root_aliases = {"root", "root-repo", "root_repo", "workspace", "."}
    if candidate in root_aliases:
        return root_repo
    raise AgentRunError(f"Repo desconocido: `{candidate}`.")


def resolve_repo_root(repo: str, *, workspace_root: Path, repos: dict[str, object], root_repo: str) -> Path:
    config = repos.get(repo)
    if not isinstance(config, dict):
        raise AgentRunError(f"Repo desconocido: `{repo}`.")
    relative = str(config.get("path", ".")).strip()
    if repo == root_repo or relative in {"", "."}:
        return workspace_root
    return workspace_root / relative


def validate_workdir(
    raw_workdir: str,
    *,
    workspace_root: Path,
    repo_root_path: Path,
    run_git: Callable[..., object] = subprocess.run,
) -> Path:
    candidate = raw_workdir.strip()
    if not candidate:
        raise AgentRunError("Debes indicar `--workdir`.")
    workdir_path = Path(candidate)
    if not workdir_path.exists():
        raise AgentRunError(f"El workdir no existe: `{candidate}`.")
    if not workdir_path.is_dir():
        raise AgentRunError(f"El workdir debe ser un directorio: `{candidate}`.")

    canonical = workdir_path.resolve()
    workspace_canonical = workspace_root.resolve()
    if not path_is_contained(canonical, workspace_canonical):
        raise AgentRunError(f"El workdir queda fuera del workspace: `{candidate}`.")

    repo_canonical = repo_root_path.resolve()
    if canonical == repo_canonical:
        return canonical

    registered = list_registered_worktree_paths(repo_root_path, run_git=run_git)
    if canonical not in registered:
        raise AgentRunError(
            f"El workdir no es el root del repo ni un worktree reconocido: `{candidate}`."
        )
    return canonical


def resolve_target_within_workdir(workdir: Path, raw_target: str) -> str:
    target_text = raw_target.strip()
    if not target_text:
        raise AgentRunError("Cada `--target` debe ser un path no vacio.")

    target_path = Path(target_text)
    if target_path.is_absolute():
        raise AgentRunError(f"Target fuera de limites: `{target_text}`.")

    normalized = os.path.normpath(target_text)
    if normalized in {".", ""}:
        parts: list[str] = []
    else:
        parts = [part for part in Path(normalized).parts if part and part != "."]

    if ".." in parts:
        raise AgentRunError(f"Target fuera de limites: `{target_text}`.")

    root_real = workdir.resolve()
    current = workdir

    for part in parts:
        current = current / part
        try:
            resolved = current.resolve(strict=False)
        except (OSError, RuntimeError):
            raise AgentRunError(f"Target fuera de limites: `{target_text}`.")
        try:
            resolved.relative_to(root_real)
        except ValueError:
            raise AgentRunError(f"Target fuera de limites: `{target_text}`.")

    if parts:
        return Path(*parts).as_posix()
    return "."


def normalize_targets(workdir: Path, raw_targets: Sequence[str]) -> tuple[str, ...]:
    if not raw_targets:
        raise AgentRunError("Debes indicar al menos un `--target`.")
    normalized = sorted({resolve_target_within_workdir(workdir, item) for item in raw_targets})
    return tuple(normalized)


def validate_prompt(raw_prompt: str) -> str:
    if not raw_prompt.strip():
        raise AgentRunError("Debes indicar un `--prompt` no vacio.")
    return raw_prompt


def executable_is_ready(executable: str, *, shutil_which: Callable[[str], Optional[str]]) -> bool:
    candidate = Path(executable)
    if candidate.is_absolute():
        return candidate.is_file() and os.access(candidate, os.X_OK)
    return shutil_which(executable) is not None


def _child_stream_bytes(payload: object) -> bytes:
    if payload is None:
        return b""
    if isinstance(payload, bytes):
        return payload
    return str(payload).encode("utf-8")


def execute_subprocess(
    invocation: AgentAdapterInvocation,
    *,
    cwd: Path,
    subprocess_run: Callable[..., object] = subprocess.run,
) -> tuple[int, bytes, bytes]:
    kwargs: dict[str, object] = {
        "args": list(invocation.argv),
        "cwd": str(cwd),
        "shell": False,
        "capture_output": True,
    }
    if invocation.stdin is not None:
        kwargs["input"] = invocation.stdin.encode("utf-8")

    try:
        completed = subprocess_run(**kwargs)
    except OSError:
        raise AgentRunError("No pude lanzar el proceso del executor: fallo al crear el proceso hijo.")

    return (
        int(getattr(completed, "returncode", 1)),
        _child_stream_bytes(getattr(completed, "stdout", None)),
        _child_stream_bytes(getattr(completed, "stderr", None)),
    )


def run_agent_process(
    *,
    executor: AgentExecutor,
    repo: str,
    workspace_root: Path,
    workdir: Path,
    targets: tuple[str, ...],
    prompt: str,
    shutil_which: Callable[[str], Optional[str]],
    subprocess_run: Callable[..., object] = subprocess.run,
    stream_writer: Callable[[str, bytes], None] | None = None,
) -> tuple[int, AgentRunMetadata]:
    started_at = datetime.now(timezone.utc).isoformat()
    workdir_resolved = str(workdir.resolve())
    workspace_resolved = str(workspace_root.resolve())
    contract_body = build_execution_contract(
        request=AgentRunRequest(
            executor=executor,
            repo=repo,
            workspace_root=workspace_resolved,
            workdir=workdir_resolved,
            targets=targets,
            user_prompt=prompt,
            contract_body="",
        )
    )
    request = AgentRunRequest(
        executor=executor,
        repo=repo,
        workspace_root=workspace_resolved,
        workdir=workdir_resolved,
        targets=targets,
        user_prompt=prompt,
        contract_body=contract_body,
    )

    try:
        adapter = resolve_adapter(executor.adapter)
        invocation = adapter.build_invocation(request)
    except AdapterExecutionNotImplementedError as exc:
        raise AgentRunError(exc.message) from exc

    if not executable_is_ready(executor.executable, shutil_which=shutil_which):
        raise AgentRunError(
            f"No pude lanzar el executor `{executor.executor_id}`: "
            f"el ejecutable no esta disponible."
        )

    exit_code, stdout, stderr = execute_subprocess(
        invocation,
        cwd=workdir,
        subprocess_run=subprocess_run,
    )
    writer = stream_writer or _default_stream_writer
    if stdout:
        writer("stdout", stdout)
    if stderr:
        writer("stderr", stderr)

    finished_at = datetime.now(timezone.utc).isoformat()
    metadata = AgentRunMetadata(
        executor_id=executor.executor_id,
        repo=repo,
        workdir=str(workdir.resolve()),
        targets=targets,
        started_at=started_at,
        finished_at=finished_at,
        exit_code=exit_code,
    )
    return exit_code, metadata


def _default_stream_writer(stream: str, payload: bytes) -> None:
    if stream == "stdout":
        target = getattr(sys.stdout, "buffer", None)
        if target is not None:
            target.write(payload)
            return
        sys.stdout.write(payload.decode("utf-8", errors="surrogateescape"))
        return
    target = getattr(sys.stderr, "buffer", None)
    if target is not None:
        target.write(payload)
        return
    sys.stderr.write(payload.decode("utf-8", errors="surrogateescape"))


def prepare_agent_run(
    *,
    executor_id: str,
    repo_raw: str,
    workdir_raw: str,
    prompt_raw: str,
    target_raws: Sequence[str],
    workspace_root: Path,
    workspace_config_file: Path,
    workspace_config: dict[str, object],
    root_repo: str,
    run_git: Callable[..., object] = subprocess.run,
) -> tuple[AgentExecutor, str, Path, tuple[str, ...], str]:
    try:
        executors = load_agent_registry(workspace_config_file)
    except AgentRegistryError as exc:
        raise AgentRunError(exc.message) from exc

    selected_id = executor_id.strip()
    if not selected_id:
        raise AgentRunError("Debes indicar un executor.")
    executor = executors.get(selected_id)
    if executor is None:
        raise AgentRunError(f"Executor desconocido: `{selected_id}`.")

    repos = workspace_config.get("repos")
    if not isinstance(repos, dict):
        raise AgentRunError("workspace.config.json debe definir `repos`.")

    repo = resolve_repo_id(repo_raw, repos=repos, root_repo=root_repo)
    repo_root_path = resolve_repo_root(
        repo,
        workspace_root=workspace_root,
        repos=repos,
        root_repo=root_repo,
    )
    workdir = validate_workdir(
        workdir_raw,
        workspace_root=workspace_root,
        repo_root_path=repo_root_path,
        run_git=run_git,
    )
    prompt = validate_prompt(prompt_raw)
    targets = normalize_targets(workdir, target_raws)
    return executor, repo, workdir, targets, prompt
