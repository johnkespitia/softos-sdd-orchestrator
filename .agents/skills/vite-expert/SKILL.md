---
name: vite-expert
description: Apply Vite conventions for SoftOS frontend repos that use Vite as the bundler and dev server.
---

# Vite Expert

- Prefer the project `vite.config.ts` (or `.js`) as the source of truth for aliases, plugins, and test config.
- Dev server must bind to `0.0.0.0` when running inside Compose so the host port mapping works.
- Default Vite port is `5173` unless the project Compose file maps another host port.
- Use package scripts (`pnpm dev`, `pnpm build`, `pnpm preview`) instead of invoking Vite binaries ad hoc.
- Keep Vitest configuration in the Vite config when the repo already colocate tests that way; do not introduce a parallel Jest setup.
