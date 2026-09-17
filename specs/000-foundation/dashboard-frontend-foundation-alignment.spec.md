---
schema_version: 2
name: Dashboard Frontend Foundation Alignment
description: Integrar el dashboard React existente al workspace SoftOS conservando su Compose y su estructura CRA.
status: approved
owner: platform
depends_on:
  - specs/000-foundation/spec-as-source-operating-model.spec.md
  - specs/000-foundation/spec-driven-delivery-and-infrastructure.spec.md
  - specs/000-foundation/repo-routing-and-worktree-orchestration.spec.md
required_runtimes:
  - node-npm-react-cra
required_services: []
required_capabilities:
  - react-cra
targets:
  - ../../workspace.config.json
  - ../../workspace.runtimes.json
  - ../../workspace.capabilities.json
  - ../../workspace.skills.json
  - ../../runtimes/node-npm-react-cra.runtime.json
  - ../../capabilities/react-cra.capability.json
  - ../../.agents/skills/node-core/SKILL.md
  - ../../.agents/skills/react-cra/SKILL.md
  - ../../flowctl/stack.py
  - ../../flowctl/ci.py
  - ../../scripts/preflight_env.sh
  - ../../dashboard-frontend/AGENTS.md
  - ../../dashboard-frontend/docker-compose.yaml
  - ../../dashboard-frontend/node.Dockerfile
  - ../../specs/000-foundation/dashboard-frontend-foundation-alignment.spec.md
---

# Dashboard Frontend Foundation Alignment

## Objetivo

Dejar `dashboard-frontend` registrado como submodulo y ejecutable desde SoftOS, reutilizando su Compose propio y manteniendo Create React App bajo `src/`.

## Alcance

- registrar runtime, capability, skills, servicio `front-app` y Compose federado;
- fijar Node 20 y `npm ci` para las dos instalaciones lockfileadas;
- exponer el desarrollo en `3001:3000` y validar el proceso HTTP;
- mantener la aplicacion React, sus rutas y sus variables publicas sin migracion de framework.

## Fuera de alcance

- cambios de UI, rutas de negocio, autenticacion o integraciones;
- migracion a Vite, TypeScript o pnpm;
- despliegues FTP y cambios de secretos de staging/produccion.

## Invariantes

- `dashboard-frontend` conserva `repo_strategy: submodule` y el gitlink es la fuente de version del repo hijo.
- El Compose del repo hijo es la unica definicion del servicio `front-app`; no se duplica en el Compose raiz.
- `src/package-lock.json` gobierna las dependencias de la aplicacion y `package-lock.json` las herramientas de release.
- Ningun valor `REACT_APP_*` se trata como secreto dentro del bundle publico.

## Criterios de aceptacion

- `flow skills context --repo dashboard-frontend --json` resuelve todas las skills.
- `docker compose config` resuelve `node.Dockerfile`, `src/` y el servicio `front-app` desde el directorio del repo hijo.
- `flow stack ps` muestra `front-app` y el servidor responde en `http://127.0.0.1:3001`.
- `CI=true npm --prefix src test -- --watchAll=false` y `npm --prefix src run build` pasan en el runtime Node 20.
- `flow spec review`, `flow spec approve` y `flow ci spec` pasan para esta spec.

## Test plan

- [@test] ../../flowctl/test_stack_compose_files.py
- [@test] ../../flowctl/test_ci_repo_contracts.py
- [@test] ../../dashboard-frontend/src/src/routes.menu.test.jsx
- [@test] ../../dashboard-frontend/src/src/routes.visibility.test.jsx

## Verification Matrix

```yaml
- name: frontend-tests
  level: integration
  command: CI=true npm --prefix src test -- --watchAll=false
  blocking_on: [ci]
  environments: [local, ci]
- name: frontend-build
  level: integration
  command: npm --prefix src run build
  blocking_on: [ci]
  environments: [local, ci]
- name: frontend-http
  level: smoke
  command: curl -fsS http://127.0.0.1:3001
  blocking_on: [ci]
  environments: [local]
```

## Stop conditions

- detener si se requiere copiar servicios del Compose hijo al root;
- detener si falta autenticacion para descargar dependencias o si se propone alterar secretos;
- detener si la validacion exige cambios funcionales fuera de los targets declarados.

## Rollback

Retirar el registro del repo y los packs nuevos, conservando el submodulo y su Compose standalone sin cambios de datos.
