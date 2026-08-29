from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

from flowctl.tooling import HOST_EXECUTION_BLOCK_MESSAGE, enforce_workspace_only_host


class AgentHostRoutingTests(unittest.TestCase):
    def test_agent_family_allowed_on_host(self) -> None:
        for args in (["agent", "list"], ["agent", "doctor"], ["agent", "doctor", "codex"], ["agent", "run", "codex"]):
            with self.subTest(args=args):
                enforce_workspace_only_host(
                    args,
                    running_inside_workspace=False,
                    force_workspace_exec=True,
                    skip_delegation=False,
                    github_actions=False,
                )

    def test_non_agent_commands_blocked_on_host(self) -> None:
        for args in (["doctor"], ["ci", "spec", "--all"], ["workflow", "doctor"]):
            with self.subTest(args=args):
                with self.assertRaises(SystemExit) as ctx:
                    enforce_workspace_only_host(
                        args,
                        running_inside_workspace=False,
                        force_workspace_exec=True,
                        skip_delegation=False,
                        github_actions=False,
                    )
                self.assertIn(HOST_EXECUTION_BLOCK_MESSAGE, str(ctx.exception))

    def test_stack_and_workspace_exec_remain_allowed(self) -> None:
        enforce_workspace_only_host(
            ["stack", "ps"],
            running_inside_workspace=False,
            force_workspace_exec=True,
            skip_delegation=False,
            github_actions=False,
        )
        enforce_workspace_only_host(
            ["workspace", "exec", "--", "python3", "./flow", "doctor"],
            running_inside_workspace=False,
            force_workspace_exec=True,
            skip_delegation=False,
            github_actions=False,
        )

    def test_flow_agent_list_runs_on_host_without_container(self) -> None:
        root = Path(__file__).resolve().parents[2]
        env = {
            **dict(__import__("os").environ),
            "FLOW_FORCE_WORKSPACE_EXEC": "1",
            "FLOW_WORKSPACE_PATH": "/definitely-not-this-worktree",
        }
        env.pop("GITHUB_ACTIONS", None)
        completed = subprocess.run(
            ["python3", str(root / "flow"), "agent", "list"],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertIn("codex", completed.stdout)
        self.assertIn("cursor", completed.stdout)
        self.assertIn("opencode-local", completed.stdout)

    def test_flow_doctor_blocked_on_host(self) -> None:
        root = Path(__file__).resolve().parents[2]
        env = {
            **dict(__import__("os").environ),
            "FLOW_FORCE_WORKSPACE_EXEC": "1",
            "FLOW_WORKSPACE_PATH": "/definitely-not-this-worktree",
        }
        env.pop("GITHUB_ACTIONS", None)
        completed = subprocess.run(
            ["python3", str(root / "flow"), "doctor"],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(0, completed.returncode)
        self.assertIn(HOST_EXECUTION_BLOCK_MESSAGE, completed.stderr)


if __name__ == "__main__":
    unittest.main()
