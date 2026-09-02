from __future__ import annotations


def render_status(name: str, passed: bool) -> str:
    label = "PASS" if passed else "FAIL"
    return f"{name}: {label}"
