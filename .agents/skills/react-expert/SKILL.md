---
name: react-expert
description: Apply React 18 conventions for SoftOS Vite frontends with feature-based src layout.
---

# React Expert

- Keep application code under `src/` with the repo's feature layout (`app`, `shared`, `features`, `pages`, `assets`, `test`).
- Prefer React Router, TanStack Query, and existing shared wrappers over adding parallel state or data libraries.
- Forms should use React Hook Form + Zod when the repo already follows that pattern.
- Observability (Sentry/PostHog) must go through existing wrappers, not scattered direct SDK calls.
- Do not migrate a Vite React app to CRA, or a CRA app to Vite, unless a root spec explicitly requires it.
