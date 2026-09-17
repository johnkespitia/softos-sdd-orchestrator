---
name: python-core
description: Apply the Python conventions used by the SoftOS root tooling and flowctl tests.
---

# Python Core

Use this skill for changes to the root `flow` CLI, `flowctl/**`, gateway Python code, or Python-based workspace checks.

## Contract

- Target the Python version provided by the workspace devcontainer.
- Prefer standard-library modules and existing `flowctl` helpers before adding dependencies.
- Keep CLI commands deterministic, non-interactive, and explicit about non-zero exits.
- Preserve JSON output as a stable machine-readable contract.
- Add focused pytest or unittest coverage for changed orchestration behavior.
- Run Python checks through `python3 ./flow workspace exec -- ...` when Docker is available.
