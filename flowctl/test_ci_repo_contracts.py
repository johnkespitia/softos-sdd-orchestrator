from __future__ import annotations

import importlib.machinery
import importlib.util
from pathlib import Path

from flowctl.ci import _reproducible_install_findings
from flowctl.testing import (
    detect_test_command,
    validate_test_file_for_runner,
    validate_test_reference_patterns,
)

ROOT = Path(__file__).resolve().parents[1]
FLOW_PATH = ROOT / "flow"
REPO_LABEL = "sdd-workspace-boilerplate"


def _load_flow_module(module_name: str):
    flow_spec = importlib.util.spec_from_loader(
        module_name,
        importlib.machinery.SourceFileLoader(module_name, str(FLOW_PATH)),
    )
    flow_module = importlib.util.module_from_spec(flow_spec)
    assert flow_spec.loader is not None
    flow_spec.loader.exec_module(flow_module)
    return flow_module


def test_reproducible_install_findings_flags_manifest_lock_drift(tmp_path: Path) -> None:
    repo_path = tmp_path / "frontend-app"
    repo_path.mkdir()
    (repo_path / "package.json").write_text('{"name":"frontend-app"}\n', encoding="utf-8")
    (repo_path / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n", encoding="utf-8")

    findings = _reproducible_install_findings(
        repo_name="frontend-app",
        repo_path=repo_path,
        repo_payload={
            "test_runner": "pnpm",
            "ci": {
                "install_contract": {
                    "mode": "strict",
                    "manifest_files": ["package.json"],
                    "lock_files": ["pnpm-lock.yaml"],
                }
            },
        },
        changed_files=["package.json"],
        commands=[("Install", ["pnpm", "install", "--frozen-lockfile"])],
    )

    assert any("sin actualizar lockfile" in finding for finding in findings)


def test_reproducible_install_findings_flags_non_strict_install_command(tmp_path: Path) -> None:
    repo_path = tmp_path / "frontend-app"
    repo_path.mkdir()
    (repo_path / "package.json").write_text('{"name":"frontend-app"}\n', encoding="utf-8")
    (repo_path / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n", encoding="utf-8")

    findings = _reproducible_install_findings(
        repo_name="frontend-app",
        repo_path=repo_path,
        repo_payload={
            "test_runner": "pnpm",
            "ci": {
                "install_contract": {
                    "mode": "strict",
                    "manifest_files": ["package.json"],
                    "lock_files": ["pnpm-lock.yaml"],
                }
            },
        },
        changed_files=[],
        commands=[("Install", ["pnpm", "install"])],
    )

    assert any("no es estricto" in finding for finding in findings)


def test_pytest_validate_accepts_linked_test_file(tmp_path: Path) -> None:
    test_file = tmp_path / "flowctl" / "test_foo.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("def test_x(): assert True\n", encoding="utf-8")

    valid, _reason = validate_test_file_for_runner("pytest", test_file)
    assert valid is True


def test_pytest_validate_rejects_non_py_and_none_runner(tmp_path: Path) -> None:
    test_file = tmp_path / "flowctl" / "test_foo.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("def test_x(): assert True\n", encoding="utf-8")

    valid, reason = validate_test_file_for_runner("none", test_file)
    assert valid is False
    assert "test_runner" in reason

    valid, _reason = validate_test_file_for_runner("pytest", tmp_path / "readme.txt")
    assert valid is False


def test_validate_test_file_for_runner_rejects_unsupported_runner(tmp_path: Path) -> None:
    test_file = tmp_path / "tests" / "test_example.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("def test_x(): assert True\n", encoding="utf-8")

    valid, reason = validate_test_file_for_runner("cargo", test_file)
    assert valid is False
    assert "cargo" in reason
    assert "no es un identificador de runner soportado" in reason


def test_detect_test_command_pytest_linked_only_paths(tmp_path: Path) -> None:
    test_x = tmp_path / "a" / "test_x.py"
    test_x.parent.mkdir(parents=True)
    test_x.write_text("def test_x(): assert True\n", encoding="utf-8")

    test_y = tmp_path / "b" / "test_y.py"
    test_y.parent.mkdir(parents=True)
    test_y.write_text("def test_y(): assert True\n", encoding="utf-8")

    not_linked = tmp_path / "tests" / "test_not_linked.py"
    not_linked.parent.mkdir(parents=True)
    not_linked.write_text("def test_not_linked(): assert True\n", encoding="utf-8")

    assert detect_test_command("pytest", tmp_path, ["a/test_x.py", "b/test_y.py"]) == [
        "python3",
        "-m",
        "pytest",
        "a/test_x.py",
        "b/test_y.py",
    ]
    assert detect_test_command("pytest", tmp_path, []) is None


def test_detect_test_command_rejects_unvalidated_paths(tmp_path: Path) -> None:
    assert detect_test_command("pytest", tmp_path, ["/etc/passwd"]) is None
    assert detect_test_command("pytest", tmp_path, ["../escape.py"]) is None


def test_detect_test_command_pytest_rejects_raw_in_repository_traversal(tmp_path: Path) -> None:
    test_file = tmp_path / "tests" / "test_valid.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("def test_ok(): assert True\n", encoding="utf-8")
    traversal_pattern = "tests/../tests/test_valid.py"

    assert detect_test_command("pytest", tmp_path, [traversal_pattern]) is None


def test_detect_test_command_pytest_rejects_nonexistent_path(tmp_path: Path) -> None:
    assert detect_test_command("pytest", tmp_path, ["tests/test_missing.py"]) is None


def test_detect_test_command_pytest_rejects_outside_symlink(tmp_path_factory) -> None:
    repo_path = tmp_path_factory.mktemp("repo")
    external_root = tmp_path_factory.mktemp("external")
    external_file = external_root / "outside_test.py"
    external_file.write_text("def test_external(): assert True\n", encoding="utf-8")

    escape_symlink = repo_path / "tests" / "test_escape.py"
    escape_symlink.parent.mkdir(parents=True)
    escape_symlink.symlink_to(external_file)

    assert detect_test_command("pytest", repo_path, ["tests/test_escape.py"]) is None


def test_none_and_php_runner_validation_preserved(tmp_path: Path) -> None:
    test_file = tmp_path / "flowctl" / "test_foo.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("def test_x(): assert True\n", encoding="utf-8")

    valid, reason = validate_test_file_for_runner("none", test_file)
    assert valid is False
    assert "test_runner" in reason

    php_test = tmp_path / "tests" / "Unit" / "ExampleTest.php"
    php_test.parent.mkdir(parents=True)
    php_test.write_text(
        "<?php\nclass ExampleTest extends TestCase { public function test_ok() {} }\n",
        encoding="utf-8",
    )

    valid, _reason = validate_test_file_for_runner("php", php_test)
    assert valid is True


def test_effective_test_runner_inherits_pytest_from_python_runtime() -> None:
    flow_module = _load_flow_module("flow_cli_effective_runner_inherit")
    assert flow_module.effective_test_runner("sdd-workspace-boilerplate") == "pytest"


def test_effective_test_runner_explicit_override_wins() -> None:
    flow_module = _load_flow_module("flow_cli_effective_runner_override")
    original_repo_config = dict(flow_module.REPO_CONFIG)
    repo_config = dict(flow_module.REPO_CONFIG["sdd-workspace-boilerplate"])
    repo_config["test_runner"] = "none"
    flow_module.REPO_CONFIG["sdd-workspace-boilerplate"] = repo_config
    try:
        assert flow_module.effective_test_runner("sdd-workspace-boilerplate") == "none"
    finally:
        flow_module.REPO_CONFIG.clear()
        flow_module.REPO_CONFIG.update(original_repo_config)


def test_validate_test_reference_patterns_accepts_linked_pytest_path(tmp_path: Path) -> None:
    test_file = tmp_path / "tests" / "test_example.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("def test_ok(): assert True\n", encoding="utf-8")

    materialized, missing, invalid = validate_test_reference_patterns(
        repo_path=tmp_path,
        runner="pytest",
        patterns=["tests/test_example.py"],
        repo_label=REPO_LABEL,
    )

    assert materialized == ["tests/test_example.py"]
    assert missing == []
    assert invalid == []


def test_validate_test_reference_patterns_rejects_absolute_path(tmp_path: Path) -> None:
    absolute_file = "/etc/passwd"

    materialized, missing, invalid = validate_test_reference_patterns(
        repo_path=tmp_path,
        runner="pytest",
        patterns=[absolute_file],
        repo_label=REPO_LABEL,
    )

    assert materialized == []
    assert missing == []
    assert invalid == [
        f"`{absolute_file}` no es una referencia valida para `{REPO_LABEL}`: debe ser un path relativo al repo."
    ]


def test_validate_test_reference_patterns_rejects_parent_traversal_escaping_repo(tmp_path: Path) -> None:
    escape_pattern = "../escape.py"

    materialized, missing, invalid = validate_test_reference_patterns(
        repo_path=tmp_path,
        runner="pytest",
        patterns=[escape_pattern],
        repo_label=REPO_LABEL,
    )

    assert materialized == []
    assert missing == []
    assert invalid == [
        f"`{escape_pattern}` no es una referencia valida para `{REPO_LABEL}`: no puede escapar del repo con `..`."
    ]


def test_validate_test_reference_patterns_rejects_raw_in_repository_traversal(tmp_path: Path) -> None:
    test_file = tmp_path / "tests" / "test_valid.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("def test_ok(): assert True\n", encoding="utf-8")
    traversal_pattern = "tests/../tests/test_valid.py"

    materialized, missing, invalid = validate_test_reference_patterns(
        repo_path=tmp_path,
        runner="pytest",
        patterns=[traversal_pattern],
        repo_label=REPO_LABEL,
    )

    assert materialized == []
    assert missing == []
    assert invalid == [
        f"`{traversal_pattern}` no es una referencia valida para `{REPO_LABEL}`: no puede escapar del repo con `..`."
    ]


def test_validate_test_reference_patterns_rejects_outside_symlink(tmp_path_factory) -> None:
    repo_path = tmp_path_factory.mktemp("repo")
    external_root = tmp_path_factory.mktemp("external")
    external_file = external_root / "outside_test.py"
    external_file.write_text("def test_external(): assert True\n", encoding="utf-8")

    outside_symlink = repo_path / "tests" / "outside_link.py"
    outside_symlink.parent.mkdir(parents=True)
    outside_symlink.symlink_to(external_file)

    materialized, missing, invalid = validate_test_reference_patterns(
        repo_path=repo_path,
        runner="pytest",
        patterns=["tests/outside_link.py"],
        repo_label=REPO_LABEL,
    )

    assert materialized == []
    assert missing == []
    assert invalid == [
        f"`tests/outside_link.py` no es una referencia valida para `{REPO_LABEL}`: resuelve fuera del repo."
    ]


def test_validate_test_reference_patterns_rejects_unsupported_runner(tmp_path: Path) -> None:
    test_file = tmp_path / "tests" / "test_example.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("def test_ok(): assert True\n", encoding="utf-8")

    materialized, missing, invalid = validate_test_reference_patterns(
        repo_path=tmp_path,
        runner="cargo",
        patterns=["tests/test_example.py"],
        repo_label=REPO_LABEL,
    )

    assert materialized == ["tests/test_example.py"]
    assert missing == []
    assert invalid == [
        f"`tests/test_example.py` no es un test valido para `{REPO_LABEL}`: el runner `cargo` no es un identificador de runner soportado."
    ]


def test_detect_test_command_php_prefers_artisan(tmp_path: Path) -> None:
    repo_path = tmp_path / "backend"
    repo_path.mkdir()
    (repo_path / "artisan").write_text("#!/usr/bin/env php\n", encoding="utf-8")

    assert detect_test_command("php", repo_path, ["tests/Unit/ExampleTest.php"]) == [
        "php",
        "artisan",
        "test",
        "tests/Unit/ExampleTest.php",
    ]


def test_detect_test_command_php_falls_back_to_phpunit(tmp_path: Path) -> None:
    repo_path = tmp_path / "backend"
    phpunit = repo_path / "vendor" / "bin" / "phpunit"
    phpunit.parent.mkdir(parents=True)
    phpunit.write_text("#!/usr/bin/env php\n", encoding="utf-8")

    assert detect_test_command("php", repo_path, ["tests/Unit/ExampleTest.php"]) == [
        str(phpunit),
        "tests/Unit/ExampleTest.php",
    ]


def test_validate_test_reference_patterns_accepts_php_test_file(tmp_path: Path) -> None:
    php_test = tmp_path / "tests" / "Unit" / "ExampleTest.php"
    php_test.parent.mkdir(parents=True)
    php_test.write_text(
        "<?php\nclass ExampleTest extends TestCase { public function test_ok() {} }\n",
        encoding="utf-8",
    )

    materialized, missing, invalid = validate_test_reference_patterns(
        repo_path=tmp_path,
        runner="php",
        patterns=["tests/Unit/ExampleTest.php"],
        repo_label="backend",
    )

    assert materialized == ["tests/Unit/ExampleTest.php"]
    assert missing == []
    assert invalid == []


def test_detect_test_command_pnpm_with_test_script(monkeypatch, tmp_path: Path) -> None:
    repo_path = tmp_path / "frontend"
    repo_path.mkdir()
    (repo_path / "package.json").write_text(
        '{"scripts":{"test":"vitest run"}}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "flowctl.testing.shutil.which",
        lambda command: "/usr/bin/pnpm" if command == "pnpm" else None,
    )

    assert detect_test_command("pnpm", repo_path, ["tests/app.test.ts"]) == [
        "pnpm",
        "test",
        "--",
        "tests/app.test.ts",
    ]


def test_validate_test_reference_patterns_accepts_pnpm_test_file(tmp_path: Path) -> None:
    pnpm_test = tmp_path / "tests" / "app.test.ts"
    pnpm_test.parent.mkdir(parents=True)
    pnpm_test.write_text("describe('app', () => { it('works', () => {}); });\n", encoding="utf-8")

    materialized, missing, invalid = validate_test_reference_patterns(
        repo_path=tmp_path,
        runner="pnpm",
        patterns=["tests/app.test.ts"],
        repo_label="frontend",
    )

    assert materialized == ["tests/app.test.ts"]
    assert missing == []
    assert invalid == []


def test_detect_test_command_go_with_go_mod(monkeypatch, tmp_path: Path) -> None:
    repo_path = tmp_path / "go-api"
    repo_path.mkdir()
    (repo_path / "go.mod").write_text("module example.com/go-api\n\ngo 1.22\n", encoding="utf-8")
    monkeypatch.setattr(
        "flowctl.testing.shutil.which",
        lambda command: "/usr/bin/go" if command == "go" else None,
    )

    assert detect_test_command("go", repo_path, ["pkg/foo_test.go"]) == [
        "go",
        "test",
        "./...",
    ]


def test_validate_test_reference_patterns_accepts_go_test_file(tmp_path: Path) -> None:
    go_test = tmp_path / "pkg" / "foo_test.go"
    go_test.parent.mkdir(parents=True)
    go_test.write_text("package pkg\n\nfunc TestFoo(t *testing.T) {}\n", encoding="utf-8")

    materialized, missing, invalid = validate_test_reference_patterns(
        repo_path=tmp_path,
        runner="go",
        patterns=["pkg/foo_test.go"],
        repo_label="go-api",
    )

    assert materialized == ["pkg/foo_test.go"]
    assert missing == []
    assert invalid == []
