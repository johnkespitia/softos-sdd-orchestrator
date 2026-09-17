---
name: typescript-expert
description: Apply TypeScript conventions for SoftOS Node frontends using strict typechecking and package scripts.
---

# TypeScript Expert

- Treat `tsconfig.json` / `tsconfig.node.json` as authoritative; do not weaken `strict` without a spec.
- Validate with `pnpm typecheck` (`tsc --noEmit`) before claiming a slice done.
- Keep path aliases aligned with Vite `resolve.alias` and `tsconfig` paths.
- Prefer existing typed shared modules over `any` escapes; if a temporary escape is required, keep it local and justified.
