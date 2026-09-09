---
schema_version: 2
name: Hub Frontend Foundation Alignment
description: Integrar hub-frontend (Vite + React + TypeScript + pnpm) al workspace SoftOS con Compose federado y submodulo.
status: approved
owner: platform
depends_on:
  - specs/000-foundation/spec-as-source-operating-model.spec.md
  - specs/000-foundation/spec-driven-delivery-and-infrastructure.spec.md
  - specs/000-foundation/repo-routing-and-worktree-orchestration.spec.md
required_runtimes:
  - node
required_services: []
required_capabilities:
  - vite-react
  - typescript
targets:
  - ../../workspace.config.json
  - ../../workspace.runtimes.json
  - ../../workspace.capabilities.json
  - ../../workspace.skills.json
  - ../../workspace.preflight.json
  - ../../runtimes/node.runtime.json
  - ../../capabilities/vite-react.capability.json
  - ../../capabilities/typescript.capability.json
  - ../../.agents/skills/node-core/SKILL.md
  - ../../.agents/skills/vite-expert/SKILL.md
  - ../../.agents/skills/react-expert/SKILL.md
  - ../../.agents/skills/typescript-expert/SKILL.md
  - ../../flowctl/stack.py
  - ../../scripts/preflight_env.sh
  - ../../hub-frontend/AGENTS.md
  - ../../hub-frontend/docker-compose.yaml
  - ../../hub-frontend/node.Dockerfile
  - ../../hub-frontend/vite.config.ts
  - ../../hub-frontend/package.json
  - ../../specs/000-foundation/hub-frontend-foundation-alignment.spec.md
---

# Hub Frontend Foundation Alignment

## Objetivo

Dejar `hub-frontend` registrado como submodulo ejecutable desde SoftOS, con Compose propio federado, Node 20 + pnpm y Vite sin migrar el stack de producto.

## Contexto

`hub-frontend` es Vite + React 18 + TypeScript + pnpm. Ya esta clonado como submodulo. Falta Compose federado, readiness HTTP y contratos foundation alineados al patron de `dashboard-frontend`.

## Problema a resolver

Sin Compose del repo hijo y sin registro `compose_file`, SoftOS no puede levantar ni validar el hub en el stack. Sin foundation specs, el routing y la evidencia de gates quedan ambiguos.

## Alcance

### Incluye

- Compose propio (`docker-compose.yaml` + `node.Dockerfile`) con servicio `hub-front`;
- exposicion host `5173` -> contenedor `5173`;
- `vite.config.ts` con `server.host=0.0.0.0` y puerto `5173`;
- registro `compose_file` / `compose_service` en `workspace.config.json`;
- skills/runtime/capability ya referenciados resolubles;
- preflight readiness opcional para el servicio.

### No incluye

- cambios de UI, rutas de negocio, auth o API contracts;
- migracion a npm/CRA/Next;
- cambios de secretos staging/produccion;
- rediseño de deploy workflows (`staging.yml` / `production.yml`) mas alla de no interferir con CI delegada.

## Repos afectados

- root harness (`workspace.*.json`, skills, preflight)
- `hub-frontend` (Compose, Dockerfile, vite server bind, AGENTS.md)

## Resultado esperado

`flow stack ps` muestra `hub-front` healthy/up y `curl -fsS http://127.0.0.1:5173` responde. Skills context del repo resuelve sin refs faltantes.

## Reglas de negocio / Invariantes

- `repo_strategy: submodule`; el gitlink es la version del hijo.
- El Compose del hijo es la unica definicion de `hub-front`; no se duplica en el Compose raiz.
- `pnpm-lock.yaml` gobierna dependencias; CI usa `--frozen-lockfile`.
- `VITE_*` son configuracion publica de bundle, no secretos.

## Flujo principal

1. Materializar Compose/Dockerfile y bind de Vite en el repo hijo.
2. Federar via `compose_file` en workspace config.
3. `flow stack up` + readiness HTTP.
4. Cerrar foundation specs con review/approve/ci spec.

## Contrato funcional

- servicio Compose: `hub-front`
- puerto host por defecto: `5173` (`HUB_FRONTEND_PORT`)
- install/test/build: `pnpm install --frozen-lockfile` / `pnpm test` / `pnpm build`

## Criterios de aceptacion

- `flow skills context --repo hub-frontend --json` resuelve todas las skills.
- `docker compose config` desde el repo hijo resuelve `node.Dockerfile` y `hub-front`.
- `flow stack ps` muestra `hub-front` y responde en `http://127.0.0.1:5173`.
- `pnpm test` y `pnpm build` pasan en Node 20.
- `flow spec review|approve` y `flow ci spec` pasan para esta spec.

## Test plan

- [@test] ../../flowctl/test_stack_compose_files.py
- [@test] ../../flowctl/test_ci_repo_contracts.py
- [@test] ../../hub-frontend/src/App.test.tsx

## Verification Matrix

```yaml
- name: hub-tests
  level: integration
  command: pnpm test
  blocking_on: [ci]
  environments: [local, ci]
- name: hub-build
  level: integration
  command: pnpm build
  blocking_on: [ci]
  environments: [local, ci]
- name: hub-http
  level: smoke
  command: curl -fsS http://127.0.0.1:5173
  blocking_on: [ci]
  environments: [local]
```

## Stop conditions

- detener si se requiere copiar el servicio al Compose raiz;
- detener si falta auth para dependencias o se proponen secretos en el repo;
- detener si la validacion exige cambios funcionales fuera de targets.

## Rollout

Aplicar en el branch de sync SoftOS; levantar stack local; no tocar entornos remotos.

## Rollback

Retirar `compose_file`/servicio del registro workspace y los archivos Compose del hijo; el submodulo de aplicacion permanece.
