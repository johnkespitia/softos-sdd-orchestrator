from __future__ import annotations

from dataclasses import dataclass
import os
import uuid
from typing import Callable, Mapping, Optional

from .agent_executors import AgentExecutor

ROLE_ORCHESTRATOR = "orchestrator"
ROLE_WORKER = "worker"
ROLE_REVIEWER = "reviewer"
SUPPORTED_AGENT_ROLES = frozenset({ROLE_ORCHESTRATOR, ROLE_WORKER, ROLE_REVIEWER})
ROLE_ENV_ROLE = "SOFTOS_AGENT_ROLE"
ROLE_ENV_RUN_ID = "SOFTOS_AGENT_RUN_ID"
ROLE_ENV_PARENT_RUN_ID = "SOFTOS_AGENT_PARENT_RUN_ID"
ROLE_ENV_HANDOFF = "SOFTOS_AGENT_HANDOFF"

# Orchestration selection is capability-oriented and model-agnostic. A resource
# can still fail at launch when its provider/model evidence is unavailable.
ORCHESTRATOR_EXECUTOR_PRIORITY = ("codex", "cursor", "opencode-go", "opencode")


class AgentRoleError(ValueError):
    pass


@dataclass(frozen=True)
class AgentRoleContext:
    role: str = ROLE_ORCHESTRATOR
    run_id: str = "standalone-orchestrator"
    parent_run_id: Optional[str] = None
    handoff_ref: Optional[str] = None


def resolve_invocation_role(
    *,
    role: object = None,
    run_id: object = None,
    parent_run_id: object = None,
    handoff_ref: object = None,
    environ: Optional[Mapping[str, str]] = None,
) -> AgentRoleContext:
    """Resolve a CLI invocation without allowing nested role escalation."""
    env = os.environ if environ is None else environ
    inherited_run_id = str(env.get(ROLE_ENV_RUN_ID, "") or "").strip() or None
    explicit_role = str(role or "").strip().lower() or None

    if inherited_run_id and explicit_role == ROLE_ORCHESTRATOR:
        raise AgentRoleError(
            "Un proceso hijo no puede elevarse a `orchestrator`; "
            "usa `worker` o `reviewer`."
        )

    effective_role = explicit_role or (
        ROLE_WORKER if inherited_run_id else ROLE_ORCHESTRATOR
    )
    effective_parent = parent_run_id or inherited_run_id
    effective_run = run_id
    if inherited_run_id and not str(effective_run or "").strip():
        effective_run = f"{inherited_run_id}:child:{uuid.uuid4().hex[:12]}"

    return normalize_role_context(
        role=effective_role,
        run_id=effective_run,
        parent_run_id=effective_parent,
        handoff_ref=handoff_ref,
    )


def normalize_role_context(
    *,
    role: object = ROLE_ORCHESTRATOR,
    run_id: object = None,
    parent_run_id: object = None,
    handoff_ref: object = None,
) -> AgentRoleContext:
    role_text = str(role or ROLE_ORCHESTRATOR).strip().lower()
    if role_text not in SUPPORTED_AGENT_ROLES:
        raise AgentRoleError(
            f"Rol de agente no soportado `{role_text}`. "
            f"Valores validos: {', '.join(sorted(SUPPORTED_AGENT_ROLES))}."
        )

    run_text = str(run_id or "").strip()
    parent_text = str(parent_run_id or "").strip() or None
    handoff_text = str(handoff_ref or "").strip() or None

    if not run_text:
        if role_text == ROLE_ORCHESTRATOR:
            run_text = "standalone-orchestrator"
        else:
            raise AgentRoleError(f"El rol `{role_text}` requiere `run_id`.")

    if role_text == ROLE_ORCHESTRATOR:
        if parent_text:
            raise AgentRoleError("Un `orchestrator` no puede tener `parent_run_id`.")
    elif not parent_text:
        raise AgentRoleError(f"El rol `{role_text}` requiere `parent_run_id`.")

    if role_text in {ROLE_WORKER, ROLE_REVIEWER} and not handoff_text:
        raise AgentRoleError(f"El rol `{role_text}` requiere una referencia `handoff`.")

    return AgentRoleContext(
        role=role_text,
        run_id=run_text,
        parent_run_id=parent_text,
        handoff_ref=handoff_text,
    )


def select_orchestrator_executor(
    executors: Mapping[str, AgentExecutor],
    *,
    executable_status: Callable[[str], str],
    priority: tuple[str, ...] = ORCHESTRATOR_EXECUTOR_PRIORITY,
) -> tuple[AgentExecutor, dict[str, object]]:
    """Select the first available orchestration-capable executor.

    The selector only proves executable availability. Resource/provider/model
    readiness remains a launch-time concern and must be reported separately.
    """
    candidates: list[dict[str, object]] = []
    for candidate_id in priority:
        executor_id = candidate_id
        if candidate_id == "opencode-go":
            executor_id = "opencode"
        executor = executors.get(executor_id)
        if executor is None:
            candidates.append({"id": candidate_id, "status": "unregistered"})
            continue
        status = executable_status(executor.executable)
        candidates.append(
            {
                "id": candidate_id,
                "executor": executor.executor_id,
                "status": status,
            }
        )
        if status == "ready":
            return executor, {
                "role": ROLE_ORCHESTRATOR,
                "selected": candidate_id,
                "executor": executor.executor_id,
                "candidates": candidates,
                "selection_basis": "capability_priority_after_executable_filter",
            }

    raise AgentRoleError(
        "No hay un executor disponible para el rol `orchestrator`. "
        + "; ".join(f"{item['id']}={item['status']}" for item in candidates)
    )
