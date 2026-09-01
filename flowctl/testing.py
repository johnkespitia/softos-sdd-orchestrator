from __future__ import annotations

import json
import os
import shutil
from pathlib import Path


def file_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def resolve_repository_relative_path(repo_path: Path, raw_path: str) -> tuple[str | None, str]:
    path_text = raw_path.strip()
    if not path_text:
        return None, "debe ser un path relativo al repo"

    target_path = Path(path_text)
    if target_path.is_absolute():
        return None, "debe ser un path relativo al repo"

    if ".." in target_path.parts:
        return None, "no puede escapar del repo con `..`"

    normalized = os.path.normpath(path_text)
    if normalized in {".", ""}:
        return None, "debe ser un path relativo al repo"

    parts = [part for part in Path(normalized).parts if part and part != "."]
    if ".." in parts:
        return None, "no puede escapar del repo con `..`"

    repo_root = repo_path.resolve()
    current = repo_path
    for part in parts:
        current = current / part
        try:
            resolved = current.resolve(strict=False)
        except (OSError, RuntimeError):
            return None, "resuelve fuera del repo"
        try:
            resolved.relative_to(repo_root)
        except ValueError:
            return None, "resuelve fuera del repo"

    if parts:
        return Path(*parts).as_posix(), ""
    return ".", ""


def valid_python_test_file(path: Path) -> tuple[bool, str]:
    if not path.is_file():
        return False, "no es un archivo"
    if path.suffix.lower() != ".py":
        return False, "debe terminar en `.py`"
    # accept if path looks like a Python test (e.g. `test_*.py`, `*_test.py`, or lives under `tests/`)
    name = path.name
    is_test_like = name.startswith("test_") or "_test." in name or ".test." in name
    is_under_tests = "tests" in path.parts
    if not (is_test_like or is_under_tests):
        return False, "debe ser `test_*.py`, `*_test.py` o vivir bajo `tests/`"

    text = file_text(path).lower()
    if "assert" in text or "def test_" in text or "def test(" in text or "import pytest" in text or "from pytest import" in text:
        return True, ""
    return False, "no parece un test Python (ausencia de `assert`, `def test_`, `def test(`, o imports de pytest)"


def valid_php_test_file(path: Path) -> tuple[bool, str]:
    if not path.is_file():
        return False, "no es un archivo"
    if path.suffix.lower() != ".php":
        return False, "debe terminar en `.php`"
    if "tests" not in path.parts:
        return False, "debe vivir bajo `tests/`"

    text = file_text(path).lower()
    if path.name.endswith("Test.php") or "extends testcase" in text or "test(" in text or "it(" in text:
        return True, ""
    return False, "no parece un test PHPUnit o Pest"


def valid_pnpm_test_file(path: Path) -> tuple[bool, str]:
    if not path.is_file():
        return False, "no es un archivo"
    if path.suffix.lower() not in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}:
        return False, "debe ser un archivo JS/TS"
    if "tests" not in path.parts and ".test." not in path.name and ".spec." not in path.name:
        return False, "debe vivir bajo `tests/` o usar sufijo `.test`/`.spec`"

    text = file_text(path).lower()
    if "describe(" in text or "it(" in text or "test(" in text:
        return True, ""
    return False, "no parece un test ejecutable por el runner JS/TS"


def valid_go_test_file(path: Path) -> tuple[bool, str]:
    if not path.is_file():
        return False, "no es un archivo"
    if path.suffix.lower() != ".go":
        return False, "debe terminar en `.go`"
    if not path.name.endswith("_test.go") and "tests" not in path.parts:
        return False, "debe usar sufijo `_test.go` o vivir bajo `tests/`"
    text = file_text(path).lower()
    if "func test" in text or path.name.endswith("_test.go"):
        return True, ""
    return False, "no parece un test ejecutable por `go test`"


def validate_test_file_for_runner(runner: str, absolute_path: Path) -> tuple[bool, str]:
    normalized_runner = runner.strip().lower()
    if normalized_runner == "none":
        return False, "el repo no declara `test_runner`"
    if normalized_runner == "pytest":
        return valid_python_test_file(absolute_path)
    if normalized_runner == "php":
        return valid_php_test_file(absolute_path)
    if normalized_runner == "pnpm":
        return valid_pnpm_test_file(absolute_path)
    if normalized_runner == "go":
        return valid_go_test_file(absolute_path)
    return False, f"el runner `{runner}` no es un identificador de runner soportado"


def materialize_glob_paths(repo_path: Path, patterns: list[str]) -> tuple[list[str], list[str]]:
    materialized: list[str] = []
    missing: list[str] = []

    for pattern in patterns:
        candidate = repo_path / pattern
        if candidate.exists():
            materialized.append(pattern)
            continue

        matches = sorted(path.relative_to(repo_path).as_posix() for path in repo_path.glob(pattern))
        if matches:
            materialized.extend(matches)
            continue

        missing.append(pattern)

    return sorted(dict.fromkeys(materialized)), missing


def validate_test_reference_patterns(
    repo_path: Path,
    runner: str,
    patterns: list[str],
    *,
    repo_label: str,
) -> tuple[list[str], list[str], list[str]]:
    normalized_runner = runner.strip().lower()
    if normalized_runner == "pytest":
        materialized: list[str] = []
        missing: list[str] = []
        invalid: list[str] = []
        for pattern in patterns:
            relative_path, reason = resolve_repository_relative_path(repo_path, pattern)
            if relative_path is None:
                invalid.append(f"`{pattern}` no es una referencia valida para `{repo_label}`: {reason}.")
                continue
            absolute_path = repo_path / relative_path
            if not absolute_path.is_file():
                missing.append(pattern)
                continue
            valid, file_reason = validate_test_file_for_runner(runner, absolute_path)
            if not valid:
                invalid.append(f"`{pattern}` no es un test valido para `{repo_label}`: {file_reason}.")
                continue
            materialized.append(relative_path)
        return sorted(dict.fromkeys(materialized)), missing, invalid

    materialized, missing = materialize_glob_paths(repo_path, patterns)
    invalid: list[str] = []
    for relative_path in materialized:
        absolute_path = repo_path / relative_path
        valid, reason = validate_test_file_for_runner(runner, absolute_path)
        if not valid:
            invalid.append(f"`{relative_path}` no es un test valido para `{repo_label}`: {reason}.")
    return materialized, missing, invalid


def detect_test_command(runner: str, repo_path: Path, test_paths: list[str]) -> list[str] | None:
    if not test_paths:
        return None

    normalized_runner = runner.strip().lower()
    if normalized_runner == "pytest":
        validated_paths: list[str] = []
        for test_path in test_paths:
            relative_path, _reason = resolve_repository_relative_path(repo_path, test_path)
            if relative_path is None:
                return None
            absolute_path = repo_path / relative_path
            if not absolute_path.is_file():
                return None
            valid, _file_reason = validate_test_file_for_runner("pytest", absolute_path)
            if not valid:
                return None
            validated_paths.append(relative_path)
        return ["python3", "-m", "pytest", *validated_paths]

    if normalized_runner == "php":
        artisan = repo_path / "artisan"
        if artisan.exists():
            return ["php", "artisan", "test", *test_paths]

        phpunit = repo_path / "vendor" / "bin" / "phpunit"
        if phpunit.exists():
            return [str(phpunit), *test_paths]

    if normalized_runner == "pnpm":
        package_json = repo_path / "package.json"
        if package_json.exists() and shutil.which("pnpm"):
            try:
                package = json.loads(package_json.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return None

            scripts = package.get("scripts", {})
            if isinstance(scripts, dict) and "test" in scripts:
                return ["pnpm", "test", "--", *test_paths]

    if normalized_runner == "go":
        go_mod = repo_path / "go.mod"
        if go_mod.exists() and shutil.which("go"):
            return ["go", "test", "./..."]

    return None
