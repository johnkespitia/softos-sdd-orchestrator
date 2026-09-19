from __future__ import annotations

import unittest

from flowctl.agent_executors import AgentExecutor
from flowctl.agent_executor_adapters import AgentRunRequest, build_execution_contract
from flowctl.agent_roles import (
    AgentRoleError,
    ROLE_ORCHESTRATOR,
    ROLE_REVIEWER,
    ROLE_WORKER,
    normalize_role_context,
    resolve_invocation_role,
    select_orchestrator_executor,
)


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
