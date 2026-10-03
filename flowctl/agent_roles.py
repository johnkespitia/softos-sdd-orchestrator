from __future__ import annotations

from dataclasses import dataclass
import os
import uuid
from typing import Callable, Mapping, Optional, Sequence

from .agent_executors import AgentExecutor
from .agent_resources import (
    AgentResource,
    WORK_CLASS_INDEPENDENT_REVIEW,
    normalize_availability,
    select_resource_candidates,
    SELECTABLE_AVAILABILITY_STATES,
)

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
# `antigravity` stays absent until RB5 admission: dedicated adapter + registry
# entry + doctor ready (see docs/agent-executors.md). Do not append it here
# while that gap remains.
ORCHESTRATOR_EXECUTOR_PRIORITY = ("codex", "cursor", "opencode-go", "opencode")

# RB1 independent-review preference chain (resource/executor ids, never model names).
INDEPENDENT_REVIEW_PREFERRED_ORDER = ("codex", "cursor", "opencode-free")


class AgentRoleError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        skip_reasons: Optional[Sequence[Mapping[str, object]]] = None,
    ) -> None:
        super().__init__(message)
        self.skip_reasons = [dict(item) for item in (skip_reasons or ())]


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


def select_reviewer_candidates(
    resources: Mapping[str, AgentResource],
    *,
    availability: Mapping[str, object],
    implementer_executor: str,
    implementer_model_resolution: str,
    required_capabilities: Optional[Sequence[str]] = None,
    data_sensitivity: Optional[str] = None,
    preferred_order: Sequence[str] = INDEPENDENT_REVIEW_PREFERRED_ORDER,
) -> tuple[list[str], dict[str, object]]:
    """Select independent reviewer resource candidates (RB4).

    Excludes the implementer executor and model_resolution, then applies
    capability/availability/sensitivity filtering and preferred_order. Routing
    never uses a concrete model name — only family signals (cost_tier /
    model_resolution).
    """
    implementer_exec = str(implementer_executor or "").strip()
    implementer_resolution = str(implementer_model_resolution or "").strip()
    if not implementer_exec or not implementer_resolution:
        raise AgentRoleError(
            "select_reviewer_candidates requiere implementer_executor e "
            "implementer_model_resolution."
        )

    excluded: list[dict[str, object]] = []
    after_identity: list[str] = []
    implementer_cost_tiers: set[str] = set()

    for resource_id, resource in sorted(resources.items()):
        if resource.executor_id == implementer_exec:
            implementer_cost_tiers.add(resource.cost_tier)
            excluded.append({"id": resource_id, "reason": "same_executor_as_implementer"})
            continue
        if resource.model_resolution == implementer_resolution:
            implementer_cost_tiers.add(resource.cost_tier)
            excluded.append(
                {"id": resource_id, "reason": "same_model_resolution_as_implementer"}
            )
            continue
        after_identity.append(resource_id)

    identity_resources = {
        resource_id: resources[resource_id] for resource_id in after_identity
    }
    ordered, wrapper_payload = select_resource_candidates(
        identity_resources,
        availability=availability,
        work_class=WORK_CLASS_INDEPENDENT_REVIEW,
        required_capabilities=required_capabilities,
        data_sensitivity=data_sensitivity,
        preferred_order=preferred_order,
    )
    filtered = list(wrapper_payload.get("filtered") or [])
    filtered_set = set(filtered)
    required = tuple(
        item.strip() for item in (required_capabilities or ()) if str(item).strip()
    )
    for resource_id in after_identity:
        if resource_id in filtered_set:
            continue
        resource = resources[resource_id]
        state = normalize_availability(availability.get(resource_id))
        if state not in SELECTABLE_AVAILABILITY_STATES:
            excluded.append({"id": resource_id, "reason": f"availability:{state}"})
            continue
        if required and not set(required).issubset(resource.capabilities):
            excluded.append({"id": resource_id, "reason": "missing_required_capabilities"})
            continue
        if data_sensitivity == "local-only" and resource.data_sensitivity != "local-only":
            excluded.append({"id": resource_id, "reason": "data_sensitivity_mismatch"})
            continue
        excluded.append({"id": resource_id, "reason": "filtered_out"})
    # Prefer another model family (cost_tier) without consulting model names.
    if implementer_cost_tiers:
        other_family = [
            resource_id
            for resource_id in ordered
            if resources[resource_id].cost_tier not in implementer_cost_tiers
        ]
        same_family = [
            resource_id
            for resource_id in ordered
            if resources[resource_id].cost_tier in implementer_cost_tiers
        ]
        ordered = other_family + same_family

    skip_reasons = list(excluded)
    if not ordered:
        raise AgentRoleError(
            "No hay un reviewer independiente disponible. "
            + "; ".join(f"{item['id']}={item['reason']}" for item in skip_reasons),
            skip_reasons=skip_reasons,
        )

    selected = ordered[0]
    reason_parts = [
        f"excluded {item['id']} ({item['reason']})" for item in excluded[:3]
    ]
    selection_reason = (
        "; ".join(reason_parts)
        if reason_parts
        else "independent candidate after implementer exclusion"
    )
    payload: dict[str, object] = {
        "role": ROLE_REVIEWER,
        "candidates": ordered,
        "selected": selected,
        "selection_basis": (
            "capability_filter_then_preferred_order_with_implementer_exclusion"
        ),
        "selection_reason": selection_reason,
        "excluded": excluded,
        "skip_reasons": skip_reasons,
        "implementer_executor": implementer_exec,
        "implementer_model_resolution": implementer_resolution,
    }
    return ordered, payload
