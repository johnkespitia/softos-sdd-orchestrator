from __future__ import annotations

import argparse
import json
from pathlib import Path

from flowctl.ci import command_ci_spec, resolve_ci_report_root
from flowctl.profiles import ProfileContext, default_deliverable_roots


def _args(*, all_specs: bool = False, changed: bool = False) -> argparse.Namespace:
    return argparse.Namespace(
        spec=None,
        all=all_specs,
        changed=changed,
        base=None,
        head=None,
        json=True,
    )


def _analysis_with_status(status: str) -> dict[str, object]:
    return {
        "frontmatter": {"status": status},
        "frontmatter_errors": [],
        "missing_frontmatter": [],
        "target_errors": [],
        "test_errors": [],
        "todo_count": 0,
        "schema_version": 2,
        "target_index": {"sdd-workspace-boilerplate": []},
        "test_index": {"sdd-workspace-boilerplate": []},
    }


def _profile_context(root: Path, *, profile_id: str, ci_reports: Path) -> ProfileContext:
    defaults = default_deliverable_roots(root)
    write_roots = dict(defaults)
    write_roots["ci_reports"] = ci_reports
    return ProfileContext(
        profile_id=profile_id,
        write_roots=write_roots,
        default_roots=defaults,
        read_roots={key: [path] for key, path in write_roots.items()},
    )


def _run_ci_spec(
    *,
    tmp_path: Path,
    ci_report_root: Path,
    profile_context: ProfileContext | None = None,
) -> tuple[int, Path]:
    spec_path = tmp_path / "specs" / "features" / "demo.spec.md"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("dummy", encoding="utf-8")
    selected_root = resolve_ci_report_root(ci_report_root, profile_context=profile_context)
    selected_root.mkdir(parents=True, exist_ok=True)

    rc = command_ci_spec(
        _args(all_specs=True),
        require_dirs=lambda: None,
        select_spec_paths=lambda *_args, **_kwargs: [spec_path],
        analyze_spec=lambda _path: _analysis_with_status("released"),
        test_reference_findings=lambda _analysis: [],
        repos_missing_test_refs=lambda _a, _b: [],
        spec_dependency_findings=lambda _analysis: [],
        rel=lambda p: str(p),
        format_findings=lambda items: [f"- {item}" for item in items] if items else ["- Sin hallazgos."],
        slugify=lambda value: str(value).replace("/", "-"),
        write_json=lambda path, payload: path.write_text(json.dumps(payload), encoding="utf-8"),
        ci_report_root=ci_report_root,
        utc_now=lambda: "2026-01-01T00:00:00+00:00",
        json_dumps=lambda obj: json.dumps(obj),
        profile_context=profile_context,
    )
    return rc, selected_root


def test_ci_spec_all_treats_draft_as_advisory(tmp_path: Path, capsys) -> None:
    spec_path = tmp_path / "specs" / "features" / "demo.spec.md"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("dummy", encoding="utf-8")

    rc = command_ci_spec(
        _args(all_specs=True),
        require_dirs=lambda: None,
        select_spec_paths=lambda *_args, **_kwargs: [spec_path],
        analyze_spec=lambda _path: _analysis_with_status("draft"),
        test_reference_findings=lambda _analysis: [],
        repos_missing_test_refs=lambda _a, _b: [],
        spec_dependency_findings=lambda _analysis: [],
        rel=lambda p: str(p),
        format_findings=lambda items: [f"- {item}" for item in items] if items else ["- Sin hallazgos."],
        slugify=lambda value: str(value).replace("/", "-"),
        write_json=lambda path, payload: path.write_text(json.dumps(payload), encoding="utf-8"),
        ci_report_root=tmp_path,
        utc_now=lambda: "2026-01-01T00:00:00+00:00",
        json_dumps=lambda obj: json.dumps(obj),
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["items"][0]["status"] == "skipped"
    assert any("modo `--all` o `--changed`" in str(item) for item in payload["items"][0]["findings"])


def test_ci_spec_changed_treats_draft_as_skipped(tmp_path: Path, capsys) -> None:
    spec_path = tmp_path / "specs" / "features" / "demo.spec.md"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("dummy", encoding="utf-8")

    rc = command_ci_spec(
        _args(all_specs=False, changed=True),
        require_dirs=lambda: None,
        select_spec_paths=lambda *_args, **_kwargs: [spec_path],
        analyze_spec=lambda _path: _analysis_with_status("draft"),
        test_reference_findings=lambda _analysis: [],
        repos_missing_test_refs=lambda _a, _b: [],
        spec_dependency_findings=lambda _analysis: [],
        rel=lambda p: str(p),
        format_findings=lambda items: [f"- {item}" for item in items] if items else ["- Sin hallazgos."],
        slugify=lambda value: str(value).replace("/", "-"),
        write_json=lambda path, payload: path.write_text(json.dumps(payload), encoding="utf-8"),
        ci_report_root=tmp_path,
        utc_now=lambda: "2026-01-01T00:00:00+00:00",
        json_dumps=lambda obj: json.dumps(obj),
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["items"][0]["status"] == "skipped"


def test_ci_spec_single_still_fails_draft(tmp_path: Path, capsys) -> None:
    spec_path = tmp_path / "specs" / "features" / "demo.spec.md"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("dummy", encoding="utf-8")

    rc = command_ci_spec(
        _args(all_specs=False),
        require_dirs=lambda: None,
        select_spec_paths=lambda *_args, **_kwargs: [spec_path],
        analyze_spec=lambda _path: _analysis_with_status("draft"),
        test_reference_findings=lambda _analysis: [],
        repos_missing_test_refs=lambda _a, _b: [],
        spec_dependency_findings=lambda _analysis: [],
        rel=lambda p: str(p),
        format_findings=lambda items: [f"- {item}" for item in items] if items else ["- Sin hallazgos."],
        slugify=lambda value: str(value).replace("/", "-"),
        write_json=lambda path, payload: path.write_text(json.dumps(payload), encoding="utf-8"),
        ci_report_root=tmp_path,
        utc_now=lambda: "2026-01-01T00:00:00+00:00",
        json_dumps=lambda obj: json.dumps(obj),
    )
    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["items"][0]["status"] == "failed"
    assert any("estado `approved`" in str(item) for item in payload["items"][0]["findings"])


def test_ci_spec_all_accepts_released(tmp_path: Path, capsys) -> None:
    spec_path = tmp_path / "specs" / "features" / "demo.spec.md"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("dummy", encoding="utf-8")

    rc = command_ci_spec(
        _args(all_specs=True),
        require_dirs=lambda: None,
        select_spec_paths=lambda *_args, **_kwargs: [spec_path],
        analyze_spec=lambda _path: _analysis_with_status("released"),
        test_reference_findings=lambda _analysis: [],
        repos_missing_test_refs=lambda _a, _b: [],
        spec_dependency_findings=lambda _analysis: [],
        rel=lambda p: str(p),
        format_findings=lambda items: [f"- {item}" for item in items] if items else ["- Sin hallazgos."],
        slugify=lambda value: str(value).replace("/", "-"),
        write_json=lambda path, payload: path.write_text(json.dumps(payload), encoding="utf-8"),
        ci_report_root=tmp_path,
        utc_now=lambda: "2026-01-01T00:00:00+00:00",
        json_dumps=lambda obj: json.dumps(obj),
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["items"][0]["status"] == "passed"


def test_ci_spec_plg_profile_routes_reports_to_profile_ci_root(tmp_path: Path, capsys) -> None:
    default_ci_root = tmp_path / ".flow" / "reports" / "ci"
    plg_ci_root = tmp_path / ".flow" / "reports" / "ci" / "plg"
    profile = _profile_context(tmp_path, profile_id="plg", ci_reports=plg_ci_root)

    assert resolve_ci_report_root(default_ci_root, profile_context=profile) == plg_ci_root

    rc, selected_root = _run_ci_spec(
        tmp_path=tmp_path,
        ci_report_root=default_ci_root,
        profile_context=profile,
    )
    assert rc == 0
    assert selected_root == plg_ci_root
    assert (plg_ci_root / "spec-all.json").is_file()
    assert (plg_ci_root / "spec-all.md").is_file()
    assert not (default_ci_root / "spec-all.json").exists()

    payload = json.loads(capsys.readouterr().out)
    assert payload["json_report"] == str(plg_ci_root / "spec-all.json")
    assert payload["markdown_report"] == str(plg_ci_root / "spec-all.md")


def test_ci_spec_without_profile_keeps_default_ci_report_root(tmp_path: Path, capsys) -> None:
    default_ci_root = tmp_path / ".flow" / "reports" / "ci"
    plg_ci_root = tmp_path / ".flow" / "reports" / "ci" / "plg"
    inactive = _profile_context(tmp_path, profile_id="", ci_reports=plg_ci_root)

    assert resolve_ci_report_root(default_ci_root, profile_context=None) == default_ci_root
    assert resolve_ci_report_root(default_ci_root, profile_context=inactive) == default_ci_root

    rc, selected_root = _run_ci_spec(
        tmp_path=tmp_path,
        ci_report_root=default_ci_root,
        profile_context=None,
    )
    assert rc == 0
    assert selected_root == default_ci_root
    assert (default_ci_root / "spec-all.json").is_file()
    assert (default_ci_root / "spec-all.md").is_file()
    assert not (plg_ci_root / "spec-all.json").exists()

    payload = json.loads(capsys.readouterr().out)
    assert payload["json_report"] == str(default_ci_root / "spec-all.json")
    assert payload["markdown_report"] == str(default_ci_root / "spec-all.md")
