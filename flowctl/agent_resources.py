from __future__ import annotations

import fnmatch
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Optional, Protocol, Sequence

from flowctl.agent_executors import (
    AgentRegistryError,
    load_json_object_with_duplicate_detection,
    parse_agents_registry,
)

RESOURCE_SCHEMA_VERSION = 1
RESOURCE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
LOCAL_WORKER_NAME = "softos-local-worker"
CLOUD_WORKER_NAME = "softos-cloud-worker"
LOCAL_MODEL_ID = "lmstudio/prism-ml/bonsai-27b"
FREE_PROVIDER_NAMESPACE = "opencode"
FREE_MODEL_GLOB = "*-free"
GO_PROVIDER_NAMESPACE = "opencode-go"
OPENCODE_CONFIG_CONTENT_ENV = "OPENCODE_CONFIG_CONTENT"
ALLOWED_PROCESS_ENV_OVERLAY_KEYS = frozenset({OPENCODE_CONFIG_CONTENT_ENV})

AVAILABILITY_STATES = frozenset(
    {
        "AVAILABLE",
        "BUSY",
        "CAPACITY_EXHAUSTED",
        "QUOTA_EXHAUSTED",
        "AUTH_UNCONFIGURED",
        "AUTH_FAILED",
        "MODEL_UNAVAILABLE",
        "PROVIDER_DOWN",
        "COOLDOWN",
        "UNKNOWN",
    }
)

SELECTABLE_AVAILABILITY_STATES = frozenset({"AVAILABLE"})

FORBIDDEN_RESOURCE_FIELD_NAMES = frozenset(
    {
        "api_key",
        "apikey",
        "auth_token",
        "credential",
        "credentials",
        "password",
        "secret",
        "token",
        "OPENCODE_GO_TOKEN",
    }
)

FORBIDDEN_MODEL_RESOLUTION_MODES = frozenset({"fixed_model", "hardcoded_model"})

RESOURCE_FIELDS = frozenset(
    {
        "executor",
        "tier",
        "capacity",
        "capabilities",
        "data_sensitivity",
        "local_profile",
        "model_resolution",
    }
)

LOCAL_PROFILE_FIELDS = frozenset({"opencode_config", "worker"})
MODEL_RESOLUTION_FIELDS = frozenset(
    {"mode", "provider_namespace", "candidate_pattern", "tie_break"}
)


class AgentResourceError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class ModelCatalogEntry:
    model_id: str
    provider_namespace: str
    capabilities: frozenset[str] = frozenset()


@dataclass(frozen=True)
class RuntimeEvidence:
    auth_configured: Mapping[str, bool] | None = None
    provider_states: Mapping[str, str] | None = None
    capacity_in_use: Mapping[str, int] | None = None
    raw_availability: str | None = None


@dataclass(frozen=True)
class LocalProfile:
    opencode_config: str
    worker: str


@dataclass(frozen=True)
class ModelResolutionPolicy:
    mode: str
    provider_namespace: str
    candidate_pattern: str | None
    tie_break: str


@dataclass(frozen=True)
class LogicalResource:
    resource_id: str
    executor_id: str
    tier: str
    capacity: int
    capabilities: tuple[str, ...]
    data_sensitivity: str
    local_profile: LocalProfile | None
    model_resolution: ModelResolutionPolicy | None


@dataclass(frozen=True)
class ResourceAvailability:
    state: str
    reason: str
    selectable: bool


@dataclass(frozen=True)
class ResolvedModel:
    resource_id: str
    model_id: str | None
    availability: ResourceAvailability


@dataclass(frozen=True)
class AgentRunResolution:
    resource_id: str | None
    executor_id: str
    env_overlay: dict[str, str]


class ModelCatalogDiscovery(Protocol):
    def list_models(self) -> Sequence[ModelCatalogEntry]:
        ...

    def get_provider_state(self, provider_namespace: str) -> str | None:
        ...


def _collect_forbidden_fields(value: object, *, path: str = "") -> list[str]:
    violations: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key)
            current = f"{path}.{key_text}" if path else key_text
            if key_text in FORBIDDEN_RESOURCE_FIELD_NAMES:
                violations.append(current)
            if key_text == "model" and path.endswith("model_resolution"):
                violations.append(current)
            violations.extend(_collect_forbidden_fields(nested, path=current))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            violations.extend(_collect_forbidden_fields(nested, path=f"{path}[{index}]"))
    return violations


def _validate_positive_int(value: object, *, field: str) -> int:
    if type(value) is not int or isinstance(value, bool) or value < 1:
        raise AgentResourceError(f"`{field}` debe ser un entero positivo; recibido `{value!r}`.")
    return value


def _parse_capabilities(value: object, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise AgentResourceError(f"`{field}` debe ser un arreglo no vacio de strings.")
    capabilities: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise AgentResourceError(f"`{field}[{index}]` debe ser un string no vacio.")
        capabilities.append(item.strip())
    return tuple(capabilities)


def _parse_local_profile(value: object, *, field: str) -> LocalProfile:
    if not isinstance(value, dict):
        raise AgentResourceError(f"`{field}` debe ser un objeto.")
    unknown = set(value) - LOCAL_PROFILE_FIELDS
    if unknown:
        raise AgentResourceError(f"Campo desconocido en `{field}`: `{sorted(unknown)[0]}`.")
    opencode_config = value.get("opencode_config")
    worker = value.get("worker")
    if not isinstance(opencode_config, str) or not opencode_config.strip():
        raise AgentResourceError(f"`{field}.opencode_config` debe ser un string no vacio.")
    if not isinstance(worker, str) or not worker.strip():
        raise AgentResourceError(f"`{field}.worker` debe ser un string no vacio.")
    return LocalProfile(opencode_config=opencode_config.strip(), worker=worker.strip())


def _parse_model_resolution(value: object, *, field: str) -> ModelResolutionPolicy:
    if not isinstance(value, dict):
        raise AgentResourceError(f"`{field}` debe ser un objeto.")
    unknown = set(value) - MODEL_RESOLUTION_FIELDS
    if unknown:
        raise AgentResourceError(f"Campo desconocido en `{field}`: `{sorted(unknown)[0]}`.")
    mode = value.get("mode")
    provider_namespace = value.get("provider_namespace")
    if not isinstance(mode, str) or not mode.strip():
        raise AgentResourceError(f"`{field}.mode` debe ser un string no vacio.")
    mode = mode.strip()
    if mode in FORBIDDEN_MODEL_RESOLUTION_MODES:
        raise AgentResourceError(f"`{field}.mode` no permitido: `{mode}`.")
    if not isinstance(provider_namespace, str) or not provider_namespace.strip():
        raise AgentResourceError(f"`{field}.provider_namespace` debe ser un string no vacio.")
    candidate_pattern = value.get("candidate_pattern")
    if candidate_pattern is not None and (
        not isinstance(candidate_pattern, str) or not candidate_pattern.strip()
    ):
        raise AgentResourceError(f"`{field}.candidate_pattern` debe ser un string no vacio cuando se define.")
    tie_break = value.get("tie_break", "lexicographic")
    if not isinstance(tie_break, str) or not tie_break.strip():
        raise AgentResourceError(f"`{field}.tie_break` debe ser un string no vacio.")
    tie_break = tie_break.strip()
    if tie_break != "lexicographic":
        raise AgentResourceError(f"`{field}.tie_break` no soportado: `{tie_break}`.")
    return ModelResolutionPolicy(
        mode=mode,
        provider_namespace=provider_namespace.strip(),
        candidate_pattern=candidate_pattern.strip() if isinstance(candidate_pattern, str) else None,
        tie_break=tie_break,
    )


def _parse_resource_entry(resource_id: str, entry: object) -> LogicalResource:
    if not RESOURCE_ID_PATTERN.fullmatch(resource_id):
        raise AgentResourceError(
            f"ID de recurso invalido `{resource_id}`; debe coincidir con ^[a-z0-9][a-z0-9-]*$."
        )
    if not isinstance(entry, dict):
        raise AgentResourceError(f"`agent_resources.resources.{resource_id}` debe ser un objeto.")
    forbidden_keys = [str(key) for key in entry if str(key) in FORBIDDEN_RESOURCE_FIELD_NAMES]
    if forbidden_keys:
        raise AgentResourceError(
            f"Campo prohibido en `agent_resources.resources.{resource_id}`: `{forbidden_keys[0]}`."
        )
    unknown = set(entry) - RESOURCE_FIELDS
    if unknown:
        raise AgentResourceError(
            f"Campo desconocido en `agent_resources.resources.{resource_id}`: `{sorted(unknown)[0]}`."
        )
    forbidden = _collect_forbidden_fields(entry)
    if forbidden:
        raise AgentResourceError(
            f"Campo prohibido en `agent_resources.resources.{resource_id}`: `{forbidden[0]}`."
        )

    executor_id = entry.get("executor")
    tier = entry.get("tier")
    data_sensitivity = entry.get("data_sensitivity")
    if not isinstance(executor_id, str) or not executor_id.strip():
        raise AgentResourceError(
            f"`agent_resources.resources.{resource_id}.executor` debe ser un string no vacio."
        )
    if not isinstance(tier, str) or not tier.strip():
        raise AgentResourceError(
            f"`agent_resources.resources.{resource_id}.tier` debe ser un string no vacio."
        )
    if not isinstance(data_sensitivity, str) or not data_sensitivity.strip():
        raise AgentResourceError(
            f"`agent_resources.resources.{resource_id}.data_sensitivity` debe ser un string no vacio."
        )

    capacity = _validate_positive_int(
        entry.get("capacity"),
        field=f"agent_resources.resources.{resource_id}.capacity",
    )
    capabilities = _parse_capabilities(
        entry.get("capabilities"),
        field=f"agent_resources.resources.{resource_id}.capabilities",
    )

    local_profile_raw = entry.get("local_profile")
    model_resolution_raw = entry.get("model_resolution")
    local_profile = (
        _parse_local_profile(local_profile_raw, field=f"agent_resources.resources.{resource_id}.local_profile")
        if local_profile_raw is not None
        else None
    )
    model_resolution = (
        _parse_model_resolution(
            model_resolution_raw,
            field=f"agent_resources.resources.{resource_id}.model_resolution",
        )
        if model_resolution_raw is not None
        else None
    )

    if local_profile is None and model_resolution is None:
        raise AgentResourceError(
            f"`agent_resources.resources.{resource_id}` debe declarar `local_profile` o `model_resolution`."
        )
    if local_profile is not None and model_resolution is not None:
        raise AgentResourceError(
            f"`agent_resources.resources.{resource_id}` no puede declarar `local_profile` y `model_resolution`."
        )

    return LogicalResource(
        resource_id=resource_id,
        executor_id=executor_id.strip(),
        tier=tier.strip(),
        capacity=capacity,
        capabilities=capabilities,
        data_sensitivity=data_sensitivity.strip(),
        local_profile=local_profile,
        model_resolution=model_resolution,
    )


def parse_agent_resources_section(
    workspace_config: dict[str, object],
    *,
    executors: Mapping[str, object] | None = None,
) -> dict[str, LogicalResource]:
    section = workspace_config.get("agent_resources")
    if section is None:
        raise AgentResourceError("workspace.config.json debe definir la seccion `agent_resources`.")
    if not isinstance(section, dict):
        raise AgentResourceError("`agent_resources` debe ser un objeto.")

    schema_version = section.get("schema_version")
    if type(schema_version) is not int or schema_version != RESOURCE_SCHEMA_VERSION:
        raise AgentResourceError(
            f"`agent_resources.schema_version` debe ser {RESOURCE_SCHEMA_VERSION}; recibido `{schema_version!r}`."
        )

    resources_raw = section.get("resources")
    if not isinstance(resources_raw, dict) or not resources_raw:
        raise AgentResourceError("`agent_resources.resources` debe ser un objeto no vacio.")

    unknown_section_fields = set(section) - {"schema_version", "resources"}
    if unknown_section_fields:
        raise AgentResourceError(
            f"Campo desconocido en `agent_resources`: `{sorted(unknown_section_fields)[0]}`."
        )

    if executors is None:
        executors = parse_agents_registry(workspace_config)

    resources: dict[str, LogicalResource] = {}
    for resource_id, entry in resources_raw.items():
        resource = _parse_resource_entry(str(resource_id), entry)
        if resource.executor_id not in executors:
            raise AgentResourceError(
                f"`agent_resources.resources.{resource.resource_id}.executor` referencia "
                f"un executor desconocido: `{resource.executor_id}`."
            )
        if resource.resource_id in resources:
            raise AgentResourceError(f"ID de recurso duplicado: `{resource.resource_id}`.")
        resources[resource.resource_id] = resource

    return dict(sorted(resources.items()))


def load_agent_resources(path: Path) -> dict[str, LogicalResource]:
    workspace_config = load_json_object_with_duplicate_detection(path)
    return parse_agent_resources_section(workspace_config)


def load_opencode_config(path: Path) -> dict[str, object]:
    payload = load_json_object_with_duplicate_detection(path)
    return payload


def _agent_model_from_config(agent_config: object) -> str | None:
    if not isinstance(agent_config, dict):
        return None
    model = agent_config.get("model")
    if isinstance(model, str) and model.strip():
        return model.strip()
    return None


def resolve_local_profile_model(
    *,
    opencode_config: Mapping[str, object],
    worker: str,
) -> str:
    default_agent = opencode_config.get("default_agent")
    if isinstance(default_agent, str) and default_agent.strip() == worker:
        top_level_model = opencode_config.get("model")
        if isinstance(top_level_model, str) and top_level_model.strip():
            return top_level_model.strip()

    agents = opencode_config.get("agent")
    if isinstance(agents, dict):
        agent_config = agents.get(worker)
        model = _agent_model_from_config(agent_config)
        if model is not None:
            return model

    raise AgentResourceError(
        f"No pude resolver el modelo del worker OpenCode `{worker}` desde la configuracion versionada."
    )


def resolve_local_resource_model(
    *,
    resource: LogicalResource,
    workspace_root: Path,
) -> ResolvedModel:
    if resource.local_profile is None:
        raise AgentResourceError(
            f"El recurso `{resource.resource_id}` no declara un perfil local versionado."
        )
    profile = resource.local_profile
    config_path = workspace_root / profile.opencode_config
    opencode_config = load_opencode_config(config_path)
    model_id = resolve_local_profile_model(opencode_config=opencode_config, worker=profile.worker)
    availability = ResourceAvailability(
        state="AVAILABLE",
        reason="local_profile_resolved",
        selectable=True,
    )
    return ResolvedModel(
        resource_id=resource.resource_id,
        model_id=model_id,
        availability=availability,
    )


def _basename_model_id(model_id: str) -> str:
    if "/" in model_id:
        return model_id.rsplit("/", 1)[-1]
    return model_id


def is_free_model_candidate(
    entry: ModelCatalogEntry,
    *,
    provider_namespace: str,
    candidate_pattern: str,
) -> bool:
    if entry.provider_namespace != provider_namespace:
        return False
    basename = _basename_model_id(entry.model_id)
    return fnmatch.fnmatchcase(basename, candidate_pattern)


def is_go_model_candidate(
    entry: ModelCatalogEntry,
    *,
    provider_namespace: str,
) -> bool:
    if entry.provider_namespace != provider_namespace:
        return False
    basename = _basename_model_id(entry.model_id).lower()
    if basename.endswith("-free"):
        return False
    return True


def _sorted_candidates(candidates: Sequence[ModelCatalogEntry]) -> list[ModelCatalogEntry]:
    return sorted(candidates, key=lambda item: item.model_id)


def normalize_availability(
    raw_state: str | None,
    *,
    reason: str = "",
) -> ResourceAvailability:
    if raw_state is None:
        return ResourceAvailability(state="UNKNOWN", reason=reason or "missing_evidence", selectable=False)
    normalized = raw_state.strip().upper()
    if normalized not in AVAILABILITY_STATES:
        return ResourceAvailability(state="UNKNOWN", reason=reason or "unrecognized_evidence", selectable=False)
    return ResourceAvailability(
        state=normalized,
        reason=reason or normalized.lower(),
        selectable=normalized in SELECTABLE_AVAILABILITY_STATES,
    )


def _capacity_availability(
    resource: LogicalResource,
    evidence: RuntimeEvidence | None,
) -> ResourceAvailability | None:
    if evidence is None or evidence.capacity_in_use is None:
        return None
    in_use = evidence.capacity_in_use.get(resource.resource_id, 0)
    if in_use >= resource.capacity:
        return ResourceAvailability(
            state="CAPACITY_EXHAUSTED",
            reason="capacity_exhausted",
            selectable=False,
        )
    return None


def _provider_availability(
    *,
    provider_namespace: str,
    discovery: ModelCatalogDiscovery,
    evidence: RuntimeEvidence | None,
) -> ResourceAvailability | None:
    if evidence is not None and evidence.provider_states is not None:
        raw = evidence.provider_states.get(provider_namespace)
        if raw is not None:
            availability = normalize_availability(raw)
            if availability.state != "AVAILABLE":
                return availability
    provider_state = discovery.get_provider_state(provider_namespace)
    if provider_state is None:
        return None
    availability = normalize_availability(provider_state)
    if availability.state != "AVAILABLE":
        return availability
    return None


def resolve_free_model(
    *,
    resource: LogicalResource,
    discovery: ModelCatalogDiscovery,
    evidence: RuntimeEvidence | None = None,
) -> ResolvedModel:
    if resource.model_resolution is None or resource.model_resolution.mode != "dynamic_free":
        raise AgentResourceError(f"El recurso `{resource.resource_id}` no usa resolucion dinamica free.")

    capacity_state = _capacity_availability(resource, evidence)
    if capacity_state is not None:
        return ResolvedModel(resource.resource_id, None, capacity_state)

    policy = resource.model_resolution
    provider_state = _provider_availability(
        provider_namespace=policy.provider_namespace,
        discovery=discovery,
        evidence=evidence,
    )
    if provider_state is not None:
        return ResolvedModel(resource.resource_id, None, provider_state)

    if evidence is not None and evidence.raw_availability is not None:
        mapped = normalize_availability(evidence.raw_availability)
        if mapped.state != "AVAILABLE":
            return ResolvedModel(resource.resource_id, None, mapped)

    pattern = policy.candidate_pattern or FREE_MODEL_GLOB
    candidates = [
        entry
        for entry in discovery.list_models()
        if is_free_model_candidate(
            entry,
            provider_namespace=policy.provider_namespace,
            candidate_pattern=pattern,
        )
    ]
    if not candidates:
        return ResolvedModel(
            resource.resource_id,
            None,
            ResourceAvailability(
                state="MODEL_UNAVAILABLE",
                reason="no_free_candidate",
                selectable=False,
            ),
        )

    selected = _sorted_candidates(candidates)[0]
    return ResolvedModel(
        resource.resource_id,
        selected.model_id,
        ResourceAvailability(state="AVAILABLE", reason="free_candidate_selected", selectable=True),
    )


def _go_provider_raw_state(
    *,
    provider_namespace: str,
    discovery: ModelCatalogDiscovery,
    evidence: RuntimeEvidence | None,
) -> str | None:
    if evidence is not None and evidence.provider_states is not None:
        raw = evidence.provider_states.get(provider_namespace)
        if raw is not None:
            return raw
    return discovery.get_provider_state(provider_namespace)


def _go_auth_or_provider_gate(
    *,
    resource: LogicalResource,
    discovery: ModelCatalogDiscovery,
    evidence: RuntimeEvidence | None,
    provider_namespace: str,
) -> ResourceAvailability | None:
    if evidence is not None and evidence.auth_configured is not None:
        if resource.resource_id in evidence.auth_configured:
            if not evidence.auth_configured[resource.resource_id]:
                return ResourceAvailability(
                    state="AUTH_UNCONFIGURED",
                    reason="auth_unconfigured",
                    selectable=False,
                )

    injected_auth = (
        evidence is not None
        and evidence.auth_configured is not None
        and evidence.auth_configured.get(resource.resource_id) is True
    )

    provider_raw = _go_provider_raw_state(
        provider_namespace=provider_namespace,
        discovery=discovery,
        evidence=evidence,
    )

    if not injected_auth:
        if provider_raw is None:
            return ResourceAvailability(
                state="AUTH_UNCONFIGURED",
                reason="auth_unconfigured",
                selectable=False,
            )
        availability = normalize_availability(provider_raw)
        if availability.state != "AVAILABLE":
            return availability
        return None

    if provider_raw is not None:
        availability = normalize_availability(provider_raw)
        if availability.state != "AVAILABLE":
            return availability
    return None


def resolve_go_model(
    *,
    resource: LogicalResource,
    discovery: ModelCatalogDiscovery,
    evidence: RuntimeEvidence | None = None,
) -> ResolvedModel:
    if resource.model_resolution is None or resource.model_resolution.mode != "dynamic_go":
        raise AgentResourceError(f"El recurso `{resource.resource_id}` no usa resolucion dinamica go.")

    policy = resource.model_resolution

    auth_gate = _go_auth_or_provider_gate(
        resource=resource,
        discovery=discovery,
        evidence=evidence,
        provider_namespace=policy.provider_namespace,
    )
    if auth_gate is not None:
        return ResolvedModel(resource.resource_id, None, auth_gate)

    capacity_state = _capacity_availability(resource, evidence)
    if capacity_state is not None:
        return ResolvedModel(resource.resource_id, None, capacity_state)

    if evidence is not None and evidence.raw_availability is not None:
        mapped = normalize_availability(evidence.raw_availability)
        if mapped.state != "AVAILABLE":
            return ResolvedModel(resource.resource_id, None, mapped)

    candidates = [
        entry
        for entry in discovery.list_models()
        if is_go_model_candidate(entry, provider_namespace=policy.provider_namespace)
    ]
    if not candidates:
        return ResolvedModel(
            resource.resource_id,
            None,
            ResourceAvailability(
                state="MODEL_UNAVAILABLE",
                reason="no_go_candidate",
                selectable=False,
            ),
        )

    selected = _sorted_candidates(candidates)[0]
    return ResolvedModel(
        resource.resource_id,
        selected.model_id,
        ResourceAvailability(state="AVAILABLE", reason="go_candidate_selected", selectable=True),
    )


def resolve_resource_model(
    *,
    resource: LogicalResource,
    workspace_root: Path,
    discovery: ModelCatalogDiscovery | None = None,
    evidence: RuntimeEvidence | None = None,
) -> ResolvedModel:
    if resource.local_profile is not None:
        resolved = resolve_local_resource_model(resource=resource, workspace_root=workspace_root)
        capacity_state = _capacity_availability(resource, evidence)
        if capacity_state is not None:
            return ResolvedModel(resource.resource_id, resolved.model_id, capacity_state)
        if evidence is not None and evidence.raw_availability is not None:
            mapped = normalize_availability(evidence.raw_availability)
            if mapped.state != "AVAILABLE":
                return ResolvedModel(resource.resource_id, resolved.model_id, mapped)
        return resolved

    if discovery is None:
        raise AgentResourceError(
            f"El recurso `{resource.resource_id}` requiere un boundary de discovery inyectable."
        )

    if resource.model_resolution is not None and resource.model_resolution.mode == "dynamic_free":
        return resolve_free_model(resource=resource, discovery=discovery, evidence=evidence)
    if resource.model_resolution is not None and resource.model_resolution.mode == "dynamic_go":
        return resolve_go_model(resource=resource, discovery=discovery, evidence=evidence)

    raise AgentResourceError(
        f"El recurso `{resource.resource_id}` no tiene una politica de resolucion soportada."
    )


@dataclass(frozen=True)
class FixtureModelCatalogDiscovery:
    models: tuple[ModelCatalogEntry, ...]
    provider_states: Mapping[str, str] | None = None

    def list_models(self) -> Sequence[ModelCatalogEntry]:
        return self.models

    def get_provider_state(self, provider_namespace: str) -> str | None:
        if self.provider_states is None:
            return None
        return self.provider_states.get(provider_namespace)


def dumps_resource_diagnostics(
    resources: Mapping[str, LogicalResource],
    *,
    workspace_root: Path,
    discovery: ModelCatalogDiscovery | None = None,
    evidence: RuntimeEvidence | None = None,
    json_dumps: Callable[[object], str] = json.dumps,
) -> str:
    payload: dict[str, object] = {"resources": []}
    for resource in resources.values():
        resolved = resolve_resource_model(
            resource=resource,
            workspace_root=workspace_root,
            discovery=discovery,
            evidence=evidence,
        )
        payload["resources"].append(
            {
                "id": resource.resource_id,
                "executor": resource.executor_id,
                "tier": resource.tier,
                "capacity": resource.capacity,
                "capabilities": list(resource.capabilities),
                "data_sensitivity": resource.data_sensitivity,
                "availability": resolved.availability.state,
                "reason": resolved.availability.reason,
                "selectable": resolved.availability.selectable,
                "model_id": resolved.model_id,
            }
        )
    return json_dumps(payload)


def _overlay_value_is_safe(value: str) -> bool:
    lowered = value.lower()
    for forbidden in FORBIDDEN_RESOURCE_FIELD_NAMES:
        if forbidden.lower() in lowered:
            return False
    return True


def build_opencode_model_config_content(model_id: str) -> str:
    candidate = model_id.strip()
    if not candidate:
        raise AgentResourceError("El modelo resuelto debe ser un string no vacio.")
    if not _overlay_value_is_safe(candidate):
        raise AgentResourceError("El modelo resuelto contiene material prohibido.")
    payload = {
        "model": candidate,
        "default_agent": CLOUD_WORKER_NAME,
        "agent": {
            CLOUD_WORKER_NAME: {
                "model": candidate,
            }
        },
    }
    serialized = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
    if not _overlay_value_is_safe(serialized):
        raise AgentResourceError("La configuracion OpenCode overlay contiene material prohibido.")
    return serialized


def _validate_opencode_cloud_overlay(parsed: dict[str, object]) -> None:
    allowed_top_level = frozenset({"model", "default_agent", "agent"})
    unknown_top = set(parsed) - allowed_top_level
    if unknown_top:
        raise AgentResourceError(
            f"`{OPENCODE_CONFIG_CONTENT_ENV}` contiene campo no permitido: `{sorted(unknown_top)[0]}`."
        )

    model = parsed.get("model")
    if not isinstance(model, str) or not model.strip():
        raise AgentResourceError(
            f"`{OPENCODE_CONFIG_CONTENT_ENV}` debe declarar `model` como string no vacio."
        )
    model = model.strip()

    default_agent = parsed.get("default_agent")
    if not isinstance(default_agent, str) or default_agent.strip() != CLOUD_WORKER_NAME:
        raise AgentResourceError(
            f"`{OPENCODE_CONFIG_CONTENT_ENV}` debe declarar `default_agent` como `{CLOUD_WORKER_NAME}`."
        )

    agents = parsed.get("agent")
    if not isinstance(agents, dict):
        raise AgentResourceError(f"`{OPENCODE_CONFIG_CONTENT_ENV}` debe declarar `agent` como objeto.")
    if set(agents) != {CLOUD_WORKER_NAME}:
        raise AgentResourceError(
            f"`{OPENCODE_CONFIG_CONTENT_ENV}` debe declarar solo el worker `{CLOUD_WORKER_NAME}`."
        )

    worker_config = agents.get(CLOUD_WORKER_NAME)
    if not isinstance(worker_config, dict):
        raise AgentResourceError(
            f"`{OPENCODE_CONFIG_CONTENT_ENV}.agent.{CLOUD_WORKER_NAME}` debe ser un objeto."
        )
    if set(worker_config) != {"model"}:
        raise AgentResourceError(
            f"`{OPENCODE_CONFIG_CONTENT_ENV}.agent.{CLOUD_WORKER_NAME}` solo puede declarar `model`."
        )
    worker_model = worker_config.get("model")
    if not isinstance(worker_model, str) or not worker_model.strip():
        raise AgentResourceError(
            f"`{OPENCODE_CONFIG_CONTENT_ENV}.agent.{CLOUD_WORKER_NAME}.model` debe ser un string no vacio."
        )
    if worker_model.strip() != model:
        raise AgentResourceError(
            f"`{OPENCODE_CONFIG_CONTENT_ENV}` debe usar el mismo modelo en `model` y "
            f"`agent.{CLOUD_WORKER_NAME}.model`."
        )
    if default_agent.strip() == LOCAL_WORKER_NAME:
        raise AgentResourceError(
            f"`{OPENCODE_CONFIG_CONTENT_ENV}` no puede seleccionar el worker local `{LOCAL_WORKER_NAME}`."
        )


def validate_process_env_overlay(overlay: Mapping[str, str]) -> dict[str, str]:
    if not overlay:
        return {}
    unknown_keys = set(overlay) - ALLOWED_PROCESS_ENV_OVERLAY_KEYS
    if unknown_keys:
        raise AgentResourceError(
            f"Clave de overlay de entorno no permitida: `{sorted(unknown_keys)[0]}`."
        )
    validated: dict[str, str] = {}
    for key, raw_value in overlay.items():
        if not isinstance(raw_value, str):
            raise AgentResourceError(f"El overlay `{key}` debe ser un string.")
        value = raw_value.strip()
        if not value:
            raise AgentResourceError(f"El overlay `{key}` no puede ser vacio.")
        if not _overlay_value_is_safe(value):
            raise AgentResourceError(f"El overlay `{key}` contiene material prohibido.")
        if key == OPENCODE_CONFIG_CONTENT_ENV:
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError as exc:
                raise AgentResourceError(
                    f"`{OPENCODE_CONFIG_CONTENT_ENV}` debe ser JSON valido: {exc}"
                ) from exc
            if not isinstance(parsed, dict):
                raise AgentResourceError(
                    f"`{OPENCODE_CONFIG_CONTENT_ENV}` debe ser un objeto JSON."
                )
            forbidden = _collect_forbidden_fields(parsed)
            if forbidden:
                raise AgentResourceError(
                    f"`{OPENCODE_CONFIG_CONTENT_ENV}` contiene campo prohibido: `{forbidden[0]}`."
                )
            _validate_opencode_cloud_overlay(parsed)
        validated[key] = value
    return validated


def build_resource_process_env_overlay(
    *,
    resource: LogicalResource,
    resolved: ResolvedModel,
) -> dict[str, str]:
    if resource.local_profile is not None:
        return {}
    if not resolved.availability.selectable or resolved.model_id is None:
        return {}
    content = build_opencode_model_config_content(resolved.model_id)
    return validate_process_env_overlay({OPENCODE_CONFIG_CONTENT_ENV: content})


def resource_unavailable_message(
    *,
    resource_id: str,
    availability: ResourceAvailability,
) -> str:
    return (
        f"El recurso `{resource_id}` no esta disponible: "
        f"{availability.state} ({availability.reason})."
    )


def resolve_agent_run_selector(
    selector: str,
    *,
    workspace_root: Path,
    workspace_config: Mapping[str, object],
    executors: Mapping[str, object],
    discovery: ModelCatalogDiscovery | None = None,
    evidence: RuntimeEvidence | None = None,
) -> AgentRunResolution:
    selected = selector.strip()
    if not selected:
        raise AgentResourceError("Debes indicar un selector de executor o recurso.")

    resources_section = workspace_config.get("agent_resources")
    resources: dict[str, LogicalResource] | None = None
    if resources_section is not None:
        resources = parse_agent_resources_section(
            dict(workspace_config),
            executors=executors,
        )

    if resources is not None and selected in resources:
        resource = resources[selected]
        resolved = resolve_resource_model(
            resource=resource,
            workspace_root=workspace_root,
            discovery=discovery,
            evidence=evidence,
        )
        if not resolved.availability.selectable:
            raise AgentResourceError(
                resource_unavailable_message(
                    resource_id=resource.resource_id,
                    availability=resolved.availability,
                )
            )
        overlay = build_resource_process_env_overlay(resource=resource, resolved=resolved)
        return AgentRunResolution(
            resource_id=resource.resource_id,
            executor_id=resource.executor_id,
            env_overlay=overlay,
        )

    if selected not in executors:
        raise AgentResourceError(f"Executor desconocido: `{selected}`.")

    return AgentRunResolution(
        resource_id=None,
        executor_id=selected,
        env_overlay={},
    )


def _subprocess_stream_text(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value or "")


def _parse_plaintext_model_catalog_lines(text: str) -> tuple[ModelCatalogEntry, ...]:
    entries: list[ModelCatalogEntry] = []
    for line in text.splitlines():
        model_id = line.strip()
        if not model_id or "/" not in model_id:
            continue
        provider_namespace, remainder = model_id.split("/", 1)
        if not provider_namespace or not remainder.strip():
            continue
        entries.append(
            ModelCatalogEntry(
                model_id=model_id,
                provider_namespace=provider_namespace,
            )
        )
    return tuple(entries)


_PROVIDER_NOT_FOUND_PATTERN = re.compile(r"Provider not found:\s*\S+", re.IGNORECASE)


def _interpret_provider_probe_output(
    *,
    returncode: int,
    stdout: str,
    stderr: str,
) -> str | None:
    if returncode == 0:
        return "AVAILABLE"
    combined = f"{stdout}\n{stderr}".strip()
    if _PROVIDER_NOT_FOUND_PATTERN.search(combined):
        return "AUTH_UNCONFIGURED"
    return "UNKNOWN"


def _parse_model_catalog_entries(payload: object) -> list[ModelCatalogEntry]:
    entries: list[ModelCatalogEntry] = []
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, str) and item.strip():
                model_id = item.strip()
                namespace = model_id.split("/", 1)[0] if "/" in model_id else "opencode"
                entries.append(ModelCatalogEntry(model_id=model_id, provider_namespace=namespace))
            elif isinstance(item, dict):
                model_id = item.get("id") or item.get("model") or item.get("name")
                provider = item.get("provider") or item.get("provider_namespace") or "opencode"
                if isinstance(model_id, str) and model_id.strip():
                    provider_text = str(provider).strip() if isinstance(provider, str) else "opencode"
                    entries.append(
                        ModelCatalogEntry(
                            model_id=model_id.strip(),
                            provider_namespace=provider_text,
                        )
                    )
    elif isinstance(payload, dict):
        for provider_namespace, models in payload.items():
            if not isinstance(provider_namespace, str):
                continue
            if isinstance(models, list):
                for model in models:
                    if isinstance(model, str) and model.strip():
                        model_id = model.strip()
                        if "/" not in model_id:
                            model_id = f"{provider_namespace}/{model_id}"
                        entries.append(
                            ModelCatalogEntry(
                                model_id=model_id,
                                provider_namespace=provider_namespace.strip(),
                            )
                        )
    return entries


@dataclass(frozen=True)
class OpencodeCliModelCatalogDiscovery:
    executable: str = "opencode"
    subprocess_run: Callable[..., object] = subprocess.run

    def list_models(self) -> Sequence[ModelCatalogEntry]:
        completed = self.subprocess_run(
            [self.executable, "models"],
            capture_output=True,
            check=False,
        )
        if int(getattr(completed, "returncode", 1)) != 0:
            return ()
        stdout = _subprocess_stream_text(getattr(completed, "stdout", b""))
        return _parse_plaintext_model_catalog_lines(stdout)

    def get_provider_state(self, provider_namespace: str) -> str | None:
        provider = provider_namespace.strip()
        if not provider:
            return "UNKNOWN"
        completed = self.subprocess_run(
            [self.executable, "models", provider],
            capture_output=True,
            check=False,
        )
        returncode = int(getattr(completed, "returncode", 1))
        stdout = _subprocess_stream_text(getattr(completed, "stdout", b""))
        stderr = _subprocess_stream_text(getattr(completed, "stderr", b""))
        return _interpret_provider_probe_output(
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
        )


def default_model_catalog_discovery(
    *,
    subprocess_run: Callable[..., object] = subprocess.run,
    executable: str = "opencode",
) -> ModelCatalogDiscovery:
    return OpencodeCliModelCatalogDiscovery(
        executable=executable,
        subprocess_run=subprocess_run,
    )


__all__ = [
    "AgentResourceError",
    "AgentRunResolution",
    "AVAILABILITY_STATES",
    "ALLOWED_PROCESS_ENV_OVERLAY_KEYS",
    "FixtureModelCatalogDiscovery",
    "FORBIDDEN_RESOURCE_FIELD_NAMES",
    "CLOUD_WORKER_NAME",
    "LOCAL_MODEL_ID",
    "LOCAL_WORKER_NAME",
    "LogicalResource",
    "ModelCatalogDiscovery",
    "ModelCatalogEntry",
    "OpencodeCliModelCatalogDiscovery",
    "OPENCODE_CONFIG_CONTENT_ENV",
    "ResolvedModel",
    "ResourceAvailability",
    "RuntimeEvidence",
    "build_opencode_model_config_content",
    "build_resource_process_env_overlay",
    "default_model_catalog_discovery",
    "dumps_resource_diagnostics",
    "is_free_model_candidate",
    "is_go_model_candidate",
    "load_agent_resources",
    "load_opencode_config",
    "normalize_availability",
    "parse_agent_resources_section",
    "resolve_agent_run_selector",
    "resolve_free_model",
    "resolve_go_model",
    "resolve_local_profile_model",
    "resolve_local_resource_model",
    "resolve_resource_model",
    "resource_unavailable_message",
    "validate_process_env_overlay",
]
