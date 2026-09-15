from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

from flowctl import release


class ReleaseVerifyTests(unittest.TestCase):
    def test_latest_check_run_replaces_failed_superseded_attempt(self) -> None:
        latest = release._latest_check_runs(
            [
                {
                    "id": 1,
                    "name": "deploy",
                    "status": "completed",
                    "conclusion": "failure",
                    "started_at": "2026-09-15T17:54:48Z",
                    "completed_at": "2026-09-15T17:55:22Z",
                },
                {
                    "id": 2,
                    "name": "deploy",
                    "status": "completed",
                    "conclusion": "success",
                    "started_at": "2026-09-15T17:59:03Z",
                    "completed_at": "2026-09-15T18:00:13Z",
                },
            ]
        )

        self.assertEqual(len(latest), 1)
        self.assertEqual(latest[0]["conclusion"], "success")

    def test_remote_tracking_refs_containing_sha_matches_origin_main(self) -> None:
        root = Path(__file__).resolve().parents[1]
        repo_sha = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "origin/main"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        present, details = release._remote_tracking_refs_containing_sha(
            repo_path=root,
            repo_sha=repo_sha,
            remote_name="origin",
            root=root,
        )
        self.assertTrue(present)
        self.assertIn("origin/main", details)


if __name__ == "__main__":
    unittest.main()
