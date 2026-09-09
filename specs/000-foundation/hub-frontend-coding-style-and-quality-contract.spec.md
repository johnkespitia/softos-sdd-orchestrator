---
schema_version: 2
name: Hub Frontend Coding Style And Quality Contract
description: Definir install, lint, typecheck, test y build reproducibles para hub-frontend con CI delegada SoftOS.
status: approved
owner: platform
depends_on:
  - specs/000-foundation/hub-frontend-foundation-alignment.spec.md
required_runtimes:
  - node
required_services: []
required_capabilities:
  - vite-react
  - typescript
targets:
  - ../../hub-frontend/AGENTS.md
  - ../../hub-frontend/package.json
  - ../../hub-frontend/pnpm-lock.yaml
  - ../../hub-frontend/src/**
  - ../../hub-frontend/.github/workflows/repo-ci.yml
  - ../../hub-frontend/.github/workflows/ci.yml
  - ../../hub-frontend/.github/workflows/frontend-ci.yml
  - ../../workspace.config.json
  - ../../.github/workflows/root-ci.yml
  - ../../flowctl/ci.py
  - ../../flowctl/test_ci_repo_contracts.py
  - ../../flowctl/test_repo_ci_matrix.py
  - ../../scripts/ci/discover_repo_ci_matrix.py
  - ../../specs/000-foundation/hub-frontend-coding-style-and-quality-contract.spec.md
---

# Hub Frontend Coding Style And Quality Contract

## Objetivo

Unificar comandos pnpm y hacer que SoftOS root CI sea el unico disparador de quality gates del hub.

## Contexto

El repo ya expone `pnpm lint|typecheck|test|build` y workflows con `push`/`pull_request`. SoftOS exige child workflows solo con `workflow_dispatch` y `source_sha`.

## Problema a resolver

Sin delegacion, root CI corre generico y los workflows del hijo siguen disparandose en push/PR, duplicando y desviando el orquestador SoftOS.

## Alcance

### Incluye

- contrato CI en `workspace.config.json` con `mode: workflow-dispatch` y `workflow: repo-ci.yml`;
- workflow hijo `repo-ci.yml` solo `workflow_dispatch`, valida `source_sha` y checkout exacto;
- retirar `push`/`pull_request` de `ci.yml` y `frontend-ci.yml` (convertir a dispatch-only o eliminar redundancia);
- comandos estrictos con lockfile.

### No incluye

- cambios de reglas ESLint/TS de producto;
- migracion de Vitest;
- alteracion de deploy secrets en staging/production mas alla de no usarlos como quality gate SoftOS.

## Repos afectados

- `hub-frontend` workflows
- root harness CI metadata

## Resultado esperado

`discover_repo_ci_matrix.py` lista `hub-frontend` en `delegated_matrix` con `source_sha` del gitlink.

## Reglas de negocio

- install: `pnpm install --frozen-lockfile`
- lint: `pnpm lint`
- typecheck: `pnpm typecheck` (en el workflow hijo)
- test: `pnpm test`
- build: `pnpm build`
- no `npm install` / no actualizar lockfiles en CI

## Flujo principal

1. Crear `repo-ci.yml` con quality gates y `source_sha`.
2. Neutralizar triggers push/PR de quality workflows legacy.
3. Declarar metadata de delegacion en workspace config.
4. Verificar matriz delegated.

## Contrato funcional

```json
"ci": {
  "mode": "workflow-dispatch",
  "workflow": "repo-ci.yml",
  "workflow_repository": "PLGEducation/hub-frontend",
  "ref": "main",
  "trigger_mode": "workflow_dispatch_only",
  "install": ["pnpm", "install", "--frozen-lockfile"],
  "lint": ["pnpm", "lint"],
  "test": ["pnpm", "test"],
  "build": ["pnpm", "build"]
}
```

## Criterios de aceptacion

- child workflow solo `workflow_dispatch` + input `source_sha` obligatorio;
- checkout usa `ref: ${{ inputs.source_sha }}`;
- matriz root descubre el repo como delegated;
- no hay quality gate en push/PR para `ci.yml` / `frontend-ci.yml`.

## Test plan

- [@test] ../../flowctl/test_ci_repo_contracts.py
- [@test] ../../flowctl/test_repo_ci_matrix.py
- [@test] ../../hub-frontend/src/App.test.tsx

## Verification Matrix

```yaml
- name: delegated-matrix
  level: integration
  command: python3 ./scripts/ci/discover_repo_ci_matrix.py
  blocking_on: [ci]
  environments: [local, ci]
- name: hub-suite
  level: integration
  command: pnpm test
  blocking_on: [ci]
  environments: [local, ci]
```

## Rollout

Commit del workflow en el submodulo y metadata en el harness; root CI despacha en el siguiente run.

## Rollback

Revertir metadata `mode: workflow-dispatch` al generico local y restaurar triggers previos del hijo si hace falta operacion de emergencia.
