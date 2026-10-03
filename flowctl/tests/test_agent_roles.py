from __future__ import annotations

import unittest
from unittest import mock

from flowctl.agent_executors import AgentExecutor
from flowctl.agent_executor_adapters import AgentRunRequest, build_execution_contract
from flowctl.agent_resources import (
    AgentResource,
    PREFERRED_ORDER_BY_WORK_CLASS,
    PREFERRED_ORDER_INDEPENDENT_REVIEW,
    WORK_CLASS_INDEPENDENT_REVIEW,
    preferred_order_for_work_class,
    select_resource_candidates,
)
from flowctl.agent_roles import (
    AgentRoleError,
    INDEPENDENT_REVIEW_PREFERRED_ORDER,
    ORCHESTRATOR_EXECUTOR_PRIORITY,
    ROLE_ORCHESTRATOR,
    ROLE_REVIEWER,
    ROLE_WORKER,
    normalize_role_context,
    resolve_invocation_role,
    select_orchestrator_executor,
    select_reviewer_candidates,
)


def _resource(
    resource_id: str,
    *,
    executor_id: str,
    model_resolution: str,
    cost_tier: str = "local",
    capabilities: frozenset[str] | None = None,
    data_sensitivity: str = "local-only",
    selection_priority: int = 10,
) -> AgentResource:
    return AgentResource(
        resource_id=resource_id,
        executor_id=executor_id,
        capabilities=capabilities
        or frozenset({"tool_calling", "write", "local_execution"}),
        capacity=1,
        cost_tier=cost_tier,
        selection_priority=selection_priority,
        model_resolution=model_resolution,
        data_sensitivity=data_sensitivity,
    )


def _reviewer_resources() -> dict[str, AgentResource]:
    return {
        "opencode-local": _resource(
            "opencode-local",
            executor_id="opencode-local",
            model_resolution="worker_profile",
            cost_tier="local",
            selection_priority=10,
        ),
        "opencode-free": _resource(
            "opencode-free",
            executor_id="opencode",
            model_resolution="dynamic_free",
            cost_tier="cloud/free",
            capabilities=frozenset({"tool_calling", "write", "cloud_execution"}),
            data_sensitivity="cloud-eligible",
            selection_priority=20,
        ),
        "opencode-go": _resource(
            "opencode-go",
            executor_id="opencode",
            model_resolution="dynamic_go",
            cost_tier="cloud/paid-low",
            capabilities=frozenset({"tool_calling", "write", "cloud_execution"}),
            data_sensitivity="cloud-eligible",
            selection_priority=30,
        ),
        "codex": _resource(
            "codex",
            executor_id="codex",
            model_resolution="worker_profile",
            cost_tier="local",
            selection_priority=40,
        ),
    }


class AgentRoleContextTests(unittest.TestCase):
    def test_standalone_run_defaults_to_orchestrator(self) -> None:
        context = normalize_role_context()
        self.assertEqual(ROLE_ORCHESTRATOR, context.role)
        self.assertEqual("standalone-orchestrator", context.run_id)
        self.assertIsNone(context.parent_run_id)

    def test_worker_requires_parent_and_handoff(self) -> None:
        with self.assertRaisesRegex(AgentRoleError, "parent_run_id"):
            normalize_role_context(role=ROLE_WORKER, run_id="worker-1", handoff_ref="handoff.json")
        with self.assertRaisesRegex(AgentRoleError, "handoff"):
            normalize_role_context(role=ROLE_WORKER, run_id="worker-1", parent_run_id="run-1")

    def test_reviewer_requires_parent_and_handoff(self) -> None:
        context = normalize_role_context(
            role=ROLE_REVIEWER,
            run_id="review-1",
            parent_run_id="run-1",
            handoff_ref="review.json",
        )
        self.assertEqual(ROLE_REVIEWER, context.role)

    def test_child_cannot_claim_orchestrator_parentage(self) -> None:
        with self.assertRaisesRegex(AgentRoleError, "no puede tener"):
            normalize_role_context(
                role=ROLE_ORCHESTRATOR,
                run_id="nested-orchestrator",
                parent_run_id="run-1",
            )

    def test_nested_invocation_defaults_to_worker(self) -> None:
        context = resolve_invocation_role(
            environ={"SOFTOS_AGENT_RUN_ID": "orchestrator-1"},
            handoff_ref="handoff.json",
        )
        self.assertEqual(ROLE_WORKER, context.role)
        self.assertEqual("orchestrator-1", context.parent_run_id)
        self.assertTrue(context.run_id.startswith("orchestrator-1:child:"))

    def test_nested_invocation_cannot_escalate(self) -> None:
        with self.assertRaisesRegex(AgentRoleError, "no puede elevarse"):
            resolve_invocation_role(
                role=ROLE_ORCHESTRATOR,
                environ={"SOFTOS_AGENT_RUN_ID": "worker-1"},
            )

    def test_contract_changes_authority_by_role(self) -> None:
        executor = AgentExecutor("codex", "codex", "codex", ())
        worker = build_execution_contract(
            request=AgentRunRequest(
                executor=executor,
                repo="root",
                workspace_root="/workspace",
                workdir="/workspace/.worktrees/child",
                targets=("flowctl/example.py",),
                user_prompt="work",
                contract_body="",
                role=ROLE_WORKER,
                run_id="worker-1",
                parent_run_id="run-1",
                handoff_ref="handoff.json",
            )
        )
        orchestrator = build_execution_contract(
            request=AgentRunRequest(
                executor=executor,
                repo="root",
                workspace_root="/workspace",
                workdir="/workspace",
                targets=("specs/features/example.spec.md",),
                user_prompt="orchestrate",
                contract_body="",
            )
        )
        self.assertIn("role: worker", worker)
        self.assertIn("parent_run_id: run-1", worker)
        self.assertIn("run BMAD/workflow orchestration", worker)
        self.assertIn("role: orchestrator", orchestrator)
        self.assertIn("use BMAD/flow lifecycle commands", orchestrator)


class OrchestratorSelectionTests(unittest.TestCase):
    def test_antigravity_absent_from_orchestrator_priority_until_admitted(self) -> None:
        # RB5 documented block: no dedicated adapter / registry entry yet.
        self.assertNotIn("antigravity", ORCHESTRATOR_EXECUTOR_PRIORITY)

    def test_selects_first_available_executor_after_filtering(self) -> None:
        executors = {
            "codex": AgentExecutor("codex", "codex", "codex", ()),
            "cursor": AgentExecutor("cursor", "cursor", "agent", ()),
            "opencode": AgentExecutor("opencode", "opencode", "opencode", ()),
        }
        statuses = {"codex": "missing", "agent": "ready", "opencode": "ready"}
        selected, payload = select_orchestrator_executor(
            executors,
            executable_status=lambda executable: statuses[executable],
        )
        self.assertEqual("cursor", selected.executor_id)
        self.assertEqual("cursor", payload["selected"])
        self.assertEqual("capability_priority_after_executable_filter", payload["selection_basis"])

    def test_selection_fails_closed_when_no_executor_is_ready(self) -> None:
        executors = {
            "codex": AgentExecutor("codex", "codex", "codex", ()),
        }
        with self.assertRaisesRegex(AgentRoleError, "No hay un executor disponible"):
            select_orchestrator_executor(
                executors,
                executable_status=lambda _executable: "missing",
            )


class IndependentReviewerSelectionTests(unittest.TestCase):
    def test_rb1_independent_review_table_matches_resource_policy(self) -> None:
        self.assertEqual(
            PREFERRED_ORDER_INDEPENDENT_REVIEW,
            preferred_order_for_work_class(WORK_CLASS_INDEPENDENT_REVIEW),
        )
        self.assertEqual(
            PREFERRED_ORDER_BY_WORK_CLASS[WORK_CLASS_INDEPENDENT_REVIEW],
            INDEPENDENT_REVIEW_PREFERRED_ORDER,
        )

    def test_same_executor_as_implementer_is_blocked(self) -> None:
        resources = _reviewer_resources()
        availability = {resource_id: "AVAILABLE" for resource_id in resources}
        candidates, payload = select_reviewer_candidates(
            resources,
            availability=availability,
            implementer_executor="opencode-local",
            implementer_model_resolution="worker_profile",
        )
        self.assertNotIn("opencode-local", candidates)
        excluded_reasons = {
            item["id"]: item["reason"] for item in payload["excluded"]  # type: ignore[index]
        }
        self.assertEqual("same_executor_as_implementer", excluded_reasons["opencode-local"])

    def test_same_model_resolution_excluded_other_family_preferred(self) -> None:
        resources = _reviewer_resources()
        availability = {resource_id: "AVAILABLE" for resource_id in resources}
        candidates, payload = select_reviewer_candidates(
            resources,
            availability=availability,
            implementer_executor="opencode-local",
            implementer_model_resolution="worker_profile",
            preferred_order=PREFERRED_ORDER_INDEPENDENT_REVIEW,
        )
        self.assertNotIn("opencode-local", candidates)
        # Same model_resolution family already excluded; cloud/free preferred over local.
        self.assertEqual("opencode-free", payload["selected"])
        self.assertEqual(
            "capability_filter_then_preferred_order_with_implementer_exclusion",
            payload["selection_basis"],
        )
        self.assertTrue(candidates)
        self.assertEqual("cloud/free", resources[candidates[0]].cost_tier)

    def test_reviewer_consumes_declared_independent_review_chain(self) -> None:
        resources = _reviewer_resources()
        availability = {resource_id: "AVAILABLE" for resource_id in resources}
        _, resource_payload = select_resource_candidates(
            resources,
            availability=availability,
            work_class=WORK_CLASS_INDEPENDENT_REVIEW,
        )
        self.assertEqual(
            list(PREFERRED_ORDER_INDEPENDENT_REVIEW),
            resource_payload["preferred_order"],
        )
        candidates, payload = select_reviewer_candidates(
            resources,
            availability=availability,
            implementer_executor="opencode-local",
            implementer_model_resolution="worker_profile",
            preferred_order=preferred_order_for_work_class(WORK_CLASS_INDEPENDENT_REVIEW),
        )
        self.assertEqual("opencode-free", payload["selected"])
        self.assertNotIn("opencode-local", candidates)
        self.assertEqual(
            "capability_filter_then_preferred_order_with_implementer_exclusion",
            payload["selection_basis"],
        )

    def test_reviewer_selection_routes_through_select_resource_candidates(self) -> None:
        resources = _reviewer_resources()
        availability = {resource_id: "AVAILABLE" for resource_id in resources}
        with mock.patch(
            "flowctl.agent_roles.select_resource_candidates",
            wraps=select_resource_candidates,
        ) as wrapped:
            candidates, payload = select_reviewer_candidates(
                resources,
                availability=availability,
                implementer_executor="opencode-local",
                implementer_model_resolution="worker_profile",
            )
        wrapped.assert_called_once()
        self.assertEqual(
            WORK_CLASS_INDEPENDENT_REVIEW,
            wrapped.call_args.kwargs["work_class"],
        )
        self.assertEqual("opencode-free", payload["selected"])
        self.assertNotIn("opencode-local", candidates)
        # Implementer identity exclusion happens before the shared wrapper.
        called_resources = wrapped.call_args.args[0]
        self.assertNotIn("opencode-local", called_resources)

    def test_no_independent_candidate_raises_with_skip_reasons(self) -> None:
        resources = {
            "opencode-local": _resource(
                "opencode-local",
                executor_id="opencode-local",
                model_resolution="worker_profile",
            ),
            "opencode-free": _resource(
                "opencode-free",
                executor_id="opencode",
                model_resolution="worker_profile",
                cost_tier="cloud/free",
                capabilities=frozenset({"tool_calling", "write", "cloud_execution"}),
                data_sensitivity="cloud-eligible",
            ),
        }
        availability = {resource_id: "AVAILABLE" for resource_id in resources}
        with self.assertRaises(AgentRoleError) as ctx:
            select_reviewer_candidates(
                resources,
                availability=availability,
                implementer_executor="opencode-local",
                implementer_model_resolution="worker_profile",
            )
        self.assertTrue(ctx.exception.skip_reasons)
        reasons = {item["id"]: item["reason"] for item in ctx.exception.skip_reasons}
        self.assertEqual("same_executor_as_implementer", reasons["opencode-local"])
        self.assertEqual("same_model_resolution_as_implementer", reasons["opencode-free"])
