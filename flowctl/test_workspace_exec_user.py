from __future__ import annotations

from pathlib import Path

import pytest

from flowctl import stack
from flowctl.context import workspace_exec_user
from flowctl.tooling import capture_workspace_tool, command_repo_exec, run_workspace_tool


def test_compose_exec_args_with_user_emits_user_flag() -> None:
    args = stack.compose_exec_args("workspace", use_tty=False, workdir="/workspace", user="vscode")

    assert args == ["exec", "-T", "--user", "vscode", "-w", "/workspace", "workspace"]


def test_compose_exec_args_without_user_omits_user_flag() -> None:
    args = stack.compose_exec_args("api", use_tty=True, workdir="/workspace/projects/api")

    assert args == ["exec", "-w", "/workspace/projects/api", "api"]


def test_run_workspace_tool_passes_configured_workspace_user(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLOW_WORKSPACE_USER", "devuser")
    captured: list[dict[str, object]] = []

    def compose_exec_args(service, *, interactive=False, workdir=None, user=None):  # noqa: ANN001
        captured.append(
            {"service": service, "interactive": interactive, "workdir": workdir, "user": user}
        )
        return ["exec", service]

    rc = run_workspace_tool(
        ["python3", "./flow", "doctor"],
        run_compose=lambda args, interactive=None: 0,
        compose_exec_args=compose_exec_args,
        workspace_service="workspace",
        workspace_path="/workspace",
        workspace_exec_user=workspace_exec_user(),
    )

    assert rc == 0
    assert captured == [
        {
            "service": "workspace",
            "interactive": None,
            "workdir": "/workspace",
            "user": "devuser",
        }
    ]


def test_capture_workspace_tool_passes_default_workspace_user() -> None:
    captured: list[dict[str, object]] = []

    def compose_exec_args(service, *, interactive=False, workdir=None, user=None):  # noqa: ANN001
        captured.append(
            {"service": service, "interactive": interactive, "workdir": workdir, "user": user}
        )
        return ["exec", service]

    execution = capture_workspace_tool(
        ["tessl", "--help"],
        root=Path("/tmp"),
        running_inside_workspace=lambda: False,
        capture_command=lambda command, cwd: {"command": command, "cwd": str(cwd)},
        capture_compose=lambda args: {"command": args},
        compose_exec_args=compose_exec_args,
        workspace_service="workspace",
        workspace_path="/workspace",
        workspace_exec_user=workspace_exec_user(),
    )

    assert execution == {"command": ["exec", "workspace", "tessl", "--help"]}
    assert captured == [
        {
            "service": "workspace",
            "interactive": False,
            "workdir": "/workspace",
            "user": "vscode",
        }
    ]


def test_command_repo_exec_does_not_force_workspace_user_from_host() -> None:
    repo_dir = Path("/tmp/projects/api")
    captured: list[dict[str, object]] = []

    def compose_exec_args(service_name, interactive=False, workdir=None, user=None):  # noqa: ANN001
        captured.append(
            {
                "service": service_name,
                "interactive": interactive,
                "workdir": workdir,
                "user": user,
            }
        )
        return ["exec", service_name, workdir or ""]

    rc = command_repo_exec(
        type("Args", (), {"repo": "api", "workdir": "", "command": ["--", "vendor/bin/phpunit"]})(),
        normalize_passthrough=lambda args: args[1:] if args and args[0] == "--" else args,
        repo_root=lambda repo: repo_dir,
        repo_compose_service=lambda repo: "php-api",
        workspace_service="workspace",
        running_inside_workspace=lambda: False,
        runtime_path=lambda path: path,
        repo_container_workdir=lambda path: "/workspace/projects/api",
        run_local_tool_at_path=lambda tool_args, cwd: 0,
        run_compose=lambda args, interactive=None: 0,
        compose_exec_args=compose_exec_args,
    )

    assert rc == 0
    assert captured == [
        {
            "service": "php-api",
            "interactive": False,
            "workdir": "/workspace/projects/api",
            "user": None,
        }
    ]


def test_workspace_exec_user_defaults_to_vscode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FLOW_WORKSPACE_USER", raising=False)
    assert workspace_exec_user() == "vscode"


def test_workspace_exec_user_reads_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLOW_WORKSPACE_USER", "custom")
    assert workspace_exec_user() == "custom"
