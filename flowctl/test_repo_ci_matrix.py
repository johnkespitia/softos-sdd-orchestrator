from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flowctl.repo_ci_matrix import build_repo_ci_matrices, resolve_submodule_gitlink


class RepoCiMatrixTests(unittest.TestCase):
    def test_build_repo_ci_matrices_splits_generic_and_delegated(self) -> None:
        workspace_config = {
            "repos": {
                "root": {"path": ".", "kind": "root"},
                "api": {
                    "path": "projects/api",
                    "kind": "implementation",
                    "runtime": "python",
                    "ci": {
                        "mode": "workflow-dispatch",
                        "workflow": "repo-ci.yml",
                        "ref": "main",
                        "source_sha": "d" * 40,
                        "trigger_mode": "workflow_dispatch_only",
                        "inputs": {"repo": "api"},
                    },
                },
                "web": {
                    "path": "projects/web",
                    "kind": "implementation",
                    "runtime": "pnpm",
                },
            }
        }
        runtime_packs = {
            "python": {"test_runner": "pytest"},
            "pnpm": {"test_runner": "pnpm"},
            "node-npm": {"test_runner": "npm"},
        }

        payload = build_repo_ci_matrices(workspace_config, runtime_packs)
        self.assertTrue(payload["has_generic"])
        self.assertTrue(payload["has_delegated"])
        self.assertEqual(payload["generic"]["include"][0]["repo"], "web")
        self.assertEqual(payload["delegated"]["include"][0]["repo"], "api")
        self.assertEqual(payload["delegated"]["include"][0]["workflow"], "repo-ci.yml")
        self.assertEqual(payload["delegated"]["include"][0]["trigger_mode"], "workflow_dispatch_only")
        self.assertEqual(payload["delegated"]["include"][0]["workflow_ref"], "main")
        self.assertEqual(payload["delegated"]["include"][0]["source_sha"], "d" * 40)

    @patch("flowctl.repo_ci_matrix.subprocess.run")
    def test_submodule_delegated_ci_separates_workflow_ref_and_gitlink_sha(self, run_mock) -> None:
        gitlink_sha = "a" * 40
        run_mock.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=f"160000 commit {gitlink_sha}\tplg-platform-backend\n",
            stderr="",
        )
        workspace_config = {
            "repos": {
                "backend": {
                    "path": "plg-platform-backend",
                    "kind": "implementation",
                    "runtime": "php",
                    "repo_strategy": "submodule",
                    "ci": {
                        "mode": "workflow-dispatch",
                        "workflow": "repo-ci.yml",
                        "ref": "main",
                    },
                }
            }
        }

        payload = build_repo_ci_matrices(
            workspace_config,
            {},
            workspace_root=Path("/workspace"),
        )

        delegated = payload["delegated"]["include"][0]
        self.assertEqual(delegated["workflow_ref"], "main")
        self.assertEqual(delegated["source_sha"], gitlink_sha)
        run_mock.assert_called_once_with(
            ["git", "ls-tree", "HEAD", "--", "plg-platform-backend"],
            cwd=Path("/workspace"),
            check=False,
            capture_output=True,
            text=True,
        )

    @patch("flowctl.repo_ci_matrix.subprocess.run")
    def test_submodule_delegated_ci_accepts_gitlink_staged_in_index(self, run_mock) -> None:
        gitlink_sha = "b" * 40
        run_mock.side_effect = [
            subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=f"160000 {gitlink_sha} 0\tdashboard-frontend\n",
                stderr="",
            ),
        ]

        self.assertEqual(
            resolve_submodule_gitlink(Path("/workspace"), "dashboard-frontend"),
            gitlink_sha,
        )
        self.assertEqual(run_mock.call_count, 2)

    @patch("flowctl.repo_ci_matrix.subprocess.run")
    def test_submodule_delegated_ci_rejects_missing_gitlink(self, run_mock) -> None:
        run_mock.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="",
            stderr="",
        )

        with self.assertRaisesRegex(ValueError, "No submodule gitlink found"):
            resolve_submodule_gitlink(Path("/workspace"), "plg-platform-backend")

    def test_delegated_ci_rejects_missing_workflow_ref(self) -> None:
        workspace_config = {
            "repos": {
                "api": {
                    "path": "projects/api",
                    "kind": "implementation",
                    "runtime": "python",
                    "ci": {
                        "mode": "workflow-dispatch",
                        "workflow": "repo-ci.yml",
                        "source_sha": "c" * 40,
                    },
                }
            }
        }

        with self.assertRaisesRegex(ValueError, "no workflow ref"):
            build_repo_ci_matrices(workspace_config, {})

    def test_delegated_ci_rejects_sha_workflow_ref(self) -> None:
        workspace_config = {
            "repos": {
                "api": {
                    "path": "projects/api",
                    "kind": "implementation",
                    "runtime": "python",
                    "ci": {
                        "mode": "workflow-dispatch",
                        "workflow": "repo-ci.yml",
                        "ref": "a" * 40,
                        "source_sha": "b" * 40,
                    },
                }
            }
        }

        with self.assertRaisesRegex(ValueError, "branch or tag, not a SHA"):
            build_repo_ci_matrices(workspace_config, {})

    def test_project_workflow_dispatches_branch_with_source_sha_input(self) -> None:
        root = Path(__file__).resolve().parents[1]
        script = root / "scripts" / "ci" / "run_project_workflow.sh"
        gitlink_sha = "b" * 40

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            gh_log = temp_path / "gh.log"
            fake_gh = temp_path / "gh"
            fake_gh.write_text(
                '#!/usr/bin/env bash\n'
                'printf "%s\\n" "$*" >> "$GH_LOG"\n'
                'if [[ "$1 $2" == "run list" ]]; then echo "321"; fi\n',
                encoding="utf-8",
            )
            fake_gh.chmod(0o755)
            env = {
                **os.environ,
                "GH_LOG": str(gh_log),
                "PATH": f"{temp_path}:{os.environ['PATH']}",
            }

            result = subprocess.run(
                [
                    "bash",
                    str(script),
                    "repo-ci.yml",
                    "owner/backend",
                    "main",
                    gitlink_sha,
                    '{"repo":"backend"}',
                ],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            gh_calls = gh_log.read_text(encoding="utf-8")
            self.assertIn("workflow run repo-ci.yml --repo owner/backend --ref main", gh_calls)
            self.assertIn("-f repo=backend", gh_calls)
            self.assertIn(f"-f source_sha={gitlink_sha}", gh_calls)
            self.assertIn(f"run list --repo owner/backend --workflow repo-ci.yml", gh_calls)
            self.assertIn("--branch main", gh_calls)
            self.assertIn("--created >=", gh_calls)
            self.assertIn("displayTitle", gh_calls)
            self.assertIn(gitlink_sha, gh_calls)
            self.assertNotIn(f"--ref {gitlink_sha}", gh_calls)
            self.assertNotIn("--commit", gh_calls)
            self.assertIn("run watch 321 --repo owner/backend --exit-status", gh_calls)

    def test_project_workflow_rejects_sha_workflow_ref(self) -> None:
        root = Path(__file__).resolve().parents[1]
        script = root / "scripts" / "ci" / "run_project_workflow.sh"

        with tempfile.TemporaryDirectory() as temp_dir:
            fake_gh = Path(temp_dir) / "gh"
            fake_gh.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            fake_gh.chmod(0o755)
            env = {**os.environ, "PATH": f"{temp_dir}:{os.environ['PATH']}"}
            result = subprocess.run(
                [
                    "bash",
                    str(script),
                    "repo-ci.yml",
                    "owner/backend",
                    "c" * 40,
                    "c" * 40,
                    "{}",
                ],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn("workflow ref must be a branch or tag, not a commit SHA", result.stderr)

    def test_root_workflow_requires_cross_repo_token_with_scoped_permissions(self) -> None:
        root = Path(__file__).resolve().parents[1]
        workflow = (root / ".github" / "workflows" / "root-ci.yml").read_text(encoding="utf-8")

        delegated_job = workflow.split("  repo-ci-delegated:", maxsplit=1)[1].split(
            "  integration-smoke:", maxsplit=1
        )[0]
        self.assertIn("permissions:\n      actions: write\n      contents: read", delegated_job)
        self.assertIn("HAS_GH_PAT:", delegated_job)
        self.assertIn("dispatches cross-repo and requires the GH_PAT secret", delegated_job)

    def test_child_workflow_checks_out_requested_source_sha(self) -> None:
        root = Path(__file__).resolve().parents[1]
        workflow = (
            root / "plg-platform-backend" / ".github" / "workflows" / "repo-ci.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("run-name: SoftOS Repository CI (${{ inputs.source_sha }})", workflow)
        self.assertIn("source_sha:", workflow)
        self.assertIn("ref: ${{ inputs.source_sha }}", workflow)


if __name__ == "__main__":
    unittest.main()
