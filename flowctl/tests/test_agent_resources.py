from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from flowctl.agent_executor_adapters import AgentRunRequest, OpenCodeAdapter, build_execution_contract
from flowctl.agent_executors import AgentExecutor, parse_agents_registry
from flowctl.agent_resources import (
    AVAILABILITY_STATES,
    AgentResourceError,
    CLOUD_WORKER_NAME,
    FixtureModelCatalogDiscovery,
    LOCAL_MODEL_ID,
    LOCAL_WORKER_NAME,
    ModelCatalogEntry,
    OPENCODE_CONFIG_CONTENT_ENV,
    OpencodeCliModelCatalogDiscovery,
    RuntimeEvidence,
    build_opencode_model_config_content,
    dumps_resource_diagnostics,
    is_free_model_candidate,
    is_go_model_candidate,
    load_agent_resources,
    normalize_availability,
    parse_agent_resources_section,
    resolve_agent_run_selector,
    resolve_free_model,
    resolve_go_model,
    resolve_local_profile_model,
    resolve_resource_model,
    validate_process_env_overlay,
)


def _base_agents() -> dict[str, object]:
    return {
        "schema_version": 1,
        "executors": {
            "codex": {"adapter": "codex", "executable": "codex", "argv": []},
            "cursor": {"adapter": "cursor", "executable": "agent", "argv": []},
            "opencode-local": {"adapter": "opencode", "executable": "opencode-softos", "argv": []},
            "opencode-cloud": {"adapter": "opencode", "executable": "opencode", "argv": []},
        },
    }


def _base_resources() -> dict[str, object]:
    return {
        "opencode-local": {
            "executor": "opencode-local",
            "tier": "local",
            "capacity": 1,
            "capabilities": ["tool_calling", "write", "patch_unit"],
            "data_sensitivity": "local-only",
            "local_profile": {
                "opencode_config": "opencode.json",
                "worker": LOCAL_WORKER_NAME,
            },
        },
        "opencode-free": {
            "executor": "opencode-cloud",
            "tier": "cloud_free",
            "capacity": 1,
            "capabilities": ["tool_calling", "write", "patch_unit"],
            "data_sensitivity": "cloud-eligible",
            "model_resolution": {
                "mode": "dynamic_free",
                "provider_namespace": "opencode",
                "candidate_pattern": "*-free",
                "tie_break": "lexicographic",
            },
        },
        "opencode-go": {
            "executor": "opencode-cloud",
            "tier": "cloud_paid_low",
            "capacity": 1,
            "capabilities": ["tool_calling", "write", "review"],
            "data_sensitivity": "cloud-eligible",
            "model_resolution": {
                "mode": "dynamic_go",
                "provider_namespace": "opencode-go",
                "tie_break": "lexicographic",
            },
        },
    }


def _workspace_config(*, resources: object | None = None, agents: object | None = None) -> dict[str, object]:
    return {
        "project": {"display_name": "Test", "root_repo": "sdd-workspace-boilerplate"},
        "repos": {"sdd-workspace-boilerplate": {"path": ".", "kind": "root"}},
        "agents": agents if agents is not None else _base_agents(),
        "agent_resources": {
            "schema_version": 1,
            "resources": resources if resources is not None else _base_resources(),
        },
    }


def _write_workspace(root: Path, config: dict[str, object]) -> Path:
    path = root / "workspace.config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def _write_opencode(root: Path) -> Path:
    payload = {
        "$schema": "https://opencode.ai/config.json",
        "default_agent": LOCAL_WORKER_NAME,
        "agent": {
            LOCAL_WORKER_NAME: {
                "model": LOCAL_MODEL_ID,
                "reasoning": True,
                "steps": 6,
            }
        },
    }
    path = root / "opencode.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class AgentResourceConfigValidationTests(unittest.TestCase):
    def test_valid_resources_parse_three_unique_ids(self) -> None:
        resources = parse_agent_resources_section(_workspace_config())
        self.assertEqual(
            ["opencode-free", "opencode-go", "opencode-local"],
            list(resources),
        )

    def test_missing_agent_resources_section_fails(self) -> None:
        with self.assertRaises(AgentResourceError):
            parse_agent_resources_section({"agents": _base_agents()})

    def test_invalid_schema_version_fails(self) -> None:
        config = _workspace_config()
        config["agent_resources"] = {"schema_version": 2, "resources": _base_resources()}
        with self.assertRaisesRegex(AgentResourceError, "schema_version"):
            parse_agent_resources_section(config)

    def test_invalid_resource_id_pattern_fails(self) -> None:
        resources = dict(_base_resources())
        resources["OpenCode-Local"] = resources.pop("opencode-local")
        with self.assertRaisesRegex(AgentResourceError, "ID de recurso invalido"):
            parse_agent_resources_section(_workspace_config(resources=resources))

    def test_unknown_executor_reference_fails(self) -> None:
        resources = dict(_base_resources())
        resources["opencode-local"]["executor"] = "missing-executor"
        with self.assertRaisesRegex(AgentResourceError, "executor desconocido"):
            parse_agent_resources_section(_workspace_config(resources=resources))

    def test_forbidden_token_field_fails(self) -> None:
        resources = dict(_base_resources())
        resources["opencode-free"]["token"] = "secret"
        with self.assertRaisesRegex(AgentResourceError, "prohibido"):
            parse_agent_resources_section(_workspace_config(resources=resources))

    def test_opencode_local_capacity_is_one(self) -> None:
        resources = parse_agent_resources_section(_workspace_config())
        self.assertEqual(1, resources["opencode-local"].capacity)


class LocalProfileResolutionTests(unittest.TestCase):
    def test_local_profile_resolves_bonsai_from_repository_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_opencode(root)
            resources = parse_agent_resources_section(_workspace_config())
            resolved = resolve_resource_model(
                resource=resources["opencode-local"],
                workspace_root=root,
            )
            self.assertEqual(LOCAL_MODEL_ID, resolved.model_id)
            self.assertEqual("AVAILABLE", resolved.availability.state)
            self.assertTrue(resolved.availability.selectable)

    def test_local_profile_reads_worker_model_from_opencode_agent_section(self) -> None:
        opencode = {
            "agent": {
                LOCAL_WORKER_NAME: {
                    "model": LOCAL_MODEL_ID,
                    "reasoning": True,
                }
            }
        }
        self.assertEqual(
            LOCAL_MODEL_ID,
            resolve_local_profile_model(opencode_config=opencode, worker=LOCAL_WORKER_NAME),
        )


class ExecutorContainmentTests(unittest.TestCase):
    def test_generic_executor_contract_has_no_model_or_provider_flags(self) -> None:
        executors = parse_agents_registry(_workspace_config())
        executor = executors["opencode-local"]
        request = AgentRunRequest(
            executor=executor,
            repo="sdd-workspace-boilerplate",
            workspace_root="/workspace",
            workdir="/workspace/.worktrees/demo",
            targets=("flowctl/agent_resources.py",),
            user_prompt="assignment",
            contract_body=build_execution_contract(
                request=AgentRunRequest(
                    executor=executor,
                    repo="sdd-workspace-boilerplate",
                    workspace_root="/workspace",
                    workdir="/workspace/.worktrees/demo",
                    targets=("flowctl/agent_resources.py",),
                    user_prompt="assignment",
                    contract_body="",
                )
            ),
        )
        invocation = OpenCodeAdapter().build_invocation(request)
        joined = " ".join(invocation.argv)
        self.assertNotIn("--model", joined)
        self.assertNotIn("--provider", joined)


class DynamicFreeResolutionTests(unittest.TestCase):
    def test_free_candidates_resolve_from_fixture_catalog(self) -> None:
        resources = parse_agent_resources_section(_workspace_config())
        discovery = FixtureModelCatalogDiscovery(
            models=(
                ModelCatalogEntry("opencode/gpt-5-free", "opencode"),
                ModelCatalogEntry("opencode/claude-free", "opencode"),
                ModelCatalogEntry("opencode/paid-go", "opencode"),
            )
        )
        resolved = resolve_free_model(
            resource=resources["opencode-free"],
            discovery=discovery,
        )
        self.assertEqual("opencode/claude-free", resolved.model_id)
        self.assertEqual("AVAILABLE", resolved.availability.state)

    def test_free_selection_is_deterministic(self) -> None:
        resources = parse_agent_resources_section(_workspace_config())
        discovery = FixtureModelCatalogDiscovery(
            models=(
                ModelCatalogEntry("opencode/zeta-free", "opencode"),
                ModelCatalogEntry("opencode/alpha-free", "opencode"),
            )
        )
        first = resolve_free_model(resource=resources["opencode-free"], discovery=discovery)
        second = resolve_free_model(resource=resources["opencode-free"], discovery=discovery)
        self.assertEqual(first.model_id, second.model_id)
        self.assertEqual("opencode/alpha-free", first.model_id)

    def test_no_free_candidate_returns_model_unavailable(self) -> None:
        resources = parse_agent_resources_section(_workspace_config())
        discovery = FixtureModelCatalogDiscovery(
            models=(ModelCatalogEntry("opencode/paid-go", "opencode"),)
        )
        resolved = resolve_free_model(resource=resources["opencode-free"], discovery=discovery)
        self.assertIsNone(resolved.model_id)
        self.assertEqual("MODEL_UNAVAILABLE", resolved.availability.state)

    def test_free_candidate_filter_matches_suffix_pattern(self) -> None:
        entry = ModelCatalogEntry("opencode/qwen-free", "opencode")
        self.assertTrue(
            is_free_model_candidate(
                entry,
                provider_namespace="opencode",
                candidate_pattern="*-free",
            )
        )


class DynamicGoResolutionTests(unittest.TestCase):
    def test_go_config_provider_namespace_is_opencode_go(self) -> None:
        resources = parse_agent_resources_section(_workspace_config())
        policy = resources["opencode-go"].model_resolution
        assert policy is not None
        self.assertEqual("opencode-go", policy.provider_namespace)

    def test_free_config_provider_namespace_remains_opencode(self) -> None:
        resources = parse_agent_resources_section(_workspace_config())
        policy = resources["opencode-free"].model_resolution
        assert policy is not None
        self.assertEqual("opencode", policy.provider_namespace)

    def test_go_begins_auth_unconfigured_without_auth_evidence(self) -> None:
        resources = parse_agent_resources_section(_workspace_config())
        discovery = FixtureModelCatalogDiscovery(
            models=(ModelCatalogEntry("opencode-go/deepseek-v4-flash", "opencode-go"),)
        )
        resolved = resolve_go_model(
            resource=resources["opencode-go"],
            discovery=discovery,
        )
        self.assertIsNone(resolved.model_id)
        self.assertEqual("AUTH_UNCONFIGURED", resolved.availability.state)
        self.assertFalse(resolved.availability.selectable)

    def test_go_explicit_false_auth_evidence_is_auth_unconfigured(self) -> None:
        resources = parse_agent_resources_section(_workspace_config())
        discovery = FixtureModelCatalogDiscovery(
            models=(ModelCatalogEntry("opencode-go/deepseek-v4-flash", "opencode-go"),),
            provider_states={"opencode-go": "AVAILABLE"},
        )
        evidence = RuntimeEvidence(auth_configured={"opencode-go": False})
        resolved = resolve_go_model(
            resource=resources["opencode-go"],
            discovery=discovery,
            evidence=evidence,
        )
        self.assertIsNone(resolved.model_id)
        self.assertEqual("AUTH_UNCONFIGURED", resolved.availability.state)

    def test_go_resolves_dynamically_with_supported_auth_evidence(self) -> None:
        resources = parse_agent_resources_section(_workspace_config())
        discovery = FixtureModelCatalogDiscovery(
            models=(
                ModelCatalogEntry("opencode-go/zeta-model", "opencode-go"),
                ModelCatalogEntry("opencode-go/alpha-model", "opencode-go"),
            )
        )
        evidence = RuntimeEvidence(auth_configured={"opencode-go": True})
        resolved = resolve_go_model(
            resource=resources["opencode-go"],
            discovery=discovery,
            evidence=evidence,
        )
        self.assertEqual("opencode-go/alpha-model", resolved.model_id)
        self.assertEqual("AVAILABLE", resolved.availability.state)

    def test_go_resolves_dynamically_with_provider_probe_available(self) -> None:
        resources = parse_agent_resources_section(_workspace_config())
        discovery = FixtureModelCatalogDiscovery(
            models=(
                ModelCatalogEntry("opencode-go/zeta-model", "opencode-go"),
                ModelCatalogEntry("opencode-go/alpha-model", "opencode-go"),
            ),
            provider_states={"opencode-go": "AVAILABLE"},
        )
        resolved = resolve_go_model(
            resource=resources["opencode-go"],
            discovery=discovery,
        )
        self.assertEqual("opencode-go/alpha-model", resolved.model_id)
        self.assertEqual("AVAILABLE", resolved.availability.state)

    def test_go_provider_not_found_is_auth_unconfigured(self) -> None:
        resources = parse_agent_resources_section(_workspace_config())
        discovery = FixtureModelCatalogDiscovery(
            models=(ModelCatalogEntry("opencode-go/deepseek-v4-flash", "opencode-go"),),
            provider_states={"opencode-go": "AUTH_UNCONFIGURED"},
        )
        resolved = resolve_go_model(
            resource=resources["opencode-go"],
            discovery=discovery,
        )
        self.assertIsNone(resolved.model_id)
        self.assertEqual("AUTH_UNCONFIGURED", resolved.availability.state)

    def test_go_unknown_provider_failure_is_not_selectable(self) -> None:
        resources = parse_agent_resources_section(_workspace_config())
        discovery = FixtureModelCatalogDiscovery(
            models=(ModelCatalogEntry("opencode-go/deepseek-v4-flash", "opencode-go"),),
            provider_states={"opencode-go": "UNKNOWN"},
        )
        resolved = resolve_go_model(
            resource=resources["opencode-go"],
            discovery=discovery,
        )
        self.assertIsNone(resolved.model_id)
        self.assertEqual("UNKNOWN", resolved.availability.state)
        self.assertFalse(resolved.availability.selectable)

    def test_go_candidate_filter_excludes_free_and_wrong_namespaces(self) -> None:
        free_entry = ModelCatalogEntry("opencode-go/demo-free", "opencode-go")
        go_entry = ModelCatalogEntry("opencode-go/deepseek-v4-flash", "opencode-go")
        opencode_entry = ModelCatalogEntry("opencode/demo-go", "opencode")
        lmstudio_entry = ModelCatalogEntry("lmstudio/some-go", "lmstudio")
        self.assertFalse(is_go_model_candidate(free_entry, provider_namespace="opencode-go"))
        self.assertTrue(is_go_model_candidate(go_entry, provider_namespace="opencode-go"))
        self.assertFalse(is_go_model_candidate(opencode_entry, provider_namespace="opencode-go"))
        self.assertFalse(is_go_model_candidate(lmstudio_entry, provider_namespace="opencode-go"))


class AvailabilityNormalizationTests(unittest.TestCase):
    def test_all_normalized_availability_states_are_supported(self) -> None:
        for state in sorted(AVAILABILITY_STATES):
            availability = normalize_availability(state)
            self.assertEqual(state, availability.state)

    def test_unknown_evidence_maps_to_unknown_and_is_not_selectable(self) -> None:
        availability = normalize_availability("probably-ready")
        self.assertEqual("UNKNOWN", availability.state)
        self.assertFalse(availability.selectable)

    def test_missing_evidence_maps_to_unknown(self) -> None:
        availability = normalize_availability(None)
        self.assertEqual("UNKNOWN", availability.state)
        self.assertFalse(availability.selectable)

    def test_provider_down_and_quota_states_are_not_selectable(self) -> None:
        for state in ("PROVIDER_DOWN", "QUOTA_EXHAUSTED", "BUSY", "COOLDOWN", "AUTH_FAILED"):
            availability = normalize_availability(state)
            self.assertFalse(availability.selectable, state)

    def test_capacity_exhausted_prevents_selection_for_free_pool(self) -> None:
        resources = parse_agent_resources_section(_workspace_config())
        discovery = FixtureModelCatalogDiscovery(
            models=(ModelCatalogEntry("opencode/alpha-free", "opencode"),)
        )
        evidence = RuntimeEvidence(capacity_in_use={"opencode-free": 1})
        resolved = resolve_free_model(
            resource=resources["opencode-free"],
            discovery=discovery,
            evidence=evidence,
        )
        self.assertEqual("CAPACITY_EXHAUSTED", resolved.availability.state)


class WorkspaceIntegrationTests(unittest.TestCase):
    def test_load_agent_resources_from_workspace_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_workspace(root, _workspace_config())
            resources = load_agent_resources(root / "workspace.config.json")
            self.assertIn("opencode-local", resources)

    def test_resource_diagnostics_redact_to_normalized_state_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_workspace(root, _workspace_config())
            _write_opencode(root)
            resources = load_agent_resources(root / "workspace.config.json")
            payload = json.loads(
                dumps_resource_diagnostics(
                    resources,
                    workspace_root=root,
                    discovery=FixtureModelCatalogDiscovery(models=()),
                )
            )
            serialized = json.dumps(payload)
            self.assertNotIn("token", serialized.lower())
            self.assertNotIn("secret", serialized.lower())
            states = {item["availability"] for item in payload["resources"]}
            self.assertIn("AUTH_UNCONFIGURED", states)
            self.assertIn("MODEL_UNAVAILABLE", states)


class OverlayAndSelectorResolutionTests(unittest.TestCase):
    def test_cloud_overlay_serializes_resolved_model_with_cloud_worker(self) -> None:
        model_id = "opencode/claude-free"
        content = build_opencode_model_config_content(model_id)
        overlay = validate_process_env_overlay({OPENCODE_CONFIG_CONTENT_ENV: content})
        parsed = json.loads(overlay[OPENCODE_CONFIG_CONTENT_ENV])
        self.assertEqual(model_id, parsed["model"])
        self.assertEqual(CLOUD_WORKER_NAME, parsed["default_agent"])
        self.assertEqual(model_id, parsed["agent"][CLOUD_WORKER_NAME]["model"])
        self.assertNotIn(LOCAL_WORKER_NAME, overlay[OPENCODE_CONFIG_CONTENT_ENV])
        self.assertNotIn("bonsai", overlay[OPENCODE_CONFIG_CONTENT_ENV].lower())

    def test_cloud_overlay_rejects_local_worker_selection(self) -> None:
        payload = json.dumps(
            {
                "model": "opencode/claude-free",
                "default_agent": LOCAL_WORKER_NAME,
                "agent": {LOCAL_WORKER_NAME: {"model": "opencode/claude-free"}},
            }
        )
        with self.assertRaises(AgentResourceError):
            validate_process_env_overlay({OPENCODE_CONFIG_CONTENT_ENV: payload})

    def test_cloud_overlay_rejects_arbitrary_extra_fields(self) -> None:
        payload = json.dumps(
            {
                "model": "opencode/claude-free",
                "default_agent": CLOUD_WORKER_NAME,
                "agent": {CLOUD_WORKER_NAME: {"model": "opencode/claude-free"}},
                "environment": {"FOO": "bar"},
            }
        )
        with self.assertRaises(AgentResourceError):
            validate_process_env_overlay({OPENCODE_CONFIG_CONTENT_ENV: payload})

    def test_overlay_rejects_secret_like_payloads(self) -> None:
        with self.assertRaises(AgentResourceError):
            validate_process_env_overlay({OPENCODE_CONFIG_CONTENT_ENV: '{"token":"secret"}'})

    def test_free_resource_selector_resolves_cloud_executor_with_overlay(self) -> None:
        config = _workspace_config()
        executors = parse_agents_registry(config)
        discovery = FixtureModelCatalogDiscovery(
            models=(ModelCatalogEntry("opencode/alpha-free", "opencode"),)
        )
        resolution = resolve_agent_run_selector(
            "opencode-free",
            workspace_root=Path("/workspace"),
            workspace_config=config,
            executors=executors,
            discovery=discovery,
        )
        self.assertEqual("opencode-free", resolution.resource_id)
        self.assertEqual("opencode-cloud", resolution.executor_id)
        self.assertIn(OPENCODE_CONFIG_CONTENT_ENV, resolution.env_overlay)
        parsed = json.loads(resolution.env_overlay[OPENCODE_CONFIG_CONTENT_ENV])
        self.assertEqual("opencode/alpha-free", parsed["model"])
        self.assertEqual(CLOUD_WORKER_NAME, parsed["default_agent"])
        self.assertEqual("opencode/alpha-free", parsed["agent"][CLOUD_WORKER_NAME]["model"])
        self.assertNotIn(LOCAL_WORKER_NAME, resolution.env_overlay[OPENCODE_CONFIG_CONTENT_ENV])
        self.assertNotIn(LOCAL_MODEL_ID, resolution.env_overlay[OPENCODE_CONFIG_CONTENT_ENV])

    def test_local_resource_selector_has_no_cloud_overlay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_opencode(root)
            config = _workspace_config()
            executors = parse_agents_registry(config)
            resolution = resolve_agent_run_selector(
                "opencode-local",
                workspace_root=root,
                workspace_config=config,
                executors=executors,
            )
            self.assertEqual("opencode-local", resolution.resource_id)
            self.assertEqual("opencode-local", resolution.executor_id)
            self.assertEqual({}, resolution.env_overlay)

    def test_legacy_executor_selector_skips_resource_overlay(self) -> None:
        config = _workspace_config()
        executors = parse_agents_registry(config)
        resolution = resolve_agent_run_selector(
            "codex",
            workspace_root=Path("/workspace"),
            workspace_config=config,
            executors=executors,
        )
        self.assertIsNone(resolution.resource_id)
        self.assertEqual("codex", resolution.executor_id)
        self.assertEqual({}, resolution.env_overlay)


class _CompletedProcess:
    def __init__(
        self,
        *,
        returncode: int = 0,
        stdout: bytes = b"",
        stderr: bytes = b"",
    ) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class OpencodeCliModelCatalogDiscoveryTests(unittest.TestCase):
    def test_list_models_parses_plaintext_catalog_lines(self) -> None:
        catalog = (
            b"opencode/big-pickle\n"
            b"opencode/ling-3.0-flash-fin-free\n"
            b"opencode/mimo-v2.5-free\n"
        )

        def fake_run(argv: list[str], **kwargs: object) -> _CompletedProcess:
            self.assertEqual(["opencode", "models"], argv)
            return _CompletedProcess(stdout=catalog)

        discovery = OpencodeCliModelCatalogDiscovery(subprocess_run=fake_run)
        models = discovery.list_models()
        self.assertEqual(
            [
                ("opencode/big-pickle", "opencode"),
                ("opencode/ling-3.0-flash-fin-free", "opencode"),
                ("opencode/mimo-v2.5-free", "opencode"),
            ],
            [(entry.model_id, entry.provider_namespace) for entry in models],
        )

    def test_list_models_discovers_free_entries_from_plaintext_catalog(self) -> None:
        catalog = (
            b"opencode/nemotron-3.5-lightning-free\n"
            b"opencode/paid-go\n"
            b"\n"
            b"not-a-model-line\n"
        )

        def fake_run(argv: list[str], **kwargs: object) -> _CompletedProcess:
            return _CompletedProcess(stdout=catalog)

        discovery = OpencodeCliModelCatalogDiscovery(subprocess_run=fake_run)
        resources = parse_agent_resources_section(_workspace_config())
        resolved = resolve_free_model(
            resource=resources["opencode-free"],
            discovery=discovery,
        )
        self.assertEqual("opencode/nemotron-3.5-lightning-free", resolved.model_id)
        self.assertEqual("AVAILABLE", resolved.availability.state)

    def test_list_models_ignores_empty_and_malformed_lines(self) -> None:
        catalog = b"\n  \nopencode/valid-free\nmissing-slash\n/opencode/leading-slash\n"

        def fake_run(argv: list[str], **kwargs: object) -> _CompletedProcess:
            return _CompletedProcess(stdout=catalog)

        discovery = OpencodeCliModelCatalogDiscovery(subprocess_run=fake_run)
        models = discovery.list_models()
        self.assertEqual(("opencode/valid-free", "opencode"), (models[0].model_id, models[0].provider_namespace))
        self.assertEqual(1, len(models))

    def test_list_models_does_not_request_json_format_flag(self) -> None:
        observed: list[list[str]] = []

        def fake_run(argv: list[str], **kwargs: object) -> _CompletedProcess:
            observed.append(list(argv))
            return _CompletedProcess(stdout=b"opencode/demo-free\n")

        discovery = OpencodeCliModelCatalogDiscovery(subprocess_run=fake_run)
        discovery.list_models()
        self.assertEqual([["opencode", "models"]], observed)
        joined = " ".join(observed[0])
        self.assertNotIn("--format", joined)
        self.assertNotIn("json", joined)

    def test_provider_probe_exit_zero_means_available(self) -> None:
        def fake_run(argv: list[str], **kwargs: object) -> _CompletedProcess:
            self.assertEqual(["opencode", "models", "opencode-go"], argv)
            return _CompletedProcess(stdout=b"opencode-go/deepseek-v4-flash\n")

        discovery = OpencodeCliModelCatalogDiscovery(subprocess_run=fake_run)
        self.assertEqual("AVAILABLE", discovery.get_provider_state("opencode-go"))

    def test_provider_probe_available_enables_go_dynamic_selection(self) -> None:
        resources = parse_agent_resources_section(_workspace_config())

        def fake_run(argv: list[str], **kwargs: object) -> _CompletedProcess:
            if argv == ["opencode", "models"]:
                return _CompletedProcess(
                    stdout=(
                        b"opencode/gpt-5-free\n"
                        b"opencode-go/deepseek-v4-flash\n"
                        b"opencode-go/glm-5.1\n"
                    )
                )
            if argv == ["opencode", "models", "opencode-go"]:
                return _CompletedProcess(stdout=b"opencode-go/deepseek-v4-flash\n")
            raise AssertionError(f"unexpected argv: {argv}")

        discovery = OpencodeCliModelCatalogDiscovery(subprocess_run=fake_run)
        resolved = resolve_go_model(
            resource=resources["opencode-go"],
            discovery=discovery,
        )
        self.assertEqual("opencode-go/deepseek-v4-flash", resolved.model_id)
        self.assertEqual("AVAILABLE", resolved.availability.state)

    def test_provider_unknown_failure_is_not_selectable(self) -> None:
        def fake_run(argv: list[str], **kwargs: object) -> _CompletedProcess:
            self.assertEqual(["opencode", "models", "opencode-go"], argv)
            return _CompletedProcess(returncode=1, stderr=b"unexpected upstream failure\n")

        discovery = OpencodeCliModelCatalogDiscovery(subprocess_run=fake_run)
        self.assertEqual("UNKNOWN", discovery.get_provider_state("opencode-go"))

    def test_provider_not_found_maps_to_auth_unconfigured_for_go(self) -> None:
        def fake_run(argv: list[str], **kwargs: object) -> _CompletedProcess:
            self.assertEqual(["opencode", "models", "opencode-go"], argv)
            return _CompletedProcess(
                returncode=1,
                stderr=b"Provider not found: opencode-go\n",
            )

        discovery = OpencodeCliModelCatalogDiscovery(subprocess_run=fake_run)
        self.assertEqual("AUTH_UNCONFIGURED", discovery.get_provider_state("opencode-go"))

    def test_provider_not_found_blocks_go_resolution_after_auth_evidence(self) -> None:
        resources = parse_agent_resources_section(_workspace_config())
        evidence = RuntimeEvidence(auth_configured={"opencode-go": True})

        def fake_run(argv: list[str], **kwargs: object) -> _CompletedProcess:
            if argv == ["opencode", "models"]:
                return _CompletedProcess(stdout=b"opencode-go/demo-go\n")
            if argv == ["opencode", "models", "opencode-go"]:
                return _CompletedProcess(
                    returncode=1,
                    stderr=b"Provider not found: opencode-go\n",
                )
            raise AssertionError(f"unexpected argv: {argv}")

        discovery = OpencodeCliModelCatalogDiscovery(subprocess_run=fake_run)
        resolved = resolve_go_model(
            resource=resources["opencode-go"],
            discovery=discovery,
            evidence=evidence,
        )
        self.assertIsNone(resolved.model_id)
        self.assertEqual("AUTH_UNCONFIGURED", resolved.availability.state)


if __name__ == "__main__":
    unittest.main()
