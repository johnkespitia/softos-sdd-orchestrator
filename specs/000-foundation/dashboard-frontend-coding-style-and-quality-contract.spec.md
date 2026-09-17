---
schema_version: 2
name: Dashboard Frontend Coding Style And Quality Contract
description: Definir instalacion, pruebas y build reproducibles para el dashboard React.
status: approved
owner: platform
depends_on:
  - specs/000-foundation/dashboard-frontend-foundation-alignment.spec.md
required_runtimes:
  - node-npm-react-cra
required_services: []
required_capabilities:
  - react-cra
targets:
  - ../../dashboard-frontend/AGENTS.md
  - ../../dashboard-frontend/package.json
  - ../../dashboard-frontend/package-lock.json
  - ../../dashboard-frontend/src/package.json
  - ../../dashboard-frontend/src/package-lock.json
  - ../../dashboard-frontend/src/src/**
  - ../../dashboard-frontend/.github/workflows/repo-ci.yml
  - ../../workspace.config.json
  - ../../.github/workflows/root-ci.yml
  - ../../flow
  - ../../flowctl/testing.py
  - ../../flowctl/ci.py
  - ../../flowctl/test_ci_repo_contracts.py
  - ../../specs/000-foundation/dashboard-frontend-coding-style-and-quality-contract.spec.md
---

# Dashboard Frontend Coding Style And Quality Contract

## Objetivo

Hacer que los agentes y CI utilicen los mismos comandos npm para el paquete de release y la aplicacion CRA.

## Contrato

- install: `npm ci && npm --prefix src ci`;
- tests: `CI=true npm --prefix src test -- --watchAll=false`;
- build: `npm --prefix src run build`;
- no se ejecuta `npm install` en CI y no se actualizan lockfiles automaticamente;
- los tests existentes bajo `src/src` son evidencia minima; no se relajan sus aserciones.

## Aceptacion

- el runtime y `workspace.config.json` declaran comandos estrictos con lockfiles;
- el workflow hijo solo tiene `workflow_dispatch`, valida `source_sha` y checkout el gitlink exacto;
- la matriz root descubre Node para este repo y bloquea ante fallo de tests o build;
- `flow slice verify` acepta el runner `npm` y valida referencias JS/JSX.

## Test plan

- [@test] ../../flowctl/test_ci_repo_contracts.py
- [@test] ../../dashboard-frontend/src/src/routes.menu.test.jsx
- [@test] ../../dashboard-frontend/src/src/routes.visibility.test.jsx

## Verification Matrix

```yaml
- name: npm-contract
  level: integration
  command: python3 -m pytest -q flowctl/test_ci_repo_contracts.py
  blocking_on: [ci]
  environments: [local, ci]
- name: cra-suite
  level: integration
  command: CI=true npm --prefix src test -- --watchAll=false
  blocking_on: [ci]
  environments: [local, ci]
```

## Fuera de alcance

No incluye refactor de componentes, cambios de dependencias de producto, migracion de bundler ni rediseño de la pipeline de despliegue FTP.
