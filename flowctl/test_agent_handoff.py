from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from flowctl.agent_handoff import agent_handoff_payload, write_agent_handoff
from flowctl.features import file_sha256
from flowctl.profiles import ProfileContext, default_deliverable_roots


def _profile_context(
    root: Path,
    *,
    profile_id: str = "plg",
    reports: Path | None = None,
    evidence: Path | None = None,
) -> ProfileContext:
    defaults = default_deliverable_roots(root)
    write_roots = dict(defaults)
    if reports is not None:
        write_roots["reports"] = reports
    if evidence is not None:
        write_roots["evidence"] = evidence
    read_roots: dict[str, list[Path]] = {}
    for key, default_root in defaults.items():
        candidates = [write_roots[key], default_root] if profile_id else [default_root]
        unique: list[Path] = []
        seen: set[Path] = set()
        for path in candidates:
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            unique.append(path)
        read_roots[key] = unique
    return ProfileContext(
        profile_id=profile_id,
        write_roots=write_roots,
        default_roots=defaults,
        read_roots=read_roots,
    )


class AgentHandoffTests(unittest.TestCase):
    def test_agent_handoff_writes_package_and_copies_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_path = root / "specs" / "features" / "sample.spec.md"
            plan_path = root / ".flow" / "plans" / "sample.json"
            report_root = root / ".flow" / "reports"
            evidence_root = report_root / "evidence"
            handoff_root = report_root / "agent-handoffs"
            spec_path.parent.mkdir(parents=True)
            plan_path.parent.mkdir(parents=True)
            (report_root / "ci").mkdir(parents=True)
            spec_path.write_text("---\nname: Sample\nstatus: approved\n---\n# Sample\n", encoding="utf-8")
            plan_path.write_text(
                json.dumps(
                    {
                        "feature": "sample",
                        "slices": [
                            {
                                "name": "core",
                                "repo": "root",
                                "branch": "feat/sample-core",
                                "worktree": ".worktrees/root-sample-core",
                                "owned_targets": ["../../flow"],
                                "acceptable_evidence": ["python3 -m unittest flowctl.test_agent_handoff"],
                                "executor_mode": "compliance-closeout",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (report_root / "ci" / "spec-sample.json").write_text(
                json.dumps({"items": [{"spec": str(spec_path), "status": "passed"}]}),
                encoding="utf-8",
            )
            state = {
                "last_approval": {
                    "spec_hash": file_sha256(spec_path),
                    "spec_mtime_ns": spec_path.stat().st_mtime_ns,
                },
                "plan_approval": {
                    "status": "approved",
                    "spec_hash": file_sha256(spec_path),
                    "plan_hash": file_sha256(plan_path),
                    "plan_json": ".flow/plans/sample.json",
                },
            }

            payload = agent_handoff_payload(
                slug="sample",
                spec_path=spec_path,
                plan_path=plan_path,
                state=state,
                report_root=report_root,
                evidence_report_root=evidence_root,
                handoff_report_root=handoff_root,
                root=root,
                rel=lambda path: str(path.relative_to(root)),
                utc_now=lambda: "2026-04-17T00:00:00Z",
            )
            output = write_agent_handoff(payload=payload, handoff_report_root=handoff_root, rel=lambda path: str(path.relative_to(root)))

            self.assertTrue(output["ready_for_agent"])
            self.assertEqual([], output["blocked_actions"])
            self.assertEqual("core", output["slices"][0]["name"])
            self.assertTrue((root / str(output["json_report"])).is_file())
            self.assertTrue((root / str(output["markdown_report"])).is_file())
            self.assertTrue((handoff_root / "sample" / spec_path.name).is_file())
            self.assertTrue((handoff_root / "sample" / plan_path.name).is_file())

    def test_agent_handoff_reports_blockers_when_evidence_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_path = root / "specs" / "features" / "sample.spec.md"
            plan_path = root / ".flow" / "plans" / "sample.json"
            spec_path.parent.mkdir(parents=True)
            plan_path.parent.mkdir(parents=True)
            spec_path.write_text("---\nname: Sample\nstatus: draft\n---\n# Sample\n", encoding="utf-8")
            plan_path.write_text('{"feature":"sample","slices":[]}\n', encoding="utf-8")

            payload = agent_handoff_payload(
                slug="sample",
                spec_path=spec_path,
                plan_path=plan_path,
                state={},
                report_root=root / ".flow" / "reports",
                evidence_report_root=root / ".flow" / "reports" / "evidence",
                handoff_report_root=root / ".flow" / "reports" / "agent-handoffs",
                root=root,
                rel=lambda path: str(path.relative_to(root)),
                utc_now=lambda: "2026-04-17T00:00:00Z",
            )

            self.assertFalse(payload["ready_for_agent"])
            self.assertIn("spec_approval", payload["blocked_actions"])
            self.assertIn("plan_approval", payload["blocked_actions"])
            self.assertTrue(payload["next_commands"][0].startswith("python3 ./flow spec approve"))
            self.assertTrue(payload["next_commands"][1].startswith("python3 ./flow plan-approve"))

    def test_agent_handoff_propagates_profile_context_to_evidence_bundle_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_path = root / "specs" / "features" / "sample.spec.md"
            plan_path = root / ".flow" / "plans" / "sample.json"
            report_root = root / ".flow" / "reports"
            legacy_evidence = report_root / "evidence"
            profile_evidence = root / ".flow" / "evidence" / "plg"
            profile_reports = report_root / "plg"
            handoff_root = report_root / "agent-handoffs"
            spec_path.parent.mkdir(parents=True)
            plan_path.parent.mkdir(parents=True)
            (profile_reports / "ci").mkdir(parents=True)
            spec_path.write_text("---\nname: Sample\nstatus: approved\n---\n# Sample\n", encoding="utf-8")
            plan_path.write_text('{"feature":"sample","slices":[]}\n', encoding="utf-8")
            (profile_reports / "ci" / "spec-sample.json").write_text(
                json.dumps({"items": [{"spec": str(spec_path), "status": "passed"}]}),
                encoding="utf-8",
            )
            context = _profile_context(
                root,
                reports=profile_reports,
                evidence=profile_evidence,
            )
            state = {
                "last_approval": {
                    "spec_hash": file_sha256(spec_path),
                    "spec_mtime_ns": spec_path.stat().st_mtime_ns,
                },
                "plan_approval": {
                    "status": "approved",
                    "spec_hash": file_sha256(spec_path),
                    "plan_hash": file_sha256(plan_path),
                    "plan_json": ".flow/plans/sample.json",
                },
            }

            payload = agent_handoff_payload(
                slug="sample",
                spec_path=spec_path,
                plan_path=plan_path,
                state=state,
                report_root=report_root,
                evidence_report_root=legacy_evidence,
                handoff_report_root=handoff_root,
                root=root,
                rel=lambda path: str(path.relative_to(root)),
                utc_now=lambda: "2026-04-17T00:00:00Z",
                profile_context=context,
            )

            bundle = payload["execution_contract"]["evidence_bundle"]
            self.assertIsInstance(bundle, dict)
            self.assertEqual(
                ".flow/evidence/plg/sample-evidence-bundle.json",
                bundle["json_report"],
            )
            self.assertTrue((profile_evidence / "sample-evidence-bundle.json").is_file())
            self.assertFalse((legacy_evidence / "sample-evidence-bundle.json").exists())
            self.assertEqual(1, len(payload["evidence"]["reports"]))
            self.assertEqual(
                ".flow/reports/plg/ci/spec-sample.json",
                payload["evidence"]["reports"][0]["path"],
            )

    def test_agent_handoff_propagates_explicit_report_read_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_path = root / "specs" / "features" / "sample.spec.md"
            plan_path = root / ".flow" / "plans" / "sample.json"
            report_root = root / ".flow" / "reports"
            profile_reports = root / ".flow" / "reports" / "plg"
            evidence_root = report_root / "evidence"
            handoff_root = report_root / "agent-handoffs"
            spec_path.parent.mkdir(parents=True)
            plan_path.parent.mkdir(parents=True)
            (profile_reports / "ci").mkdir(parents=True)
            (report_root / "ci").mkdir(parents=True)
            spec_path.write_text("---\nname: Sample\nstatus: draft\n---\n# Sample\n", encoding="utf-8")
            plan_path.write_text('{"feature":"sample","slices":[]}\n', encoding="utf-8")
            (profile_reports / "ci" / "spec-sample.json").write_text(
                json.dumps({"status": "passed", "source": "profile"}),
                encoding="utf-8",
            )
            (report_root / "ci" / "workflow-sample.json").write_text(
                json.dumps({"status": "passed", "source": "legacy"}),
                encoding="utf-8",
            )

            payload = agent_handoff_payload(
                slug="sample",
                spec_path=spec_path,
                plan_path=plan_path,
                state={},
                report_root=report_root,
                evidence_report_root=evidence_root,
                handoff_report_root=handoff_root,
                root=root,
                rel=lambda path: str(path.relative_to(root)),
                utc_now=lambda: "2026-04-17T00:00:00Z",
                report_read_roots=[profile_reports, report_root],
            )

            paths = {item["path"] for item in payload["evidence"]["reports"]}
            self.assertIn(".flow/reports/plg/ci/spec-sample.json", paths)
            self.assertIn(".flow/reports/ci/workflow-sample.json", paths)
            # Nested profile file must not appear twice via legacy scan.
            self.assertEqual(2, len(payload["evidence"]["reports"]))


if __name__ == "__main__":
    unittest.main()
