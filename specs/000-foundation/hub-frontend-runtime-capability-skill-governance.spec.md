---
schema_version: 2
name: Hub Frontend Runtime Capability Skill Governance
description: Gobernar runtime node, capabilities vite-react/typescript y skills efectivas de hub-frontend.
status: approved
owner: platform
depends_on:
  - specs/000-foundation/hub-frontend-foundation-alignment.spec.md
  - specs/000-foundation/hub-frontend-coding-style-and-quality-contract.spec.md
required_runtimes:
  - node
required_services: []
required_capabilities:
  - vite-react
  - typescript
targets:
  - ../../runtimes/node.runtime.json
  - ../../workspace.runtimes.json
  - ../../capabilities/vite-react.capability.json
  - ../../capabilities/typescript.capability.json
  - ../../workspace.capabilities.json
  - ../../workspace.skills.json
  - ../../.agents/skills/node-core/SKILL.md
  - ../../.agents/skills/vite-expert/SKILL.md
  - ../../.agents/skills/react-expert/SKILL.md
  - ../../.agents/skills/typescript-expert/SKILL.md
  - ../../workspace.config.json
  - ../../flowctl/runtimes.py
  - ../../flowctl/test_ci_repo_contracts.py
  - ../../specs/000-foundation/hub-frontend-runtime-capability-skill-governance.spec.md
---

# Hub Frontend Runtime Capability Skill Governance

## Objetivo

Garantizar que el contexto efectivo de `hub-frontend` resuelve runtime `node`, capabilities `vite-react` + `typescript` y skills locales sin referencias rotas.

## Contexto

Las capabilities stock referencian `workspace/vite-expert`, `workspace/react-expert` y `workspace/typescript-expert`. Esas skills ya existen localmente en el harness.

## Problema a resolver

Sin gobernanza explicita, un agente puede inventar skills/runtimes o mezclar contratos npm/CRA del dashboard con pnpm/Vite del hub.

## Alcance

### Incluye

- verificar manifiestos runtime/capability/skills habilitados;
- mantener `agent_skill_refs` del repo coherentes con `workspace.skills.json`;
- documentar que `node-core` cubre pnpm y npm segun lockfile.

### No incluye

- crear un runtime pack nuevo salvo que el generico `node` resulte insuficiente;
- migracion de framework.

## Repos afectados

- root harness manifests y skills
- metadata de `hub-frontend` en workspace config

## Resultado esperado

`flow skills doctor` y `flow skills context --repo hub-frontend --json` pasan con paths existentes.

## Reglas de negocio

- runtime describe Node/pnpm y Compose externo del repo;
- capabilities no escriben stubs sobre un submodulo existente;
- skills locales versionadas bajo `.agents/skills/**`;
- cualquier migracion de framework requiere spec separada.

## Flujo principal

1. Auditar refs del repo.
2. Corregir manifiestos si faltan.
3. Evidenciar doctor + context.

## Contrato funcional

Skills minimas del repo:

- `workspace/node-core`
- `workspace/vite-expert`
- `workspace/react-expert`
- `workspace/typescript-expert`

## Criterios de aceptacion

- `flow skills doctor` sin refs faltantes;
- runtime `node` y capabilities habilitados;
- `python3 ./flow skills context --repo hub-frontend --json` lista paths existentes;
- no se referencian `workspace/react-cra` ni runtime CRA para este repo.

## Test plan

- [@test] ../../flowctl/test_ci_repo_contracts.py
- [@test] ../../flowctl/test_skills_doctor_refs.py

## Verification Matrix

```yaml
- name: skills-context
  level: integration
  command: python3 ./flow skills context --repo hub-frontend --json
  blocking_on: [ci]
  environments: [local]
- name: skills-doctor
  level: integration
  command: python3 ./flow skills doctor --json
  blocking_on: [ci]
  environments: [local, ci]
```

## Rollout

Sin despliegue remoto; solo manifests del harness.

## Rollback

Restaurar `agent_skill_refs` previos; no tocar codigo de producto del hub.
