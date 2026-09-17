---
name: react-cra
description: Apply the local conventions for the existing Create React App frontend under a nested src package.
---

# React Create React App

- The application package lives under `src/`; its `package.json` and lockfile are authoritative for frontend dependencies.
- Preserve Create React App scripts and use `npm --prefix src ci`, `npm --prefix src test -- --watchAll=false`, and `npm --prefix src run build` for non-interactive checks.
- Keep the development server bound to `0.0.0.0` and expose host port `3001` to container port `3000` through the project-owned Compose file.
- Build-time `REACT_APP_*` values are public bundle configuration. Never commit credentials or production secret values.
- Do not migrate to Vite, TypeScript, or another framework as part of infrastructure alignment.
