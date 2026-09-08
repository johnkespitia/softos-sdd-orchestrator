---
schema_version: 2
name: PLG Platform Backend Runtime Capability Skill Governance
description: Registrar runtime, capability y skills tecnicas compatibles con el backend Laravel 8.
status: draft
owner: platform
depends_on:
  - specs/000-foundation/plg-platform-backend-foundation-alignment.spec.md
  - specs/000-foundation/plg-platform-backend-coding-style-and-quality-contract.spec.md
required_runtimes:
  - php-laravel8-apache
required_services: []
required_capabilities:
  - laravel8
targets:
  - ../../runtimes/**
  - ../../capabilities/**
  - ../../.agents/skills/**
  - ../../workspace.runtimes.json
  - ../../workspace.capabilities.json
  - ../../workspace.skills.json
  - ../../workspace.config.json
  - ../../flowctl/skills.py
  - ../../flowctl/skills_ops.py
  - ../../flowctl/test_skills_doctor_refs.py
  - ../../flowctl/test_stack_compose_files.py
  - ../../plg-platform-backend/AGENTS.md
  - ../../specs/000-foundation/plg-platform-backend-runtime-capability-skill-governance.spec.md
---

# PLG Platform Backend Runtime Capability Skill Governance

## Objetivo

Eliminar referencias de skills sin resolver y describir de forma declarativa el runtime PHP/Apache y la capability Laravel 8 del proyecto.

## Contexto

El repo hereda `workspace/php-core`, pero esa entrada no existe. La capability Laravel disponible genera Laravel 10 y no representa la aplicacion 8.x actual. Ademas, el lockfile vigente exige PHP 8.2 aunque el Dockerfile usaba PHP 8.0.

## Problema a resolver

Los agentes reciben contexto incompleto y un runtime generico con estructura, servidor y version distintos a los del backend.

## Alcance

### Incluye

- runtime especializado para aplicacion PHP en subdirectorio con compose externo
- capability Laravel 8 sin sobrescribir archivos existentes
- skills locales PHP core y Laravel 8
- validacion de referencias transitivas en skills doctor

### No incluye

- upgrade de Laravel o dependencias Composer
- instalacion de skills externos no auditados
- reglas de dominio del producto

## Repos afectados

| Repo | Responsabilidad |
| --- | --- |
| `plg-platform-harness` | Catalogos y validacion de runtime/capability/skills. |
| `plg-platform-backend` | Consumo del contexto tecnico y reglas locales. |

## Resultado esperado

`flow skills context --repo plg-platform-backend --json` devuelve paths no nulos para todas las skills y el repo declara una capability compatible con Laravel 8.

## Reglas de negocio

- Ninguna referencia de skill puede quedar sin entrada habilitada.
- El runtime describe ejecucion y layout; la capability describe Laravel.
- El compose es externo y no se genera desde el runtime.
- La modernizacion de versiones requiere otra spec.

## Flujo principal

1. El repo resuelve su runtime registrado.
2. El runtime aporta defaults PHP y la capability aporta contexto Laravel.
3. `flow skills context` materializa todas las rutas.
4. `flow skills doctor` falla ante cualquier referencia inexistente.

## Contrato funcional

- Runtime PHP 8.2 con `src` como application root, PHPUnit como runner y compose nulo.
- Capability compatible con `laravel/framework` 8.x.
- Skills locales breves, especificas y sin instrucciones de negocio.
- Repo con lista efectiva deduplicada de skills.

## Criterios de aceptacion

- Runtime y capability aparecen habilitados en sus manifests.
- Todas las `agent_skill_refs` resuelven un path.
- `flow doctor` y `flow skills doctor` pasan.
- La capability no cambia `composer.json` ni crea stubs sobre el proyecto existente.
- Los gates de spec pasan.

## Test plan

- [@test] ../../flowctl/test_stack_compose_files.py
- [@test] ../../flowctl/test_skills_doctor_refs.py
- [@test] ../../plg-platform-backend/src/tests/Unit/Logging/DatadogLoggerTest.php

## Verification Matrix

```yaml
- name: skill-reference-governance
  level: integration
  command: python3 -m pytest -q flowctl/test_skills_doctor_refs.py
  blocking_on: [ci]
  environments: [local]
- name: effective-skill-context
  level: smoke
  command: python3 ./flow skills context --repo plg-platform-backend --json
  blocking_on: [ci]
  environments: [local]
```

## Rollout

Registrar primero skills, luego capability y runtime, y finalmente cambiar el repo al nuevo runtime.

## Rollback

Restaurar el runtime `php` generico y retirar las entradas nuevas sin modificar codigo de aplicacion.
