from __future__ import annotations

import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from flowctl.features import command_plan_approval_status, command_plan_approve, file_sha256


def _json_dumps(payload: object) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=True)


class PlanApprovalGateTests(unittest.TestCase):
    def test_plan_approve_requires_current_spec_approval_and_records_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_path = root / "sample.spec.md"
            plan_root = root / ".flow" / "plans"
            plan_root.mkdir(parents=True)
            plan_path = plan_root / "sample.json"
            spec_path.write_text("---\nname: Sample\nstatus: approved\n---\n# Sample\n", encoding="utf-8")
            plan_path.write_text('{"feature":"sample","slices":[]}\n', encoding="utf-8")
            state: dict[str, object] = {
                "last_approval": {
                    "spec_hash": file_sha256(spec_path),
                    "spec_mtime_ns": spec_path.stat().st_mtime_ns,
                }
            }

            rc = command_plan_approve(
                Namespace(spec="sample", approver="john"),
                resolve_spec=lambda _spec: spec_path,
                spec_slug=lambda _path: "sample",
                plan_root=plan_root,
                read_state=lambda _slug: state,
                write_state=lambda _slug, payload: state.update(payload),
                rel=lambda path: str(path.relative_to(root)),
                utc_now=lambda: "2026-04-16T00:00:00Z",
            )

            self.assertEqual(0, rc)
            approval = state["plan_approval"]
            self.assertIsInstance(approval, dict)
            self.assertEqual(file_sha256(spec_path), approval["spec_hash"])
            self.assertEqual(file_sha256(plan_path), approval["plan_hash"])

    def test_plan_approval_status_invalidates_when_plan_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_path = root / "sample.spec.md"
            plan_root = root / ".flow" / "plans"
            plan_root.mkdir(parents=True)
            plan_path = plan_root / "sample.json"
            spec_path.write_text("---\nname: Sample\nstatus: approved\n---\n# Sample\n", encoding="utf-8")
            plan_path.write_text('{"feature":"sample","slices":[]}\n', encoding="utf-8")
            state = {
                "plan_approval": {
                    "status": "approved",
                    "spec_hash": file_sha256(spec_path),
                    "plan_hash": file_sha256(plan_path),
                }
            }
            plan_path.write_text('{"feature":"sample","slices":[{"name":"changed"}]}\n', encoding="utf-8")
            captured: dict[str, object] = {}

            def capture(payload: object) -> str:
                self.assertIsInstance(payload, dict)
                captured.update(payload)
                return _json_dumps(payload)

            rc = command_plan_approval_status(
                Namespace(spec="sample", json=True),
                resolve_spec=lambda _spec: spec_path,
                spec_slug=lambda _path: "sample",
                plan_root=plan_root,
                read_state=lambda _slug: state,
                rel=lambda path: str(path.relative_to(root)),
                json_dumps=capture,
            )

            self.assertEqual(0, rc)
            self.assertFalse(captured["approved"])
            self.assertIn("plan_hash_changed", captured["invalid_reasons"])

    def test_plan_approval_status_prefers_profile_plan_when_both_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_path = root / "sample.spec.md"
            legacy_root = root / ".flow" / "plans"
            profile_root = root / ".flow" / "plans" / "plg"
            legacy_root.mkdir(parents=True)
            profile_root.mkdir(parents=True)
            profile_plan = profile_root / "sample.json"
            legacy_plan = legacy_root / "sample.json"
            spec_path.write_text("---\nname: Sample\nstatus: approved\n---\n# Sample\n", encoding="utf-8")
            profile_plan.write_text('{"feature":"sample","source":"profile","slices":[]}\n', encoding="utf-8")
            legacy_plan.write_text('{"feature":"sample","source":"legacy","slices":[]}\n', encoding="utf-8")
            captured: dict[str, object] = {}

            def capture(payload: object) -> str:
                self.assertIsInstance(payload, dict)
                captured.update(payload)
                return _json_dumps(payload)

            rc = command_plan_approval_status(
                Namespace(spec="sample", json=True),
                resolve_spec=lambda _spec: spec_path,
                spec_slug=lambda _path: "sample",
                plan_root=legacy_root,
                plan_read_roots=[profile_root, legacy_root],
                read_state=lambda _slug: {},
                rel=lambda path: str(path.relative_to(root)),
                json_dumps=capture,
            )

            self.assertEqual(0, rc)
            self.assertEqual(".flow/plans/plg/sample.json", captured["plan_path"])
            self.assertEqual(file_sha256(profile_plan), captured["current_plan_hash"])
            self.assertNotIn("missing_plan", captured["invalid_reasons"])

    def test_plan_approval_status_falls_back_to_legacy_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_path = root / "sample.spec.md"
            legacy_root = root / ".flow" / "plans"
            profile_root = root / ".flow" / "plans" / "plg"
            legacy_root.mkdir(parents=True)
            profile_root.mkdir(parents=True)
            legacy_plan = legacy_root / "sample.json"
            spec_path.write_text("---\nname: Sample\nstatus: approved\n---\n# Sample\n", encoding="utf-8")
            legacy_plan.write_text('{"feature":"sample","source":"legacy","slices":[]}\n', encoding="utf-8")
            captured: dict[str, object] = {}

            def capture(payload: object) -> str:
                self.assertIsInstance(payload, dict)
                captured.update(payload)
                return _json_dumps(payload)

            rc = command_plan_approval_status(
                Namespace(spec="sample", json=True),
                resolve_spec=lambda _spec: spec_path,
                spec_slug=lambda _path: "sample",
                plan_root=legacy_root,
                plan_read_roots=[profile_root, legacy_root],
                read_state=lambda _slug: {},
                rel=lambda path: str(path.relative_to(root)),
                json_dumps=capture,
            )

            self.assertEqual(0, rc)
            self.assertEqual(".flow/plans/sample.json", captured["plan_path"])
            self.assertEqual(file_sha256(legacy_plan), captured["current_plan_hash"])
            self.assertNotIn("missing_plan", captured["invalid_reasons"])

    def test_plan_approve_falls_back_to_legacy_plan_and_records_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_path = root / "sample.spec.md"
            legacy_root = root / ".flow" / "plans"
            profile_root = root / ".flow" / "plans" / "plg"
            legacy_root.mkdir(parents=True)
            profile_root.mkdir(parents=True)
            legacy_plan = legacy_root / "sample.json"
            spec_path.write_text("---\nname: Sample\nstatus: approved\n---\n# Sample\n", encoding="utf-8")
            legacy_plan.write_text('{"feature":"sample","slices":[]}\n', encoding="utf-8")
            state: dict[str, object] = {
                "last_approval": {
                    "spec_hash": file_sha256(spec_path),
                    "spec_mtime_ns": spec_path.stat().st_mtime_ns,
                }
            }

            rc = command_plan_approve(
                Namespace(spec="sample", approver="john"),
                resolve_spec=lambda _spec: spec_path,
                spec_slug=lambda _path: "sample",
                plan_root=legacy_root,
                plan_read_roots=[profile_root, legacy_root],
                read_state=lambda _slug: state,
                write_state=lambda _slug, payload: state.update(payload),
                rel=lambda path: str(path.relative_to(root)),
                utc_now=lambda: "2026-04-16T00:00:00Z",
            )

            self.assertEqual(0, rc)
            approval = state["plan_approval"]
            self.assertIsInstance(approval, dict)
            self.assertEqual(".flow/plans/sample.json", approval["plan_json"])
            self.assertEqual(file_sha256(legacy_plan), approval["plan_hash"])
            self.assertEqual(".flow/plans/sample.json", state["plan_json"])

    def test_plan_approval_status_default_ignores_profile_scoped_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_path = root / "sample.spec.md"
            legacy_root = root / ".flow" / "plans"
            profile_root = root / ".flow" / "plans" / "plg"
            profile_root.mkdir(parents=True)
            profile_plan = profile_root / "sample.json"
            spec_path.write_text("---\nname: Sample\nstatus: approved\n---\n# Sample\n", encoding="utf-8")
            profile_plan.write_text('{"feature":"sample","source":"profile","slices":[]}\n', encoding="utf-8")
            captured: dict[str, object] = {}

            def capture(payload: object) -> str:
                self.assertIsInstance(payload, dict)
                captured.update(payload)
                return _json_dumps(payload)

            rc = command_plan_approval_status(
                Namespace(spec="sample", json=True),
                resolve_spec=lambda _spec: spec_path,
                spec_slug=lambda _path: "sample",
                plan_root=legacy_root,
                read_state=lambda _slug: {},
                rel=lambda path: str(path.relative_to(root)),
                json_dumps=capture,
            )

            self.assertEqual(0, rc)
            self.assertEqual(".flow/plans/sample.json", captured["plan_path"])
            self.assertIn("missing_plan", captured["invalid_reasons"])


if __name__ == "__main__":
    unittest.main()
