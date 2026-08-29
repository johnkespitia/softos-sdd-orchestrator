from __future__ import annotations

import json
import stat
import tempfile
import unittest
from pathlib import Path

from flowctl.agent_executors import (
    AgentRegistryError,
    command_agent_doctor,
    command_agent_list,
    load_agent_registry,
    parse_agents_registry,
)


def _write_config(root: Path, agents: object, *, project: bool = True) -> Path:
    payload: dict[str, object] = {}
    if project:
        payload = {
            "project": {"display_name": "Test", "root_repo": "softos-agentic"},
            "repos": {"softos-agentic": {"path": ".", "kind": "root"}},
        }
    payload["agents"] = agents
    path = root / "workspace.config.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class AgentRegistryValidationTests(unittest.TestCase):
    def test_valid_registry_parses_three_executors(self) -> None:
        registry = parse_agents_registry(
            {
                "agents": {
                    "schema_version": 1,
                    "executors": {
                        "cursor": {"adapter": "cursor", "executable": "agent", "argv": []},
                        "codex": {"adapter": "codex", "executable": "codex", "argv": []},
                        "opencode-local": {"adapter": "opencode", "executable": "opencode", "argv": []},
                    },
                }
            }
        )
        self.assertEqual(["codex", "cursor", "opencode-local"], list(registry))

    def test_missing_agents_section_fails(self) -> None:
        with self.assertRaises(AgentRegistryError):
            parse_agents_registry({"project": {}})

    def test_invalid_schema_version_fails(self) -> None:
        with self.assertRaisesRegex(AgentRegistryError, "schema_version"):
            parse_agents_registry({"agents": {"schema_version": 2, "executors": {"codex": {"adapter": "codex", "executable": "codex", "argv": []}}}})

    def test_schema_version_rejects_non_integer_types(self) -> None:
        invalid_values = [True, False, "1", 1.0, None, [], {}]
        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaisesRegex(AgentRegistryError, "schema_version"):
                    parse_agents_registry(
                        {
                            "agents": {
                                "schema_version": value,
                                "executors": {"codex": {"adapter": "codex", "executable": "codex", "argv": []}},
                            }
                        }
                    )

    def test_absolute_executable_path_is_accepted(self) -> None:
        registry = parse_agents_registry(
            {
                "agents": {
                    "schema_version": 1,
                    "executors": {
                        "codex": {"adapter": "codex", "executable": "/usr/local/bin/codex", "argv": []},
                    },
                }
            }
        )
        self.assertEqual("/usr/local/bin/codex", registry["codex"].executable)

    def test_relative_executable_paths_fail(self) -> None:
        invalid_executables = ["bin/codex", "./codex", "../codex"]
        for executable in invalid_executables:
            with self.subTest(executable=executable):
                with self.assertRaisesRegex(AgentRegistryError, "ruta absoluta"):
                    parse_agents_registry(
                        {
                            "agents": {
                                "schema_version": 1,
                                "executors": {"codex": {"adapter": "codex", "executable": executable, "argv": []}},
                            }
                        }
                    )

    def test_empty_executors_fails(self) -> None:
        with self.assertRaisesRegex(AgentRegistryError, "executors"):
            parse_agents_registry({"agents": {"schema_version": 1, "executors": {}}})

    def test_invalid_executor_id_fails(self) -> None:
        with self.assertRaisesRegex(AgentRegistryError, "ID de executor invalido"):
            parse_agents_registry(
                {
                    "agents": {
                        "schema_version": 1,
                        "executors": {"Bad_ID": {"adapter": "codex", "executable": "codex", "argv": []}},
                    }
                }
            )

    def test_unsupported_adapter_fails(self) -> None:
        with self.assertRaisesRegex(AgentRegistryError, "no soportado"):
            parse_agents_registry(
                {
                    "agents": {
                        "schema_version": 1,
                        "executors": {"codex": {"adapter": "unknown", "executable": "codex", "argv": []}},
                    }
                }
            )

    def test_unknown_executor_field_fails(self) -> None:
        with self.assertRaisesRegex(AgentRegistryError, "Campo desconocido"):
            parse_agents_registry(
                {
                    "agents": {
                        "schema_version": 1,
                        "executors": {"codex": {"adapter": "codex", "executable": "codex", "argv": [], "model": "gpt-4"}},
                    }
                }
            )

    def test_duplicate_json_keys_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "workspace.config.json"
            path.write_text(
                '{"agents": {"schema_version": 1, "executors": {"codex": {"adapter": "codex", "executable": "codex", "argv": []}}}, '
                '"agents": {"schema_version": 1, "executors": {}}}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(AgentRegistryError, "duplicada"):
                load_agent_registry(path)


class AgentListTests(unittest.TestCase):
    def test_list_returns_lexical_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _write_config(
                root,
                {
                    "schema_version": 1,
                    "executors": {
                        "cursor": {"adapter": "cursor", "executable": "agent", "argv": []},
                        "codex": {"adapter": "codex", "executable": "codex", "argv": []},
                        "opencode-local": {"adapter": "opencode", "executable": "opencode", "argv": []},
                    },
                },
            )
            from io import StringIO
            import sys

            buffer = StringIO()
            stdout = sys.stdout
            sys.stdout = buffer
            try:
                rc = command_agent_list(
                    argparse_namespace(json=False),
                    workspace_config_file=config,
                    json_dumps=json.dumps,
                )
            finally:
                sys.stdout = stdout

            self.assertEqual(0, rc)
            lines = [line for line in buffer.getvalue().splitlines() if line.strip()]
            self.assertEqual(
                [
                    "codex\tadapter=codex\texecutable=codex",
                    "cursor\tadapter=cursor\texecutable=agent",
                    "opencode-local\tadapter=opencode\texecutable=opencode",
                ],
                lines,
            )


class AgentDoctorTests(unittest.TestCase):
    def test_doctor_reports_ready_with_fake_path_executables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            for name in ("codex", "agent", "opencode"):
                path = bin_dir / name
                path.write_text("#!/bin/sh\n", encoding="utf-8")
                path.chmod(path.stat().st_mode | stat.S_IXUSR)

            config = _write_config(
                root,
                {
                    "schema_version": 1,
                    "executors": {
                        "codex": {"adapter": "codex", "executable": str(bin_dir / "codex"), "argv": []},
                        "cursor": {"adapter": "cursor", "executable": str(bin_dir / "agent"), "argv": []},
                        "opencode-local": {"adapter": "opencode", "executable": str(bin_dir / "opencode"), "argv": []},
                    },
                },
            )

            rc = command_agent_doctor(
                argparse_namespace(json=False, executor=None),
                workspace_config_file=config,
                shutil_which=lambda _: None,
                json_dumps=json.dumps,
            )
            self.assertEqual(0, rc)

    def test_doctor_reports_missing_executable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _write_config(
                root,
                {
                    "schema_version": 1,
                    "executors": {
                        "codex": {"adapter": "codex", "executable": "missing-codex-cli", "argv": []},
                    },
                },
            )
            rc = command_agent_doctor(
                argparse_namespace(json=False, executor=None),
                workspace_config_file=config,
                shutil_which=lambda _: None,
                json_dumps=json.dumps,
            )
            self.assertEqual(1, rc)

    def test_doctor_unknown_executor_exits_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _write_config(
                root,
                {
                    "schema_version": 1,
                    "executors": {
                        "codex": {"adapter": "codex", "executable": "codex", "argv": []},
                    },
                },
            )
            with self.assertRaises(SystemExit):
                command_agent_doctor(
                    argparse_namespace(json=False, executor="missing"),
                    workspace_config_file=config,
                    shutil_which=lambda _: None,
                    json_dumps=json.dumps,
                )


def argparse_namespace(**kwargs: object) -> object:
    class Namespace:
        pass

    ns = Namespace()
    for key, value in kwargs.items():
        setattr(ns, key, value)
    return ns


if __name__ == "__main__":
    unittest.main()
