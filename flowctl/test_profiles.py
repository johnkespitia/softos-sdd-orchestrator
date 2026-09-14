from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from flowctl.profiles import (
    artifact_candidates,
    default_deliverable_roots,
    first_existing_path,
    resolve_profile_context,
)


def _write_profile(root: Path, profile_id: str, *, spec_roots: list[str], deliverables: dict[str, str]) -> None:
    profiles_dir = root / "profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "id": profile_id,
        "name": profile_id.upper(),
        "spec_roots": spec_roots,
        "deliverables": deliverables,
    }
    (profiles_dir / f"{profile_id}.json").write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )


def _plg_deliverables() -> dict[str, str]:
    return {
        "plans": ".flow/plans/plg",
        "reports": ".flow/reports/plg",
        "ci_reports": ".flow/reports/ci/plg",
        "evidence": ".flow/evidence/plg",
        "runs": ".flow/runs/plg",
        "state": ".flow/state/plg",
    }


class ProfileResolverTests(unittest.TestCase):
    def test_explicit_profile_selection_overrides_spec_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_profile(
                root,
                "plg",
                spec_roots=["specs/features/plg"],
                deliverables=_plg_deliverables(),
            )
            _write_profile(
                root,
                "ops",
                spec_roots=["specs/features/ops"],
                deliverables={
                    "plans": ".flow/plans/ops",
                    "reports": ".flow/reports/ops",
                    "ci_reports": ".flow/reports/ci/ops",
                    "evidence": ".flow/evidence/ops",
                    "runs": ".flow/runs/ops",
                    "state": ".flow/state/ops",
                },
            )
            # Spec under plg roots, but explicit --profile ops wins.
            spec_path = root / "specs" / "features" / "plg" / "sample.spec.md"
            spec_path.parent.mkdir(parents=True)
            spec_path.write_text("# sample\n", encoding="utf-8")

            context = resolve_profile_context(
                root=root,
                spec_path=spec_path,
                explicit_profile="ops",
            )

            self.assertEqual("ops", context.profile_id)
            self.assertTrue(context.active)
            self.assertEqual(root / ".flow" / "plans" / "ops", context.write_roots["plans"])
            self.assertEqual(
                [root / ".flow" / "plans" / "ops", root / ".flow" / "plans"],
                context.read_roots["plans"],
            )

    def test_spec_root_auto_detection_selects_plg(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_profile(
                root,
                "plg",
                spec_roots=["specs/features/plg"],
                deliverables=_plg_deliverables(),
            )
            spec_path = root / "specs" / "features" / "plg" / "demo.spec.md"
            spec_path.parent.mkdir(parents=True)
            spec_path.write_text("# demo\n", encoding="utf-8")

            context = resolve_profile_context(
                root=root,
                spec_path=spec_path,
                explicit_profile=None,
            )

            self.assertEqual("plg", context.profile_id)
            self.assertEqual(root / ".flow" / "plans" / "plg", context.write_roots["plans"])
            self.assertEqual(root / ".flow" / "reports" / "plg", context.write_roots["reports"])
            self.assertEqual(root / ".flow" / "reports" / "ci" / "plg", context.write_roots["ci_reports"])
            self.assertEqual(root / ".flow" / "evidence" / "plg", context.write_roots["evidence"])
            defaults = default_deliverable_roots(root)
            self.assertEqual(defaults["plans"], context.default_roots["plans"])
            self.assertEqual(
                [root / ".flow" / "plans" / "plg", defaults["plans"]],
                context.read_roots["plans"],
            )

    def test_non_plg_fallback_uses_default_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_profile(
                root,
                "plg",
                spec_roots=["specs/features/plg"],
                deliverables=_plg_deliverables(),
            )
            spec_path = root / "specs" / "features" / "softos-sample.spec.md"
            spec_path.parent.mkdir(parents=True)
            spec_path.write_text("# softos\n", encoding="utf-8")
            defaults = default_deliverable_roots(root)

            context = resolve_profile_context(
                root=root,
                spec_path=spec_path,
                explicit_profile=None,
            )

            self.assertEqual("", context.profile_id)
            self.assertFalse(context.active)
            self.assertEqual(defaults, context.write_roots)
            self.assertEqual(defaults, context.default_roots)
            for key, default_root in defaults.items():
                self.assertEqual([default_root], context.read_roots[key])

    def test_ambiguity_failure_requires_explicit_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_profile(
                root,
                "plg",
                spec_roots=["specs/features/plg"],
                deliverables=_plg_deliverables(),
            )
            _write_profile(
                root,
                "plg-extra",
                spec_roots=["specs/features/plg"],
                deliverables={
                    "plans": ".flow/plans/plg-extra",
                    "reports": ".flow/reports/plg-extra",
                    "ci_reports": ".flow/reports/ci/plg-extra",
                    "evidence": ".flow/evidence/plg-extra",
                    "runs": ".flow/runs/plg-extra",
                    "state": ".flow/state/plg-extra",
                },
            )
            spec_path = root / "specs" / "features" / "plg" / "overlap.spec.md"
            spec_path.parent.mkdir(parents=True)
            spec_path.write_text("# overlap\n", encoding="utf-8")

            with self.assertRaises(ValueError) as raised:
                resolve_profile_context(
                    root=root,
                    spec_path=spec_path,
                    explicit_profile=None,
                )

            message = str(raised.exception)
            self.assertIn("multiple profiles", message)
            self.assertIn("--profile", message)

    def test_profile_first_legacy_candidate_ordering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_profile(
                root,
                "plg",
                spec_roots=["specs/features/plg"],
                deliverables=_plg_deliverables(),
            )
            spec_path = root / "specs" / "features" / "plg" / "routing.spec.md"
            spec_path.parent.mkdir(parents=True)
            spec_path.write_text("# routing\n", encoding="utf-8")

            context = resolve_profile_context(
                root=root,
                spec_path=spec_path,
                explicit_profile=None,
            )
            candidates = artifact_candidates(context.read_roots["plans"], "routing.json")
            profile_plan = root / ".flow" / "plans" / "plg" / "routing.json"
            legacy_plan = root / ".flow" / "plans" / "routing.json"
            self.assertEqual([profile_plan, legacy_plan], candidates)

            # Prefer profile-scoped artifact when both exist.
            profile_plan.parent.mkdir(parents=True, exist_ok=True)
            legacy_plan.parent.mkdir(parents=True, exist_ok=True)
            profile_plan.write_text('{"source":"profile"}\n', encoding="utf-8")
            legacy_plan.write_text('{"source":"legacy"}\n', encoding="utf-8")
            self.assertEqual(profile_plan, first_existing_path(candidates))

            # Fall back to legacy when profile artifact is absent.
            profile_plan.unlink()
            self.assertEqual(legacy_plan, first_existing_path(candidates))

            # When neither exists, keep profile-first candidate as the default path.
            legacy_plan.unlink()
            self.assertEqual(profile_plan, first_existing_path(candidates))


if __name__ == "__main__":
    unittest.main()
