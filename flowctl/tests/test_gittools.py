import os
from pathlib import Path
from unittest.mock import patch, MagicMock

from flowctl.gittools import git_output


class TestGitOutput:
    """Tests for flowctl/gittools.py::git_output.

    Bug: When Git pre-commit hooks run, GIT_INDEX_FILE is set to the root index.
    Previously, git_output() forwarded the full process env into subprocess.run,
    causing failures like: "fatal: .git/index: index file open failed: Not a directory"

    This test verifies that git_output() no longer passes Git-specific environment
    variables (GIT_INDEX_FILE, GIT_OBJECT_DIRECTORY, etc.) to subprocess calls,
    even when they are set in the parent process.
    """

    def test_git_output_ignores_bogus_git_index_file(self):
        """git_output should succeed even with a bogus GIT_INDEX_FILE env var."""
        bogus_index = "/nonexistent/path/to/bad/index"

        # Set a bogus GIT_INDEX_FILE that would normally cause git to fail.
        with patch.dict(os.environ, {
            "GIT_INDEX_FILE": bogus_index,
        }):
            # git rev-parse --is-inside-work-tree is a simple query that should
            # work regardless of what GIT_INDEX_FILE is set to (it's a metadata
            # query against the .git directory, not about the working tree index).
            returncode, stdout, stderr = git_output(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=Path("/home/john/workspace/plg-platform-harness"),
                root=Path("/home/john/workspace/plg-platform-harness"),
            )

        # The call should succeed (returncode 0). If GIT_INDEX_FILE were forwarded,
        # git would fail with "fatal: .git/index: index file open failed"
        assert returncode == 0, f"git_output failed: stderr={stderr!r}"
        assert stdout.strip() == "true", f"Unexpected output: {stdout!r}"

    def test_git_output_uses_clean_env(self):
        """git_output should copy os.environ and strip Git-specific vars."""
        with patch.dict(os.environ, {
            "GIT_INDEX_FILE": "/fake/index",
            "GIT_DIR": "/fake/.git",
            "GIT_WORK_TREE": "/fake/tree",
        }):
            returncode, stdout, stderr = git_output(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=Path("/home/john/workspace/plg-platform-harness"),
                root=Path("/home/john/workspace/plg-platform-harness"),
            )

        assert returncode == 0, f"git_output failed: stderr={stderr!r}"