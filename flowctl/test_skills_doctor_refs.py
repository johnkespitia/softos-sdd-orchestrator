from __future__ import annotations

import argparse
import json
from pathlib import Path

from flowctl.skills_ops import command_skills_doctor


def _entry(name: str, *, enabled: bool = True) -> dict[str, object]:
    return {
        "name": name,
        "provider": "tessl",
        "kind": "skill",
        "source": f".agents/skills/{name}",
        "enabled": enabled,
        "required": False,
        "sync": False,
        "requires": [],
        "local_source_path": Path("."),
    }


def _run_doctor(capsys, references: list[tuple[str, str]], entries: list[dict[str, object]]):
    rc = command_skills_doctor(
        argparse.Namespace(json=True),
        load_skills_config=lambda: {"providers": {"tessl": {"enabled": True}}, "entries": []},
        skills_entries=lambda _payload: (entries, []),
        normalize_skill_provider=lambda provider: provider,
        workspace_executable_available=lambda _executable: True,
        rel=lambda path: str(path),
        skills_config_file=Path("workspace.skills.json"),
        json_dumps=lambda payload: json.dumps(payload),
        configured_skill_references=lambda: references,
    )
    return rc, json.loads(capsys.readouterr().out)


def test_skills_doctor_rejects_unknown_references(capsys) -> None:
    rc, payload = _run_doctor(capsys, [("repo `api`", "workspace/missing")], [_entry("workspace/php-core")])

    assert rc == 1
    assert payload["findings"] == ["repo `api` referencia la skill inexistente `workspace/missing`."]


def test_skills_doctor_accepts_enabled_references(capsys) -> None:
    rc, payload = _run_doctor(capsys, [("runtime `php`", "workspace/php-core")], [_entry("workspace/php-core")])

    assert rc == 0
    assert payload["findings"] == []
