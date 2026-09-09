---
name: node-core
description: Apply the SoftOS Node.js conventions for dependency installation, tests, builds, and reproducible local execution with npm or pnpm.
---

# Node Core

- Honor the repository package manager and lockfile: `npm ci` with `package-lock.json`, or `pnpm install --frozen-lockfile` with `pnpm-lock.yaml`. Do not mix managers in the same repo.
- Run commands from the package root declared by the repo runtime. If the app is nested, use the explicit package prefix declared by its project contract.
- Keep Node and package-manager versions aligned with the runtime Dockerfile, `packageManager` field, and CI setup.
- Prefer existing package scripts and avoid adding tooling that is not required by the project.
- Treat build-time `REACT_APP_*`, `VITE_*`, or equivalent public variables as configuration, never as secrets.
