from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pytest

from flowctl.features import command_plan, command_slice_start, file_sha256, load_plan_and_slice
from flowctl.specs import (
    SpecConfig,
    analyze_spec,
    build_spec_config,
    require_routed_paths,
    slice_governance_findings,
)
from flowctl.workflows import command_workflow_next_step


def _config(tmp_path: Path) -> SpecConfig:
    return build_spec_config(
        root=tmp_path,
        specs_root=tmp_path / "specs",
        feature_specs=tmp_path / "specs" / "features",
        root_repo="root",
        default_targets={"root": ["../../specs/**"], "api": ["../../api/app/**", "../../api/tests/**"]},
        repo_prefixes={"api": "../../api/", "root": "../../"},
        target_roots={"root": {"specs"}, "api": {"app", "tests"}},
        test_required_roots={"root": set(), "api": {"app", "tests"}},
        test_hints={"api": "../../api/tests/**"},
        required_frontmatter_fields=("name", "description", "status", "targets"),
        test_ref_re=re.compile(r"\[@test\]\s+([^\s`]+)"),
        todo_re=re.compile(r"\bTODO\b"),
    )


def _write_spec(tmp_path: Path, body: str) -> Path:
    spec_path = tmp_path / "specs" / "features" / "demo.spec.md"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(body, encoding="utf-8")
    return spec_path


def test_slice_breakdown_supports_multi_slice_plan(tmp_path: Path) -> None:
    config = _config(tmp_path)
    spec_path = _write_spec(
        tmp_path,
        """---
schema_version: 3
name: demo
description: demo
status: approved
owner: platform
single_slice_reason: ""
multi_domain: false
phases: []
depends_on: []
required_runtimes: []
required_services: []
required_capabilities: []
stack_projects: []
stack_services: []
stack_capabilities: []
targets:
  - ../../api/app/controllers/**
  - ../../api/app/services/**
---

# demo

## Slice Breakdown

```yaml
- name: api-controller
  targets:
    - ../../api/app/controllers/**
  hot_area: api/controllers
  depends_on: []
- name: api-service
  targets:
    - ../../api/app/services/**
  hot_area: api/services
  depends_on:
    - api-controller
```
""",
    )

    analysis = analyze_spec(spec_path, config=config)

    assert len(analysis["slice_breakdown"]) == 2
    assert analysis["slice_breakdown"][1]["depends_on"] == ["api-controller"]
    assert slice_governance_findings(analysis) == []


def test_slice_governance_requires_exception_for_single_slice(tmp_path: Path) -> None:
    config = _config(tmp_path)
    spec_path = _write_spec(
        tmp_path,
        """---
schema_version: 3
name: demo
description: demo
status: approved
owner: platform
single_slice_reason: ""
multi_domain: true
phases:
  - foundation
  - rollout
depends_on: []
required_runtimes: []
required_services: []
required_capabilities: []
stack_projects: []
stack_services: []
stack_capabilities: []
targets:
  - ../../api/app/controllers/**
---

# demo

## Slice Breakdown

```yaml
- name: api-main
  targets:
    - ../../api/app/controllers/**
  hot_area: api/controllers
  depends_on: []
```
""",
    )

    analysis = analyze_spec(spec_path, config=config)
    findings = slice_governance_findings(analysis)

    assert any("single_slice_reason" in item for item in findings)
    assert any("al menos `3`" in item or "al menos `2`" in item for item in findings)


def test_command_plan_materializes_declared_slices(tmp_path: Path) -> None:
    config = _config(tmp_path)
    spec_path = _write_spec(
        tmp_path,
        """---
schema_version: 3
name: demo
description: demo
status: approved
owner: platform
single_slice_reason: ""
multi_domain: false
phases: []
depends_on: []
required_runtimes: []
required_services: []
required_capabilities: []
stack_projects: []
stack_services: []
stack_capabilities: []
targets:
  - ../../api/app/controllers/**
  - ../../api/app/services/**
---

# demo

## Slice Breakdown

```yaml
- name: api-controller
  targets:
    - ../../api/app/controllers/**
  hot_area: api/controllers
  depends_on: []
- name: api-service
  targets:
    - ../../api/app/services/**
  hot_area: api/services
  depends_on:
    - api-controller
```
""",
    )
    (tmp_path / "api").mkdir(parents=True, exist_ok=True)
    plan_root = tmp_path / ".flow" / "plans"
    worktree_root = tmp_path / ".worktrees"
    state: dict[str, object] = {}

    rc = command_plan(
        argparse.Namespace(spec="demo"),
        require_dirs=lambda: plan_root.mkdir(parents=True, exist_ok=True),
        resolve_spec=lambda _spec: spec_path,
        spec_slug=lambda _path: "demo",
        analyze_spec=lambda path: analyze_spec(path, config=config),
        require_routed_paths=lambda paths, label: require_routed_paths(paths, label, config=config),
        repo_slice_prefix=lambda repo: repo,
        repo_root=lambda repo: tmp_path / repo,
        worktree_root=worktree_root,
        plan_root=plan_root,
        read_state=lambda _slug: state.copy(),
        write_state=lambda _slug, payload: state.update(payload),
        ensure_remote_claim_for_plan=None,
        rel=lambda path: str(path),
        utc_now=lambda: "2026-03-29T00:00:00+00:00",
    )

    assert rc == 0
    payload = json.loads((plan_root / "demo.json").read_text(encoding="utf-8"))
    assert [item["name"] for item in payload["slices"]] == ["api-controller", "api-service"]
    assert payload["slices"][0]["hot_area"] == "api/controllers"
    assert payload["slices"][1]["depends_on"] == ["api-controller"]


def test_slice_governance_requires_closeout_contract_for_verification_only(tmp_path: Path) -> None:
    config = _config(tmp_path)
    spec_path = _write_spec(
        tmp_path,
        """---
schema_version: 3
name: demo
description: demo
status: approved
owner: platform
single_slice_reason: narrow verification slice
multi_domain: false
phases: []
depends_on: []
required_runtimes: []
required_services: []
required_capabilities: []
stack_projects: []
stack_services: []
stack_capabilities: []
targets:
  - ../../api/tests/**
---

# demo

## Slice Breakdown

```yaml
- name: verify-contract
  targets:
    - ../../api/tests/**
  hot_area: api/tests
  slice_mode: verification-only
  surface_policy: forbidden
  depends_on: []
```
""",
    )

    analysis = analyze_spec(spec_path, config=config)
    findings = slice_governance_findings(analysis)

    assert any("minimum_valid_completion" in item for item in findings)
    assert any("validated_noop_allowed" in item for item in findings)
    assert any("acceptable_evidence" in item for item in findings)


def test_slice_start_handoff_includes_compliance_closeout_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _config(tmp_path)
    spec_path = _write_spec(
        tmp_path,
        """---
schema_version: 3
name: demo
description: demo
status: approved
owner: platform
single_slice_reason: narrow enforcement slice
multi_domain: false
phases: []
depends_on: []
required_runtimes: []
required_services: []
required_capabilities: []
stack_projects: []
stack_services: []
stack_capabilities: []
targets:
  - ../../api/tests/**
---

# demo

## Slice Breakdown

```yaml
- name: verify-contract
  targets:
    - ../../api/tests/**
  hot_area: api/tests
  slice_mode: enforcement
  surface_policy: forbidden
  minimum_valid_completion: Add contract checks without opening new endpoints.
  validated_noop_allowed: true
  acceptable_evidence:
    - python3 ./flow slice verify demo verify-contract --json
    - contract verification
  depends_on: []
```
""",
    )
    (tmp_path / "api").mkdir(parents=True, exist_ok=True)
    plan_root = tmp_path / ".flow" / "plans"
    report_root = tmp_path / ".flow" / "reports"
    worktree_root = tmp_path / ".worktrees"
    state: dict[str, object] = {}

    rc = command_plan(
        argparse.Namespace(spec="demo"),
        require_dirs=lambda: plan_root.mkdir(parents=True, exist_ok=True),
        resolve_spec=lambda _spec: spec_path,
        spec_slug=lambda _path: "demo",
        analyze_spec=lambda path: analyze_spec(path, config=config),
        require_routed_paths=lambda paths, label: require_routed_paths(paths, label, config=config),
        repo_slice_prefix=lambda repo: repo,
        repo_root=lambda repo: tmp_path / repo,
        worktree_root=worktree_root,
        plan_root=plan_root,
        read_state=lambda _slug: state.copy(),
        write_state=lambda _slug, payload: state.update(payload),
        ensure_remote_claim_for_plan=None,
        rel=lambda path: str(path),
        utc_now=lambda: "2026-03-29T00:00:00+00:00",
    )

    assert rc == 0
    payload = json.loads((plan_root / "demo.json").read_text(encoding="utf-8"))
    assert payload["slices"][0]["executor_mode"] == "compliance-closeout"
    assert payload["slices"][0]["surface_policy"] == "forbidden"
    state["last_approval"] = {
        "spec_hash": file_sha256(spec_path),
        "spec_mtime_ns": spec_path.stat().st_mtime_ns,
    }
    state["plan_approval"] = {
        "status": "approved",
        "spec_hash": file_sha256(spec_path),
        "plan_hash": file_sha256(plan_root / "demo.json"),
        "plan_json": str(plan_root / "demo.json"),
    }

    report_root.mkdir(parents=True, exist_ok=True)

    class _Completed:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr("flowctl.features.subprocess.run", lambda *args, **kwargs: _Completed())

    rc = command_slice_start(
        argparse.Namespace(spec="demo", slice="verify-contract"),
        slugify=lambda value: value,
        load_plan_and_slice=lambda slug, slice_name: load_plan_and_slice(
            slug,
            slice_name,
            plan_root=plan_root,
            rel=lambda path: str(path),
        ),
        worktree_root=worktree_root,
        report_root=report_root,
        read_state=lambda _slug: state.copy(),
        write_state=lambda _slug, payload: state.update(payload),
        rel=lambda path: str(path),
    )

    assert rc == 0
    handoff = (report_root / "demo-verify-contract-handoff.md").read_text(encoding="utf-8")
    assert "Executor mode: `compliance-closeout`" in handoff
    assert "Minimum valid completion: Add contract checks without opening new endpoints." in handoff
    assert "Validated no-op allowed: `yes`" in handoff
    assert "solo reabrir alcance ante bloqueo tecnico real" in handoff
    assert f"python3 ./flow repo exec api --workdir {worktree_root / 'api-demo-verify-contract'} -- <cmd>" in handoff


@pytest.mark.parametrize(
    ("planned_runtime_root", "current_runtime_root_name"),
    [
        (Path("/workspace/coding-execution-runtime-v1-spec"), "host-runtime"),
        (Path("/home/john/workspace/softos-agentic/coding-execution-runtime-v1-spec"), "container-runtime"),
    ],
)
def test_slice_start_rebases_planned_paths_to_current_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    planned_runtime_root: Path,
    current_runtime_root_name: str,
) -> None:
    current_runtime_root = tmp_path / current_runtime_root_name
    worktree_root = current_runtime_root / ".worktrees"
    report_root = tmp_path / "reports"
    report_root.mkdir()
    planned_worktree_root = planned_runtime_root / ".worktrees"
    selected = {
        "name": "api",
        "repo": "api",
        "repo_path": str(planned_runtime_root / "api"),
        "worktree": str(planned_worktree_root / "api-demo-api"),
        "branch": "flow/demo-api",
        "owned_targets": ["../../api/app/**"],
    }
    plan = {"spec_path": "specs/features/demo.spec.md", "worktree_root": str(planned_worktree_root)}
    calls: list[list[str]] = []

    class _Completed:
        returncode = 0
        stdout = ""
        stderr = ""

    def run(command: list[str], **_kwargs: object) -> _Completed:
        calls.append(command)
        return _Completed()

    monkeypatch.setattr("flowctl.features.subprocess.run", run)

    rc = command_slice_start(
        argparse.Namespace(spec="demo", slice="api"),
        slugify=lambda value: value,
        load_plan_and_slice=lambda _slug, _slice: (plan, selected, tmp_path / ".flow/plans/demo.json"),
        worktree_root=worktree_root,
        report_root=report_root,
        read_state=lambda _slug: {},
        write_state=lambda _slug, _payload: None,
        rel=lambda path: str(path),
        policy_check=lambda **_kwargs: {"allowed": True, "blocked_reasons": [], "next_required_actions": []},
    )

    expected_repo = current_runtime_root / "api"
    expected_worktree = worktree_root / "api-demo-api"
    assert rc == 0
    assert calls == [
        [
            "git",
            "-C",
            str(expected_repo),
            "worktree",
            "add",
            "--relative-paths",
            str(expected_worktree),
            "-b",
            "flow/demo-api",
        ]
    ]
    assert "/workspace/" not in " ".join(calls[0])
    handoff = (report_root / "demo-api-handoff.md").read_text(encoding="utf-8")
    assert f"--workdir {expected_worktree} -- <cmd>" in handoff


def test_slice_start_preserves_paths_in_same_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runtime_root = tmp_path / "runtime"
    worktree_root = runtime_root / ".worktrees"
    report_root = tmp_path / "reports"
    report_root.mkdir()
    repo_path = runtime_root / "api"
    worktree = worktree_root / "api-demo-api"
    selected = {
        "name": "api",
        "repo": "api",
        "repo_path": str(repo_path),
        "worktree": str(worktree),
        "branch": "flow/demo-api",
        "owned_targets": ["../../api/app/**"],
    }
    plan = {"spec_path": "specs/features/demo.spec.md", "worktree_root": str(worktree_root)}
    calls: list[list[str]] = []

    class _Completed:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr(
        "flowctl.features.subprocess.run",
        lambda command, **_kwargs: (calls.append(command), _Completed())[1],
    )

    command_slice_start(
        argparse.Namespace(spec="demo", slice="api"),
        slugify=lambda value: value,
        load_plan_and_slice=lambda _slug, _slice: (plan, selected, tmp_path / ".flow/plans/demo.json"),
        worktree_root=worktree_root,
        report_root=report_root,
        read_state=lambda _slug: {},
        write_state=lambda _slug, _payload: None,
        rel=lambda path: str(path),
        policy_check=lambda **_kwargs: {"allowed": True, "blocked_reasons": [], "next_required_actions": []},
    )

    assert calls[0][2] == str(repo_path)
    assert calls[0][6] == str(worktree)


def test_slice_start_requires_approved_plan_before_worktree(tmp_path: Path) -> None:
    plan_root = tmp_path / ".flow" / "plans"
    report_root = tmp_path / ".flow" / "reports"
    worktree_root = tmp_path / ".worktrees"
    plan_root.mkdir(parents=True)
    spec_path = _write_spec(
        tmp_path,
        """---
schema_version: 3
name: demo
description: demo
status: approved
owner: platform
targets:
  - ../../api/app/**
---

# demo
""",
    )
    (plan_root / "demo.json").write_text(
        json.dumps(
            {
                "feature": "demo",
                "spec_path": str(spec_path),
                "slices": [
                    {
                        "name": "api",
                        "repo": "api",
                        "repo_path": str(tmp_path / "api"),
                        "worktree": str(worktree_root / "api-demo-api"),
                        "branch": "flow/demo-api",
                        "targets": ["../../api/app/**"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="missing_plan_approval"):
        command_slice_start(
            argparse.Namespace(spec="demo", slice="api"),
            slugify=lambda value: value,
            load_plan_and_slice=lambda slug, slice_name: load_plan_and_slice(
                slug,
                slice_name,
                plan_root=plan_root,
                rel=lambda path: str(path),
            ),
            worktree_root=worktree_root,
            report_root=report_root,
            read_state=lambda _slug: {},
            write_state=lambda _slug, payload: None,
            rel=lambda path: str(path),
        )

    assert not worktree_root.exists()


def test_slice_start_uses_injected_policy_before_worktree(tmp_path: Path) -> None:
    plan_root = tmp_path / ".flow" / "plans"
    report_root = tmp_path / ".flow" / "reports"
    worktree_root = tmp_path / ".worktrees"
    plan_root.mkdir(parents=True)
    spec_path = _write_spec(tmp_path, "# demo\n")
    (plan_root / "demo.json").write_text(
        json.dumps(
            {
                "feature": "demo",
                "spec_path": str(spec_path),
                "slices": [
                    {
                        "name": "api",
                        "repo": "api",
                        "repo_path": str(tmp_path / "api"),
                        "worktree": str(worktree_root / "api-demo-api"),
                        "branch": "flow/demo-api",
                        "targets": ["../../api/app/**"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    def deny_policy(**_kwargs: object) -> dict[str, object]:
        return {
            "allowed": False,
            "blocked_reasons": ["spec_approval:missing_approval"],
            "next_required_actions": ["python3 ./flow spec approve demo"],
        }

    with pytest.raises(SystemExit, match="Policy bloqueo `slice start`"):
        command_slice_start(
            argparse.Namespace(spec="demo", slice="api"),
            slugify=lambda value: value,
            load_plan_and_slice=lambda slug, slice_name: load_plan_and_slice(
                slug,
                slice_name,
                plan_root=plan_root,
                rel=lambda path: str(path),
            ),
            worktree_root=worktree_root,
            report_root=report_root,
            read_state=lambda _slug: {},
            write_state=lambda _slug, payload: None,
            rel=lambda path: str(path),
            policy_check=deny_policy,
        )

    assert not worktree_root.exists()


def test_workflow_next_step_blocks_invalid_slice_governance(tmp_path: Path) -> None:
    spec_path = _write_spec(tmp_path, "# demo\n")
    analysis = {
        "frontmatter": {"status": "approved"},
        "schema_version": 3,
        "targets": ["../../api/app/controllers/**"],
        "target_index": {"api": [{"raw": "../../api/app/controllers/**", "relative": "app/controllers/**"}]},
        "slice_breakdown": [],
        "slice_breakdown_errors": ["Falta la seccion `## Slice Breakdown` con un bloque YAML."],
        "single_slice_reason": "",
        "multi_domain": False,
        "phases": [],
    }

    with pytest.raises(SystemExit, match="gobernanza de slices"):
        command_workflow_next_step(
            argparse.Namespace(spec="demo", json=True),
            require_dirs=lambda: None,
            workspace_config={"project": {"workflow": {"default_orchestrator": "bmad", "force_orchestrator": True}}},
            resolve_spec=lambda _spec: spec_path,
            spec_slug=lambda _path: "demo",
            analyze_spec=lambda _path: analysis,
            read_state=lambda _slug: {},
            plan_root=tmp_path / ".flow" / "plans",
            workflow_report_root=tmp_path / ".flow" / "reports" / "workflow",
            root=tmp_path,
            rel=lambda path: str(path),
            utc_now=lambda: "2026-03-29T00:00:00+00:00",
            json_dumps=json.dumps,
        )
