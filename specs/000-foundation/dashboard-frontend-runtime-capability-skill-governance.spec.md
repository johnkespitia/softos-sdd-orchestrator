---
schema_version: 2
name: Dashboard Frontend Runtime Capability Skill Governance
description: Gobernar el runtime Node npm, la capability CRA y las skills efectivas del dashboard.
status: approved
owner: platform
depends_on:
  - specs/000-foundation/dashboard-frontend-foundation-alignment.spec.md
  - specs/000-foundation/dashboard-frontend-coding-style-and-quality-contract.spec.md
required_runtimes:
  - node-npm-react-cra
required_services: []
required_capabilities:
  - react-cra
targets:
  - ../../runtimes/node-npm-react-cra.runtime.json
  - ../../workspace.runtimes.json
  - ../../capabilities/react-cra.capability.json
  - ../../workspace.capabilities.json
  - ../../workspace.skills.json
  - ../../.agents/skills/node-core/SKILL.md
  - ../../.agents/skills/react-cra/SKILL.md
  - ../../workspace.config.json
  - ../../flowctl/runtimes.py
  - ../../flowctl/testing.py
  - ../../flowctl/parser.py
  - ../../flowctl/test_ci_repo_contracts.py
  - ../../specs/000-foundation/dashboard-frontend-runtime-capability-skill-governance.spec.md
---

# Dashboard Frontend Runtime Capability Skill Governance

## Resultado esperado

El contexto efectivo del repo devuelve runtime `node-npm-react-cra`, capability `react-cra` y skills locales resolubles, sin referencias a skills inexistentes.

## Reglas

- el runtime describe Node 20/npm, el layout doble de paquetes y Compose externo;
- la capability describe React CRA y no introduce stubs ni dependencias nuevas;
- `workspace/node-core` y `workspace/react-cra` son skills locales versionadas;
- cualquier migracion de framework requiere una spec separada.

## Aceptacion

- `flow skills doctor` pasa sin referencias faltantes;
- el runtime y capability aparecen habilitados en sus manifiestos;
- `python3 ./flow skills context --repo dashboard-frontend --json` lista paths existentes;
- la suite de contratos de CI y el build CRA pasan.

## Test plan

- [@test] ../../flowctl/test_ci_repo_contracts.py
- [@test] ../../flowctl/test_skills_doctor_refs.py

## Verification Matrix

```yaml
- name: skills-context
  level: integration
  command: python3 ./flow skills context --repo dashboard-frontend --json
  blocking_on: [ci]
  environments: [local]
- name: skills-doctor
  level: integration
  command: python3 ./flow skills doctor --json
  blocking_on: [ci]
  environments: [local, ci]
```

## Rollback

Restaurar el registro previo del workspace y retirar solo los packs nuevos; no modificar el codigo de la aplicacion.
