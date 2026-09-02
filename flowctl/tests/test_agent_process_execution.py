from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from flowctl.agent_executors import AgentRegistryError, command_agent_run, load_agent_registry
from flowctl.agent_process_execution import (
    AgentRunError,
    AgentRunMetadata,
    execute_subprocess,
    prepare_agent_run,
    resolve_target_within_workdir,
    run_agent_process,
    validate_workdir,
)
from flowctl.agent_executor_adapters import (
    EXECUTION_CONTRACT_BEGIN,
    AgentAdapterInvocation,
    AgentRunRequest,
    GenericStdinAdapter,
    build_execution_contract,
)
from flowctl.agent_executors import AgentExecutor
from flowctl.tooling import HOST_EXECUTION_BLOCK_MESSAGE


def _write_config(root: Path, *, agents: object | None = None, repos: object | None = None) -> Path:
    payload: dict[str, object] = {
        "project": {"display_name": "Test", "root_repo": "softos-agentic"},
        "repos": repos
        or {
            "softos-agentic": {"path": ".", "kind": "root"},
        },
    }
    if agents is not None:
        payload["agents"] = agents
    path = root / "workspace.config.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_fake_executor(path: Path) -> None:
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "if len(sys.argv) > 1 and sys.argv[1].isdigit():\n"
        "    code = int(sys.argv[1])\n"
        "else:\n"
        "    code = 0\n"
        "sys.stdout.write('FAKE_STDOUT')\n"
        "sys.stderr.write('FAKE_STDERR')\n"
        "if not sys.stdin.isatty():\n"
        "    sys.stdin.read()\n"
        "raise SystemExit(code)\n",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=path, capture_output=True, check=True)
    subprocess.run(
        ["git", "-C", str(path), "config", "user.email", "agent-test@softos.test"],
        check=True,
    )
    subprocess.run(["git", "-C", str(path), "config", "user.name", "agent-test"], check=True)
    subprocess.run(
        ["git", "-C", str(path), "commit", "--allow-empty", "-m", "init"],
        capture_output=True,
        check=True,
    )


def _add_git_worktree(repo_root: Path, worktree_path: Path, branch: str = "demo/test") -> None:
    worktree_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "worktree",
            "add",
            "-b",
            branch,
            str(worktree_path),
        ],
        capture_output=True,
        check=True,
    )


class PathContainmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        _init_git_repo(self.root)
        self.worktree_root = self.root / ".worktrees"
        self.worktree = self.worktree_root / "softos-agentic-demo-slice"
        _add_git_worktree(self.root, self.worktree)
        (self.worktree / "allowed.txt").write_text("ok", encoding="utf-8")

    def tearDown(self) -> None:
        subprocess.run(
            ["git", "-C", str(self.root), "worktree", "remove", "--force", str(self.worktree)],
            capture_output=True,
            check=False,
        )
        self.tmp.cleanup()

    def test_valid_repo_root_and_worktree_are_accepted(self) -> None:
        validate_workdir(
            str(self.root),
            workspace_root=self.root,
            repo_root_path=self.root,
        )
        validate_workdir(
            str(self.worktree),
            workspace_root=self.root,
            repo_root_path=self.root,
        )

    def test_fake_worktree_directory_is_rejected(self) -> None:
        fake = self.worktree_root / "softos-agentic-fake-slice"
        fake.mkdir(parents=True)
        with self.assertRaisesRegex(AgentRunError, "worktree reconocido"):
            validate_workdir(
                str(fake),
                workspace_root=self.root,
                repo_root_path=self.root,
            )

    def test_nested_directory_inside_worktree_is_rejected(self) -> None:
        nested = self.worktree / "nested"
        nested.mkdir()
        with self.assertRaisesRegex(AgentRunError, "worktree reconocido"):
            validate_workdir(
                str(nested),
                workspace_root=self.root,
                repo_root_path=self.root,
            )

    def test_target_inside_worktree_is_accepted(self) -> None:
        relative = resolve_target_within_workdir(self.worktree, "allowed.txt")
        self.assertEqual("allowed.txt", relative)

    def test_prospective_target_inside_worktree_is_accepted(self) -> None:
        relative = resolve_target_within_workdir(self.worktree, "future/nested/file.py")
        self.assertEqual("future/nested/file.py", relative)

    def test_absolute_target_is_rejected_even_inside_workdir(self) -> None:
        absolute = str((self.worktree / "allowed.txt").resolve())
        with self.assertRaisesRegex(AgentRunError, "fuera de limites"):
            resolve_target_within_workdir(self.worktree, absolute)

    def test_target_outside_worktree_is_rejected(self) -> None:
        outside = self.root / "outside.txt"
        outside.write_text("nope", encoding="utf-8")
        with self.assertRaisesRegex(AgentRunError, "fuera de limites"):
            resolve_target_within_workdir(self.worktree, "../outside.txt")

    def test_parent_traversal_target_is_rejected(self) -> None:
        with self.assertRaisesRegex(AgentRunError, "fuera de limites"):
            resolve_target_within_workdir(self.worktree, "../outside.txt")

    def test_symlink_escape_is_rejected(self) -> None:
        outside = self.root / "secret.txt"
        outside.write_text("secret", encoding="utf-8")
        link = self.worktree / "escape-link"
        link.symlink_to(outside)
        with self.assertRaisesRegex(AgentRunError, "fuera de limites"):
            resolve_target_within_workdir(self.worktree, "escape-link")

    def test_prospective_path_beneath_symlink_escape_is_rejected(self) -> None:
        outside = self.root / "secret.txt"
        outside.write_text("secret", encoding="utf-8")
        link = self.worktree / "escape-link"
        link.symlink_to(outside)
        with self.assertRaisesRegex(AgentRunError, "fuera de limites"):
            resolve_target_within_workdir(self.worktree, "escape-link/nested.py")

    def test_dangling_symlink_escape_is_rejected(self) -> None:
        outside = self.root / "missing-outside.txt"
        link = self.worktree / "dangling-escape"
        link.symlink_to(outside)
        with self.assertRaisesRegex(AgentRunError, "fuera de limites"):
            resolve_target_within_workdir(self.worktree, "dangling-escape")

    def test_chained_symlink_to_external_existing_target_is_rejected(self) -> None:
        outside = self.root / "secret.txt"
        outside.write_text("secret", encoding="utf-8")
        link_b = self.worktree / "link-b"
        link_b.symlink_to(outside)
        link_a = self.worktree / "link-a"
        link_a.symlink_to("link-b")
        with self.assertRaisesRegex(AgentRunError, "fuera de limites"):
            resolve_target_within_workdir(self.worktree, "link-a")

    def test_chained_symlink_to_external_dangling_target_is_rejected(self) -> None:
        outside = self.root / "missing-outside.txt"
        link_b = self.worktree / "link-b"
        link_b.symlink_to(outside)
        link_a = self.worktree / "link-a"
        link_a.symlink_to("link-b")
        with self.assertRaisesRegex(AgentRunError, "fuera de limites"):
            resolve_target_within_workdir(self.worktree, "link-a")

    def test_prospective_path_beneath_chained_escaping_symlink_is_rejected(self) -> None:
        outside = self.root / "secret.txt"
        outside.write_text("secret", encoding="utf-8")
        link_b = self.worktree / "link-b"
        link_b.symlink_to(outside)
        link_a = self.worktree / "link-a"
        link_a.symlink_to("link-b")
        with self.assertRaisesRegex(AgentRunError, "fuera de limites"):
            resolve_target_within_workdir(self.worktree, "link-a/nested.py")

    def test_repo_worktree_mismatch_is_rejected(self) -> None:
        backend_root = self.root / "backend"
        backend_root.mkdir()
        _init_git_repo(backend_root)
        other_worktree = self.worktree_root / "backend-demo-slice"
        _add_git_worktree(backend_root, other_worktree, branch="demo/backend")
        with self.assertRaisesRegex(AgentRunError, "worktree reconocido"):
            validate_workdir(
                str(other_worktree),
                workspace_root=self.root,
                repo_root_path=self.root,
            )
        subprocess.run(
            ["git", "-C", str(backend_root), "worktree", "remove", "--force", str(other_worktree)],
            capture_output=True,
            check=False,
        )


class SubprocessExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.fake = self.root / "fake-agent"
        _write_fake_executor(self.fake)
        self.test_adapter = GenericStdinAdapter(adapter_name="test")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_argv_invocation_uses_shell_false(self) -> None:
        captured: dict[str, object] = {}

        def fake_run(**kwargs: object) -> object:
            captured.update(kwargs)
            return subprocess.CompletedProcess(args=kwargs["args"], returncode=0, stdout=b"", stderr=b"")

        execute_subprocess(
            AgentAdapterInvocation(argv=(str(self.fake), "0"), stdin="prompt"),
            cwd=self.root,
            subprocess_run=fake_run,
        )
        self.assertEqual(list(captured["args"]), [str(self.fake), "0"])
        self.assertIs(captured["shell"], False)
        self.assertEqual(b"prompt", captured["input"])

    def test_stdout_and_stderr_are_captured_without_extra_newlines(self) -> None:
        streams: dict[str, bytes] = {}

        def writer(stream: str, payload: bytes) -> None:
            streams[stream] = payload

        executor = AgentExecutor(
            executor_id="test",
            adapter="test",
            executable=str(self.fake),
            argv=("0",),
        )
        with mock.patch(
            "flowctl.agent_process_execution.resolve_adapter",
            return_value=self.test_adapter,
        ):
            exit_code, _metadata = run_agent_process(
                executor=executor,
                repo="softos-agentic",
                workspace_root=self.root,
                workdir=self.root,
                targets=("allowed.txt",),
                prompt="operator prompt",
                shutil_which=lambda _: None,
                subprocess_run=subprocess.run,
                stream_writer=writer,
            )
        self.assertEqual(0, exit_code)
        self.assertEqual(b"FAKE_STDOUT", streams["stdout"])
        self.assertEqual(b"FAKE_STDERR", streams["stderr"])

    def test_child_exit_code_is_propagated_exactly(self) -> None:
        for expected in (0, 1, 37):
            with self.subTest(expected=expected):
                with mock.patch(
                    "flowctl.agent_process_execution.resolve_adapter",
                    return_value=GenericStdinAdapter(adapter_name="test"),
                ):
                    exit_code, _metadata = run_agent_process(
                        executor=AgentExecutor(
                            executor_id="test",
                            adapter="test",
                            executable=str(self.fake),
                            argv=(str(expected),),
                        ),
                        repo="softos-agentic",
                        workspace_root=self.root,
                        workdir=self.root,
                        targets=("allowed.txt",),
                        prompt="operator prompt",
                        shutil_which=lambda _: None,
                        subprocess_run=subprocess.run,
                    )
                self.assertEqual(expected, exit_code)

    def test_invalid_utf8_child_output_preserves_exact_bytes_and_exit_code(self) -> None:
        noisy = self.root / "noisy-agent"
        noisy.write_bytes(
            b"#!/usr/bin/env python3\n"
            b"import sys\n"
            b"sys.stdout.buffer.write(b'\\xff\\xfe')\n"
            b"raise SystemExit(17)\n"
        )
        noisy.chmod(noisy.stat().st_mode | stat.S_IXUSR)
        executor = AgentExecutor(
            executor_id="test",
            adapter="test",
            executable=str(noisy),
            argv=(),
        )
        streams: dict[str, bytes] = {}

        def writer(stream: str, payload: bytes) -> None:
            streams[stream] = payload

        with mock.patch(
            "flowctl.agent_process_execution.resolve_adapter",
            return_value=self.test_adapter,
        ):
            exit_code, _metadata = run_agent_process(
                executor=executor,
                repo="softos-agentic",
                workspace_root=self.root,
                workdir=self.root,
                targets=("allowed.txt",),
                prompt="operator prompt",
                shutil_which=lambda _: None,
                subprocess_run=subprocess.run,
                stream_writer=writer,
            )
        self.assertEqual(17, exit_code)
        self.assertEqual(b"\xff\xfe", streams["stdout"])

    def test_process_creation_failure_is_deterministic(self) -> None:
        executor = AgentExecutor(
            executor_id="test",
            adapter="test",
            executable=str(self.fake),
            argv=(),
        )

        def failing_run(**kwargs: object) -> object:
            raise FileNotFoundError("vanished")

        with mock.patch(
            "flowctl.agent_process_execution.resolve_adapter",
            return_value=self.test_adapter,
        ):
            with self.assertRaisesRegex(AgentRunError, "fallo al crear el proceso hijo"):
                run_agent_process(
                    executor=executor,
                    repo="softos-agentic",
                    workspace_root=self.root,
                    workdir=self.root,
                    targets=("allowed.txt",),
                    prompt="operator prompt",
                    shutil_which=lambda _: str(self.fake),
                    subprocess_run=failing_run,
                )

    def test_missing_executable_after_readiness_check_is_deterministic(self) -> None:
        secret_prompt = "SUPER_SECRET_PROMPT_TOKEN"
        secret_env = "SUPER_SECRET_ENV_TOKEN"
        secret_argv = "SUPER_SECRET_ARGV_TOKEN"
        executor = AgentExecutor(
            executor_id="test",
            adapter="test",
            executable=str(self.fake),
            argv=(secret_argv,),
        )

        def failing_run(**kwargs: object) -> object:
            raise FileNotFoundError("vanished")

        with mock.patch(
            "flowctl.agent_process_execution.resolve_adapter",
            return_value=self.test_adapter,
        ):
            with mock.patch.dict(os.environ, {"TEST_AGENT_SECRET": secret_env}, clear=False):
                with self.assertRaises(AgentRunError) as ctx:
                    run_agent_process(
                        executor=executor,
                        repo="softos-agentic",
                        workspace_root=self.root,
                        workdir=self.root,
                        targets=("allowed.txt",),
                        prompt=secret_prompt,
                        shutil_which=lambda _: None,
                        subprocess_run=failing_run,
                    )
        diagnostic = str(ctx.exception)
        self.assertIn("fallo al crear el proceso hijo", diagnostic)
        self.assertNotIn("no esta disponible", diagnostic)
        self.assertNotIn(secret_prompt, diagnostic)
        self.assertNotIn(secret_env, diagnostic)
        self.assertNotIn(secret_argv, diagnostic)


class ExecutionContractTests(unittest.TestCase):
    def test_contract_contains_required_fields_and_sorted_targets(self) -> None:
        executor = AgentExecutor(
            executor_id="codex",
            adapter="codex",
            executable="codex",
            argv=(),
        )
        contract = build_execution_contract(
            request=AgentRunRequest(
                executor=executor,
                repo="softos-agentic",
                workspace_root="/workspace",
                workdir="/workspace/.worktrees/demo",
                targets=("b.txt", "a.txt"),
                user_prompt="do work",
                contract_body="",
            )
        )
        self.assertIn(EXECUTION_CONTRACT_BEGIN, contract)
        self.assertIn("executor: codex", contract)
        self.assertIn("repository: softos-agentic", contract)
        self.assertIn("workspace_root: /workspace", contract)
        self.assertIn("workdir: /workspace/.worktrees/demo", contract)
        self.assertIn("  - a.txt", contract)
        self.assertIn("  - b.txt", contract)
        self.assertIn(
            "python3 ./flow repo exec --workdir /workspace/.worktrees/demo softos-agentic -- <command>",
            contract,
        )
        self.assertIn("scripts/workspace_exec.sh python3 ./flow <command>", contract)
        self.assertIn("python3 ./flow stack <command>", contract)


class SensitiveMaterialTests(unittest.TestCase):
    def test_metadata_excludes_prompt_streams_and_argv(self) -> None:
        metadata = AgentRunMetadata(
            executor_id="codex",
            repo="softos-agentic",
            workdir="/workspace/.worktrees/demo",
            targets=("flowctl/agent_executors.py",),
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:01+00:00",
            exit_code=0,
        )
        payload = metadata.__dict__
        forbidden_keys = {"prompt", "stdout", "stderr", "argv", "environment", "env"}
        self.assertTrue(forbidden_keys.isdisjoint(payload.keys()))

    def test_command_run_does_not_persist_sensitive_material_on_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports = root / ".flow" / "reports"
            reports.mkdir(parents=True)
            fake = root / "fake-agent"
            _write_fake_executor(fake)
            secret_prompt = "SUPER_SECRET_PROMPT_TOKEN"
            secret_env = "SUPER_SECRET_ENV_TOKEN"
            secret_argv = "SUPER_SECRET_ARGV_TOKEN"
            config = _write_config(
                root,
                agents={
                    "schema_version": 1,
                    "executors": {
                        "codex": {
                            "adapter": "codex",
                            "executable": str(fake),
                            "argv": [secret_argv],
                        },
                    },
                },
            )
            (root / "target.txt").write_text("x", encoding="utf-8")

            with mock.patch.dict(os.environ, {"TEST_AGENT_SECRET": secret_env}, clear=False):
                with mock.patch(
                    "flowctl.agent_process_execution.resolve_adapter",
                    return_value=GenericStdinAdapter(adapter_name="test"),
                ):
                    rc = command_agent_run(
                        argparse_namespace(
                            executor="codex",
                            repo="workspace-root",
                            workdir=str(root),
                            prompt=secret_prompt,
                            target=["target.txt"],
                        ),
                        workspace_root=root,
                        workspace_config_file=config,
                        workspace_config=json.loads(config.read_text(encoding="utf-8")),
                        worktree_root=root / ".worktrees",
                        root_repo="softos-agentic",
                        repo_names=["softos-agentic"],
                        shutil_which=lambda _: None,
                        subprocess_run=subprocess.run,
                    )

            self.assertEqual(0, rc)
            persisted = "".join(path.read_text(encoding="utf-8") for path in reports.rglob("*") if path.is_file())
            self.assertNotIn(secret_prompt, persisted)
            self.assertNotIn(secret_env, persisted)
            self.assertNotIn(secret_argv, persisted)

    def test_validation_failure_does_not_echo_sensitive_material(self) -> None:
        secret_prompt = "SUPER_SECRET_PROMPT_TOKEN"
        secret_env = "SUPER_SECRET_ENV_TOKEN"
        secret_argv = "SUPER_SECRET_ARGV_TOKEN"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _write_config(
                root,
                agents={
                    "schema_version": 1,
                    "executors": {
                        "codex": {
                            "adapter": "codex",
                            "executable": "codex",
                            "argv": [secret_argv],
                        },
                    },
                },
            )
            with mock.patch.dict(os.environ, {"TEST_AGENT_SECRET": secret_env}, clear=False):
                with self.assertRaises(SystemExit) as ctx:
                    command_agent_run(
                        argparse_namespace(
                            executor="codex",
                            repo="workspace-root",
                            workdir=str(root),
                            prompt=secret_prompt,
                            target=["../outside.txt"],
                        ),
                        workspace_root=root,
                        workspace_config_file=config,
                        workspace_config=json.loads(config.read_text(encoding="utf-8")),
                        worktree_root=root / ".worktrees",
                        root_repo="softos-agentic",
                        repo_names=["softos-agentic"],
                        shutil_which=lambda _: None,
                        subprocess_run=subprocess.run,
                    )
            diagnostic = str(ctx.exception)
            self.assertNotIn(secret_prompt, diagnostic)
            self.assertNotIn(secret_env, diagnostic)
            self.assertNotIn(secret_argv, diagnostic)

    def test_missing_executable_does_not_echo_sensitive_material(self) -> None:
        secret_prompt = "SUPER_SECRET_PROMPT_TOKEN"
        secret_env = "SUPER_SECRET_ENV_TOKEN"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing_executable = str((root / "missing-executor").resolve())
            config = _write_config(
                root,
                agents={
                    "schema_version": 1,
                    "executors": {
                        "codex": {
                            "adapter": "codex",
                            "executable": missing_executable,
                            "argv": [],
                        },
                    },
                },
            )
            (root / "target.txt").write_text("x", encoding="utf-8")
            with mock.patch.dict(os.environ, {"TEST_AGENT_SECRET": secret_env}, clear=False):
                with self.assertRaises(SystemExit) as ctx:
                    command_agent_run(
                        argparse_namespace(
                            executor="codex",
                            repo="workspace-root",
                            workdir=str(root),
                            prompt=secret_prompt,
                            target=["target.txt"],
                        ),
                        workspace_root=root,
                        workspace_config_file=config,
                        workspace_config=json.loads(config.read_text(encoding="utf-8")),
                        worktree_root=root / ".worktrees",
                        root_repo="softos-agentic",
                        repo_names=["softos-agentic"],
                        shutil_which=lambda _: None,
                        subprocess_run=subprocess.run,
                    )
            diagnostic = str(ctx.exception)
            self.assertNotIn(secret_prompt, diagnostic)
            self.assertNotIn(secret_env, diagnostic)
            self.assertIn("no esta disponible", diagnostic)


class ExecutorResolutionTests(unittest.TestCase):
    def test_unknown_executor_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _write_config(
                root,
                agents={
                    "schema_version": 1,
                    "executors": {
                        "codex": {"adapter": "codex", "executable": "codex", "argv": []},
                    },
                },
            )
            workspace_config = json.loads(config.read_text(encoding="utf-8"))
            with self.assertRaisesRegex(AgentRunError, "Executor desconocido: `missing`"):
                prepare_agent_run(
                    executor_id="missing",
                    repo_raw="softos-agentic",
                    workdir_raw=str(root),
                    prompt_raw="prompt",
                    target_raws=["."],
                    workspace_root=root,
                    workspace_config_file=config,
                    workspace_config=workspace_config,
                    root_repo="softos-agentic",
                )

    def test_missing_registry_section_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "workspace.config.json"
            config.write_text(
                json.dumps(
                    {
                        "project": {"display_name": "Test", "root_repo": "softos-agentic"},
                        "repos": {"softos-agentic": {"path": ".", "kind": "root"}},
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(AgentRegistryError):
                load_agent_registry(config)

    def test_v1_adapter_reports_missing_executable_when_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = _write_config(
                root,
                agents={
                    "schema_version": 1,
                    "executors": {
                        "codex": {"adapter": "codex", "executable": "codex", "argv": []},
                    },
                },
            )
            workspace_config = json.loads(config.read_text(encoding="utf-8"))
            (root / "target.txt").write_text("x", encoding="utf-8")
            executor, repo, workdir, targets, prompt = prepare_agent_run(
                executor_id="codex",
                repo_raw="workspace-root",
                workdir_raw=str(root),
                prompt_raw="prompt",
                target_raws=["target.txt"],
                workspace_root=root,
                workspace_config_file=config,
                workspace_config=workspace_config,
                root_repo="softos-agentic",
            )
            with self.assertRaises(AgentRunError) as ctx:
                run_agent_process(
                    executor=executor,
                    repo=repo,
                    workspace_root=root,
                    workdir=workdir,
                    targets=targets,
                    prompt=prompt,
                    shutil_which=lambda _: None,
                    subprocess_run=subprocess.run,
                )
            diagnostic = str(ctx.exception)
            self.assertIn("no esta disponible", diagnostic)

    def test_v1_adapter_run_launches_with_fake_executable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake = root / "fake-codex"
            _write_fake_executor(fake)
            config = _write_config(
                root,
                agents={
                    "schema_version": 1,
                    "executors": {
                        "codex": {"adapter": "codex", "executable": str(fake), "argv": []},
                    },
                },
            )
            workspace_config = json.loads(config.read_text(encoding="utf-8"))
            (root / "target.txt").write_text("x", encoding="utf-8")
            executor, repo, workdir, targets, prompt = prepare_agent_run(
                executor_id="codex",
                repo_raw="workspace-root",
                workdir_raw=str(root),
                prompt_raw="prompt",
                target_raws=["target.txt"],
                workspace_root=root,
                workspace_config_file=config,
                workspace_config=workspace_config,
                root_repo="softos-agentic",
            )
            exit_code, _metadata = run_agent_process(
                executor=executor,
                repo=repo,
                workspace_root=root,
                workdir=workdir,
                targets=targets,
                prompt=prompt,
                shutil_which=lambda _: str(fake),
                subprocess_run=subprocess.run,
            )
            self.assertEqual(0, exit_code)

class CommandAgentRunIntegrationTests(unittest.TestCase):
    def test_prepare_agent_run_normalizes_targets_in_lexical_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "b.txt").write_text("b", encoding="utf-8")
            (root / "a.txt").write_text("a", encoding="utf-8")
            config = _write_config(
                root,
                agents={
                    "schema_version": 1,
                    "executors": {
                        "codex": {"adapter": "codex", "executable": "codex", "argv": []},
                    },
                },
            )
            workspace_config = json.loads(config.read_text(encoding="utf-8"))
            _executor, _repo, workdir, targets, prompt = prepare_agent_run(
                executor_id="codex",
                repo_raw="workspace-root",
                workdir_raw=str(root),
                prompt_raw="  do it  ",
                target_raws=["b.txt", "a.txt"],
                workspace_root=root,
                workspace_config_file=config,
                workspace_config=workspace_config,
                root_repo="softos-agentic",
            )
            self.assertEqual(("a.txt", "b.txt"), targets)
            self.assertEqual("  do it  ", prompt)
            self.assertEqual(root.resolve(), workdir.resolve())


class HostNativeRoutingTests(unittest.TestCase):
    def test_flow_agent_run_stays_host_native_without_container(self) -> None:
        root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp)
            codex = bin_dir / "codex"
            _write_fake_executor(codex)
            env = {
                **dict(os.environ),
                "FLOW_FORCE_WORKSPACE_EXEC": "1",
                "FLOW_WORKSPACE_PATH": "/definitely-not-this-worktree",
                "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
            }
            env.pop("GITHUB_ACTIONS", None)
            completed = subprocess.run(
                [
                    "python3",
                    str(root / "flow"),
                    "agent",
                    "run",
                    "codex",
                    "--repo",
                    "workspace-root",
                    "--workdir",
                    str(root),
                    "--prompt",
                    "host-native probe",
                    "--target",
                    "flowctl/agent_process_execution.py",
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertNotIn(HOST_EXECUTION_BLOCK_MESSAGE, completed.stderr)
        self.assertEqual(0, completed.returncode, completed.stderr + completed.stdout)
        self.assertIn("FAKE_STDOUT", completed.stdout)


def _write_opencode_config(root: Path) -> None:
    payload = {
        "default_agent": "softos-local-worker",
        "agent": {
            "softos-local-worker": {
                "model": "lmstudio/prism-ml/bonsai-27b",
                "reasoning": True,
                "steps": 6,
            }
        },
    }
    (root / "opencode.json").write_text(json.dumps(payload), encoding="utf-8")


def _agent_resources_config(
    *,
    fake_opencode: str,
    fake_opencode_softos: str,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "executors": {
            "codex": {"adapter": "codex", "executable": "codex", "argv": []},
            "opencode-local": {
                "adapter": "opencode",
                "executable": fake_opencode_softos,
                "argv": [],
            },
            "opencode-cloud": {
                "adapter": "opencode",
                "executable": fake_opencode,
                "argv": [],
            },
        },
    }


def _resource_section() -> dict[str, object]:
    return {
        "schema_version": 1,
        "resources": {
            "opencode-local": {
                "executor": "opencode-local",
                "tier": "local",
                "capacity": 1,
                "capabilities": ["tool_calling", "write", "patch_unit"],
                "data_sensitivity": "local-only",
                "local_profile": {
                    "opencode_config": "opencode.json",
                    "worker": "softos-local-worker",
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
        },
    }


def _write_config_overlay_workspace(
    root: Path,
    *,
    fake_opencode: Path,
    fake_opencode_softos: Path,
) -> Path:
    payload: dict[str, object] = {
        "project": {"display_name": "Test", "root_repo": "softos-agentic"},
        "repos": {"softos-agentic": {"path": ".", "kind": "root"}},
        "agents": _agent_resources_config(
            fake_opencode=str(fake_opencode),
            fake_opencode_softos=str(fake_opencode_softos),
        ),
        "agent_resources": _resource_section(),
    }
    path = root / "workspace.config.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    _write_opencode_config(root)
    return path


def _write_opencode_env_probe(path: Path) -> None:
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import os\n"
        "import sys\n"
        "content = os.environ.get('OPENCODE_CONFIG_CONTENT', '')\n"
        "sys.stdout.write(content)\n"
        "sys.stderr.write('')\n"
        "if not sys.stdin.isatty():\n"
        "    sys.stdin.read()\n"
        "raise SystemExit(0)\n",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


class ResourceExecutionBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.fake_opencode = self.root / "fake-opencode"
        self.fake_opencode_softos = self.root / "fake-opencode-softos"
        _write_opencode_env_probe(self.fake_opencode)
        _write_opencode_env_probe(self.fake_opencode_softos)
        self.config = _write_config_overlay_workspace(
            self.root,
            fake_opencode=self.fake_opencode,
            fake_opencode_softos=self.fake_opencode_softos,
        )
        self.workspace_config = json.loads(self.config.read_text(encoding="utf-8"))
        (self.root / "target.txt").write_text("x", encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _discovery_free(self) -> object:
        from flowctl.agent_resources import FixtureModelCatalogDiscovery, ModelCatalogEntry

        return FixtureModelCatalogDiscovery(
            models=(ModelCatalogEntry("opencode/claude-free", "opencode"),)
        )

    def _discovery_go(self) -> object:
        from flowctl.agent_resources import FixtureModelCatalogDiscovery, ModelCatalogEntry

        return FixtureModelCatalogDiscovery(
            models=(
                ModelCatalogEntry("opencode-go/zeta-model", "opencode-go"),
                ModelCatalogEntry("opencode-go/alpha-model", "opencode-go"),
            )
        )

    def test_legacy_executor_invocation_still_works(self) -> None:
        fake_codex = self.root / "fake-codex"
        _write_fake_executor(fake_codex)
        config = _write_config(
            self.root,
            agents={
                "schema_version": 1,
                "executors": {
                    "codex": {"adapter": "codex", "executable": str(fake_codex), "argv": []},
                },
            },
        )
        workspace_config = json.loads(config.read_text(encoding="utf-8"))
        prepared = prepare_agent_run(
            executor_id="codex",
            repo_raw="workspace-root",
            workdir_raw=str(self.root),
            prompt_raw="prompt",
            target_raws=["target.txt"],
            workspace_root=self.root,
            workspace_config_file=config,
            workspace_config=workspace_config,
            root_repo="softos-agentic",
        )
        exit_code, _metadata = run_agent_process(
            executor=prepared.executor,
            repo=prepared.repo,
            workspace_root=self.root,
            workdir=prepared.workdir,
            targets=prepared.targets,
            prompt=prepared.prompt,
            shutil_which=lambda _: str(fake_codex),
            subprocess_run=subprocess.run,
        )
        self.assertEqual(0, exit_code)
        self.assertEqual({}, dict(prepared.env_overlay))

    def test_opencode_local_uses_softos_wrapper_without_overlay(self) -> None:
        captured: dict[str, object] = {}

        def fake_run(**kwargs: object) -> object:
            captured.update(kwargs)
            return subprocess.CompletedProcess(args=kwargs["args"], returncode=0, stdout=b"", stderr=b"")

        prepared = prepare_agent_run(
            executor_id="opencode-local",
            repo_raw="workspace-root",
            workdir_raw=str(self.root),
            prompt_raw="prompt",
            target_raws=["target.txt"],
            workspace_root=self.root,
            workspace_config_file=self.config,
            workspace_config=self.workspace_config,
            root_repo="softos-agentic",
        )
        self.assertEqual("opencode-local", prepared.resource_id)
        self.assertEqual(str(self.fake_opencode_softos), prepared.executor.executable)
        self.assertEqual({}, dict(prepared.env_overlay))

        with mock.patch(
            "flowctl.agent_process_execution.resolve_adapter",
            return_value=GenericStdinAdapter(adapter_name="opencode"),
        ):
            run_agent_process(
                executor=prepared.executor,
                repo=prepared.repo,
                workspace_root=self.root,
                workdir=prepared.workdir,
                targets=prepared.targets,
                prompt=prepared.prompt,
                shutil_which=lambda _: str(self.fake_opencode_softos),
                subprocess_run=fake_run,
                env_overlay=prepared.env_overlay,
            )
        self.assertNotIn("env", captured)

    def test_opencode_free_passes_dynamic_model_via_overlay(self) -> None:
        captured: dict[str, object] = {}

        def fake_run(**kwargs: object) -> object:
            captured.update(kwargs)
            env = kwargs.get("env", {})
            stdout = str(env.get("OPENCODE_CONFIG_CONTENT", "")).encode("utf-8")
            return subprocess.CompletedProcess(args=kwargs["args"], returncode=0, stdout=stdout, stderr=b"")

        prepared = prepare_agent_run(
            executor_id="opencode-free",
            repo_raw="workspace-root",
            workdir_raw=str(self.root),
            prompt_raw="prompt",
            target_raws=["target.txt"],
            workspace_root=self.root,
            workspace_config_file=self.config,
            workspace_config=self.workspace_config,
            root_repo="softos-agentic",
            discovery=self._discovery_free(),
        )
        self.assertEqual("opencode-free", prepared.resource_id)
        self.assertEqual(str(self.fake_opencode), prepared.executor.executable)
        parsed = json.loads(prepared.env_overlay["OPENCODE_CONFIG_CONTENT"])
        self.assertEqual("opencode/claude-free", parsed["model"])
        self.assertEqual("softos-cloud-worker", parsed["default_agent"])
        self.assertEqual("opencode/claude-free", parsed["agent"]["softos-cloud-worker"]["model"])
        self.assertNotIn("softos-local-worker", prepared.env_overlay["OPENCODE_CONFIG_CONTENT"])
        self.assertNotIn("bonsai", prepared.env_overlay["OPENCODE_CONFIG_CONTENT"].lower())

        with mock.patch(
            "flowctl.agent_process_execution.resolve_adapter",
            return_value=GenericStdinAdapter(adapter_name="opencode"),
        ):
            exit_code, _metadata = run_agent_process(
                executor=prepared.executor,
                repo=prepared.repo,
                workspace_root=self.root,
                workdir=prepared.workdir,
                targets=prepared.targets,
                prompt=prepared.prompt,
                shutil_which=lambda _: str(self.fake_opencode),
                subprocess_run=fake_run,
                env_overlay=prepared.env_overlay,
                resource_id=prepared.resource_id,
            )
        self.assertEqual(0, exit_code)
        env = captured["env"]
        self.assertIn("PATH", env)
        self.assertIn("opencode/claude-free", env["OPENCODE_CONFIG_CONTENT"])
        argv = captured["args"]
        joined = " ".join(str(item) for item in argv)
        self.assertNotIn("--model", joined)
        self.assertNotIn("--provider", joined)

    def test_opencode_go_unauthenticated_does_not_spawn(self) -> None:
        spawn_called = False

        def fake_run(**kwargs: object) -> object:
            nonlocal spawn_called
            spawn_called = True
            return subprocess.CompletedProcess(args=kwargs["args"], returncode=0, stdout=b"", stderr=b"")

        with self.assertRaisesRegex(AgentRunError, "AUTH_UNCONFIGURED"):
            prepare_agent_run(
                executor_id="opencode-go",
                repo_raw="workspace-root",
                workdir_raw=str(self.root),
                prompt_raw="prompt",
                target_raws=["target.txt"],
                workspace_root=self.root,
                workspace_config_file=self.config,
                workspace_config=self.workspace_config,
                root_repo="softos-agentic",
                discovery=self._discovery_go(),
                subprocess_run=fake_run,
            )
        self.assertFalse(spawn_called)

    def test_opencode_go_with_fixture_evidence_applies_overlay(self) -> None:
        from flowctl.agent_resources import RuntimeEvidence

        captured: dict[str, object] = {}

        def fake_run(**kwargs: object) -> object:
            captured.update(kwargs)
            env = kwargs.get("env", {})
            stdout = str(env.get("OPENCODE_CONFIG_CONTENT", "")).encode("utf-8")
            return subprocess.CompletedProcess(args=kwargs["args"], returncode=0, stdout=stdout, stderr=b"")

        evidence = RuntimeEvidence(auth_configured={"opencode-go": True})
        prepared = prepare_agent_run(
            executor_id="opencode-go",
            repo_raw="workspace-root",
            workdir_raw=str(self.root),
            prompt_raw="prompt",
            target_raws=["target.txt"],
            workspace_root=self.root,
            workspace_config_file=self.config,
            workspace_config=self.workspace_config,
            root_repo="softos-agentic",
            discovery=self._discovery_go(),
            evidence=evidence,
        )
        self.assertEqual("opencode-go/alpha-model", json.loads(prepared.env_overlay["OPENCODE_CONFIG_CONTENT"])["model"])
        self.assertEqual(
            "softos-cloud-worker",
            json.loads(prepared.env_overlay["OPENCODE_CONFIG_CONTENT"])["default_agent"],
        )
        self.assertEqual(str(self.fake_opencode), prepared.executor.executable)

        with mock.patch(
            "flowctl.agent_process_execution.resolve_adapter",
            return_value=GenericStdinAdapter(adapter_name="opencode"),
        ):
            run_agent_process(
                executor=prepared.executor,
                repo=prepared.repo,
                workspace_root=self.root,
                workdir=prepared.workdir,
                targets=prepared.targets,
                prompt=prepared.prompt,
                shutil_which=lambda _: str(self.fake_opencode),
                subprocess_run=fake_run,
                env_overlay=prepared.env_overlay,
            )
        self.assertIn("opencode-go/alpha-model", captured["env"]["OPENCODE_CONFIG_CONTENT"])

    def test_environment_merge_preserves_inherited_values(self) -> None:
        captured: dict[str, object] = {}
        inherited = "PRESERVED_OVERLAY_PROBE"

        def fake_run(**kwargs: object) -> object:
            captured.update(kwargs)
            return subprocess.CompletedProcess(args=kwargs["args"], returncode=0, stdout=b"", stderr=b"")

        prepared = prepare_agent_run(
            executor_id="opencode-free",
            repo_raw="workspace-root",
            workdir_raw=str(self.root),
            prompt_raw="prompt",
            target_raws=["target.txt"],
            workspace_root=self.root,
            workspace_config_file=self.config,
            workspace_config=self.workspace_config,
            root_repo="softos-agentic",
            discovery=self._discovery_free(),
        )
        with mock.patch.dict(os.environ, {"PRESERVED_OVERLAY_PROBE": inherited}, clear=False):
            with mock.patch(
                "flowctl.agent_process_execution.resolve_adapter",
                return_value=GenericStdinAdapter(adapter_name="opencode"),
            ):
                run_agent_process(
                    executor=prepared.executor,
                    repo=prepared.repo,
                    workspace_root=self.root,
                    workdir=prepared.workdir,
                    targets=prepared.targets,
                    prompt=prepared.prompt,
                    shutil_which=lambda _: str(self.fake_opencode),
                    subprocess_run=fake_run,
                    env_overlay=prepared.env_overlay,
                )
        self.assertEqual(inherited, captured["env"]["PRESERVED_OVERLAY_PROBE"])

    def test_unavailable_free_resource_blocks_execution(self) -> None:
        from flowctl.agent_resources import FixtureModelCatalogDiscovery

        discovery = FixtureModelCatalogDiscovery(models=())
        with self.assertRaisesRegex(AgentRunError, "MODEL_UNAVAILABLE"):
            prepare_agent_run(
                executor_id="opencode-free",
                repo_raw="workspace-root",
                workdir_raw=str(self.root),
                prompt_raw="prompt",
                target_raws=["target.txt"],
                workspace_root=self.root,
                workspace_config_file=self.config,
                workspace_config=self.workspace_config,
                root_repo="softos-agentic",
                discovery=discovery,
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
