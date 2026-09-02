from __future__ import annotations

import unittest

from .status_fixture import render_status


class RenderStatusTests(unittest.TestCase):
    def test_cursor_pass(self) -> None:
        self.assertEqual(render_status("cursor", True), "cursor: PASS")

    def test_opencode_fail(self) -> None:
        self.assertEqual(render_status("opencode", False), "opencode: FAIL")


if __name__ == "__main__":
    unittest.main()
