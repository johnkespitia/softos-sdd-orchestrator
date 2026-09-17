from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from flowctl.evidence import (
    evidence_status_payload,
    resolve_evidence_plan_path,
    resolve_evidence_report_root,
    resolve_report_scan_roots,
    write_evidence_bundle,
)
from flowctl.features import file_sha256
from flowctl.profiles import ProfileContext, default_deliverable_roots


def _profile_context(
    root: Path,
    *,
    profile_id: str = "plg",
    plans: Path | None = None,
    reports: Path | None = None,
    evidence: Path | None = None,
) -> ProfileContext:
    defaults = default_deliverable_roots(root)
    write_roots = dict(defaults)
    if plans is not None:
        write_roots["plans"] = plans
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


class EvidenceTests(unittest.TestCase):
    def test_evidence_status_reports_missing_plan_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_path = root / "specs" / "features" / "sample.spec.md"
            plan_path = root / ".flow" / "plans" / "sample.json"
            report_root = root / ".flow" / "reports"
            spec_path.parent.mkdir(parents=True)
            plan_path.parent.mkdir(parents=True)
            (report_root / "ci").mkdir(parents=True)
            (report_root / "agent-handoffs").mkdir(parents=True)
            spec_path.write_text("---\nname: Sample\nstatus: approved\n---\n# Sample\n", encoding="utf-8")
            plan_path.write_text('{"feature":"sample","slices":[]}\n', encoding="utf-8")
            (report_root / "ci" / "spec-sample.json").write_text(
                json.dumps({"items": [{"spec": str(spec_path), "status": "passed"}]}),
                encoding="utf-8",
            )
            (report_root / "agent-handoffs" / "sample-agent-handoff.json").write_text(
                json.dumps({"feature": "sample"}),
                encoding="utf-8",
            )
            state = {
                "last_approval": {
                    "spec_hash": file_sha256(spec_path),
                    "spec_mtime_ns": spec_path.stat().st_mtime_ns,
                }
            }

            payload = evidence_status_payload(
                slug="sample",
                spec_path=spec_path,
                plan_path=plan_path,
                state=state,
                report_root=report_root,
                rel=lambda path: str(path.relative_to(root)),
                utc_now=lambda: "2026-04-16T00:00:00Z",
            )

            self.assertFalse(payload["ready_for_release"])
            self.assertIn("plan_approval", payload["missing"])
            self.assertTrue(payload["ci_spec"]["passed"])
            self.assertEqual(1, len(payload["reports"]))

    def test_write_evidence_bundle_copies_matching_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report_root = root / ".flow" / "reports"
            evidence_root = report_root / "evidence"
            source = report_root / "ci" / "spec-sample.json"
            source.parent.mkdir(parents=True)
            source.write_text('{"status":"passed"}\n', encoding="utf-8")
            payload = {
                "feature": "sample",
                "ready_for_release": False,
                "missing": ["plan_approval"],
                "spec_path": "specs/features/sample.spec.md",
                "plan_path": ".flow/plans/sample.json",
                "reports": [{"path": ".flow/reports/ci/spec-sample.json", "kind": "ci", "format": "json"}],
            }

            bundle = write_evidence_bundle(
                payload=payload,
                evidence_report_root=evidence_root,
                root=root,
                rel=lambda path: str(path.relative_to(root)),
            )

            bundle_info = bundle["bundle"]
            self.assertIsInstance(bundle_info, dict)
            self.assertTrue((root / str(bundle_info["json_report"])).is_file())
            self.assertTrue((root / str(bundle_info["markdown_report"])).is_file())
            copied = root / ".flow" / "reports" / "evidence" / "sample" / "spec-sample.json"
            self.assertTrue(copied.is_file())

    def test_resolve_evidence_plan_path_prefers_profile_when_both_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy_root = root / ".flow" / "plans"
            profile_root = root / ".flow" / "plans" / "plg"
            legacy_root.mkdir(parents=True)
            profile_root.mkdir(parents=True)
            profile_plan = profile_root / "sample.json"
            legacy_plan = legacy_root / "sample.json"
            profile_plan.write_text('{"feature":"sample","source":"profile"}\n', encoding="utf-8")
            legacy_plan.write_text('{"feature":"sample","source":"legacy"}\n', encoding="utf-8")
            context = _profile_context(root, plans=profile_root)

            resolved = resolve_evidence_plan_path(
                "sample",
                plan_root=legacy_root,
                profile_context=context,
            )

            self.assertEqual(profile_plan, resolved)

    def test_resolve_evidence_plan_path_falls_back_to_legacy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy_root = root / ".flow" / "plans"
            profile_root = root / ".flow" / "plans" / "plg"
            legacy_root.mkdir(parents=True)
            profile_root.mkdir(parents=True)
            legacy_plan = legacy_root / "sample.json"
            legacy_plan.write_text('{"feature":"sample","source":"legacy"}\n', encoding="utf-8")
            context = _profile_context(root, plans=profile_root)

            resolved = resolve_evidence_plan_path(
                "sample",
                plan_root=legacy_root,
                profile_context=context,
            )

            self.assertEqual(legacy_plan, resolved)

    def test_resolve_evidence_plan_path_default_ignores_profile_scoped_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy_root = root / ".flow" / "plans"
            profile_root = root / ".flow" / "plans" / "plg"
            profile_root.mkdir(parents=True)
            profile_plan = profile_root / "sample.json"
            profile_plan.write_text('{"feature":"sample","source":"profile"}\n', encoding="utf-8")

            resolved = resolve_evidence_plan_path("sample", plan_root=legacy_root)

            self.assertEqual(legacy_root / "sample.json", resolved)
            self.assertFalse(resolved.exists())

    def test_resolve_evidence_report_root_uses_profile_write_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy_evidence = root / ".flow" / "reports" / "evidence"
            profile_evidence = root / ".flow" / "evidence" / "plg"
            context = _profile_context(root, evidence=profile_evidence)

            self.assertEqual(
                profile_evidence,
                resolve_evidence_report_root(legacy_evidence, profile_context=context),
            )

    def test_resolve_evidence_report_root_keeps_legacy_without_active_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy_evidence = root / ".flow" / "reports" / "evidence"
            profile_evidence = root / ".flow" / "evidence" / "plg"
            inactive = _profile_context(root, profile_id="", evidence=profile_evidence)

            self.assertEqual(legacy_evidence, resolve_evidence_report_root(legacy_evidence))
            self.assertEqual(
                legacy_evidence,
                resolve_evidence_report_root(legacy_evidence, profile_context=inactive),
            )

    def test_write_evidence_bundle_routes_to_profile_evidence_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy_evidence = root / ".flow" / "reports" / "evidence"
            profile_evidence = root / ".flow" / "evidence" / "plg"
            source = root / ".flow" / "reports" / "ci" / "spec-sample.json"
            source.parent.mkdir(parents=True)
            source.write_text('{"status":"passed"}\n', encoding="utf-8")
            context = _profile_context(root, evidence=profile_evidence)
            payload = {
                "feature": "sample",
                "ready_for_release": False,
                "missing": ["plan_approval"],
                "spec_path": "specs/features/sample.spec.md",
                "plan_path": ".flow/plans/sample.json",
                "reports": [{"path": ".flow/reports/ci/spec-sample.json", "kind": "ci", "format": "json"}],
            }

            bundle = write_evidence_bundle(
                payload=payload,
                evidence_report_root=legacy_evidence,
                root=root,
                rel=lambda path: str(path.relative_to(root)),
                profile_context=context,
            )

            bundle_info = bundle["bundle"]
            self.assertIsInstance(bundle_info, dict)
            self.assertEqual(
                ".flow/evidence/plg/sample-evidence-bundle.json",
                bundle_info["json_report"],
            )
            self.assertTrue((profile_evidence / "sample-evidence-bundle.json").is_file())
            self.assertTrue((profile_evidence / "sample" / "spec-sample.json").is_file())
            self.assertFalse((legacy_evidence / "sample-evidence-bundle.json").exists())

    def test_resolve_report_scan_roots_dedupes_duplicate_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report_root = root / ".flow" / "reports"
            profile_reports = root / ".flow" / "reports" / "plg"
            profile_reports.mkdir(parents=True)
            report_root.mkdir(parents=True, exist_ok=True)
            context = _profile_context(root, reports=profile_reports)

            roots = resolve_report_scan_roots(report_root, profile_context=context)
            self.assertEqual([profile_reports, report_root], roots)

            duplicated = resolve_report_scan_roots(
                report_root,
                report_read_roots=[profile_reports, report_root, profile_reports],
            )
            self.assertEqual([profile_reports, report_root], duplicated)

    def test_evidence_status_dedupes_matching_reports_across_scan_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_path = root / "specs" / "features" / "sample.spec.md"
            plan_path = root / ".flow" / "plans" / "sample.json"
            report_root = root / ".flow" / "reports"
            profile_reports = report_root / "plg"
            spec_path.parent.mkdir(parents=True)
            plan_path.parent.mkdir(parents=True)
            (profile_reports / "ci").mkdir(parents=True)
            spec_path.write_text("---\nname: Sample\nstatus: approved\n---\n# Sample\n", encoding="utf-8")
            plan_path.write_text('{"feature":"sample","slices":[]}\n', encoding="utf-8")
            report_file = profile_reports / "ci" / "spec-sample.json"
            report_file.write_text(
                json.dumps({"items": [{"spec": str(spec_path), "status": "passed"}]}),
                encoding="utf-8",
            )
            context = _profile_context(root, reports=profile_reports)
            state = {
                "last_approval": {
                    "spec_hash": file_sha256(spec_path),
                    "spec_mtime_ns": spec_path.stat().st_mtime_ns,
                }
            }

            payload = evidence_status_payload(
                slug="sample",
                spec_path=spec_path,
                plan_path=plan_path,
                state=state,
                report_root=report_root,
                rel=lambda path: str(path.relative_to(root)),
                utc_now=lambda: "2026-04-16T00:00:00Z",
                profile_context=context,
            )

            # Nested profile root under legacy reports would otherwise double-count.
            self.assertEqual(1, len(payload["reports"]))
            self.assertEqual(".flow/reports/plg/ci/spec-sample.json", payload["reports"][0]["path"])


if __name__ == "__main__":
    unittest.main()
