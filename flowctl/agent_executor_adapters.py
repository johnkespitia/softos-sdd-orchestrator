from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from flowctl.agent_executors import AgentExecutor

EXECUTION_CONTRACT_BEGIN = "---SOFTOS_EXECUTION_CONTRACT---"
EXECUTION_CONTRACT_END = "---SOFTOS_EXECUTION_CONTRACT_END---"

V1_ADAPTERS = frozenset({"codex", "cursor", "opencode"})


class AdapterExecutionNotImplementedError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class AgentRunRequest:
    executor: AgentExecutor
    repo: str
    workspace_root: str
    workdir: str
    targets: tuple[str, ...]
    user_prompt: str
    contract_body: str


@dataclass(frozen=True)
class AgentAdapterInvocation:
    argv: tuple[str, ...]
    stdin: str | None = None


class AgentExecutorAdapter(Protocol):
    adapter_name: str

    def build_invocation(self, request: AgentRunRequest) -> AgentAdapterInvocation:
        ...


@dataclass(frozen=True)
class GenericStdinAdapter:
    """Test-oriented stdin transport; real vendor adapters land in slice 3."""

    adapter_name: str

    def build_invocation(self, request: AgentRunRequest) -> AgentAdapterInvocation:
        delivered_prompt = f"{request.contract_body}\n\n{request.user_prompt}"
        argv = (request.executor.executable, *request.executor.argv)
        return AgentAdapterInvocation(argv=argv, stdin=delivered_prompt)


def build_execution_contract(*, request: AgentRunRequest) -> str:
    sorted_targets = "\n".join(f"  - {target}" for target in sorted(request.targets))
    repo_runtime = (
        f"python3 ./flow repo exec {request.repo} --workdir {request.workdir} -- <command>"
    )
    control_plane = "scripts/workspace_exec.sh python3 ./flow <command>"
    docker_lifecycle = "python3 ./flow stack <command>"
    body = "\n".join(
        [
            EXECUTION_CONTRACT_BEGIN,
            f"executor: {request.executor.executor_id}",
            f"repository: {request.repo}",
            f"workspace_root: {request.workspace_root}",
            f"workdir: {request.workdir}",
            "allowed_targets:",
            sorted_targets or "  -",
            "boundaries:",
            "  - reads and writes limited to the assigned repo/worktree",
            "  - writes limited to allowed_targets",
            "canonical_commands:",
            f"  - repo_runtime: {repo_runtime}",
            f"  - control_plane: {control_plane}",
            f"  - docker_lifecycle: {docker_lifecycle}",
            "notices:",
            "  - normal control-plane commands remain workspace-only; flow agent is host-native",
            "  - BMAD and workflow orchestration are outside this run's authority",
            EXECUTION_CONTRACT_END,
        ]
    )
    return body


def resolve_adapter(adapter_name: str) -> AgentExecutorAdapter:
    if adapter_name in V1_ADAPTERS:
        raise AdapterExecutionNotImplementedError(
            f"La ejecucion del adapter `{adapter_name}` aun no esta implementada."
        )
    if adapter_name == "test":
        return GenericStdinAdapter(adapter_name=adapter_name)
    raise ValueError(f"Adapter no soportado: `{adapter_name}`.")
