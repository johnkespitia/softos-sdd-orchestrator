---
schema_version: 2
name: PLG Platform Backend Coding Style And Quality Contract
description: Definir comandos reproducibles de formato, analisis y pruebas para el backend Laravel existente.
status: approved
owner: platform
depends_on:
  - specs/000-foundation/plg-platform-backend-foundation-alignment.spec.md
required_runtimes:
  - php-laravel8-apache
required_services: []
required_capabilities:
  - laravel8
targets:
  - ../../workspace.config.json
  - ../../plg-platform-backend/AGENTS.md
  - ../../plg-platform-backend/.github/**
  - ../../plg-platform-backend/src/composer.json
  - ../../plg-platform-backend/src/composer.lock
  - ../../plg-platform-backend/src/phpunit.xml
  - ../../plg-platform-backend/src/tests/**
  - ../../specs/000-foundation/plg-platform-backend-coding-style-and-quality-contract.spec.md
---

# PLG Platform Backend Coding Style And Quality Contract

## Objetivo

Hacer que cualquier agente ejecute la misma instalacion y los mismos gates de calidad desde `src/`, tanto localmente como en CI.

## Contexto

La aplicacion tiene una suite PHPUnit amplia, pero el registro actual ejecuta Composer desde la raiz del submodulo y no declara lint ni analisis estatico.

## Problema a resolver

La CI generica no encuentra `composer.json`, no prepara el entorno Laravel correcto y no expresa una definicion de terminado para cambios PHP.

## Alcance

### Incluye

- comandos Composer y PHPUnit con workdir `src/`
- taxonomia unit, feature y smoke
- workflow CI delegado y disparado por el root SoftOS
- convenciones de estilo existentes de PHP/Laravel

### No incluye

- refactor masivo para corregir deuda de estilo historica
- cambios funcionales o aumento arbitrario de cobertura
- despliegues

## Repos afectados

| Repo | Responsabilidad |
| --- | --- |
| `plg-platform-harness` | Seleccion y delegacion del gate CI. |
| `plg-platform-backend` | Comandos de calidad y workflow ejecutable. |

## Resultado esperado

La instalacion usa el lockfile, PHPUnit ejecuta sus suites reales y el root bloquea integracion cuando falla la CI delegada.

## Reglas de negocio

- No se usa `composer update` en CI.
- Todo comando PHP parte de `src/` o usa `--working-dir=src`.
- La CI delegada solo acepta `workflow_dispatch`.
- Los tests que necesitan MySQL reciben un servicio aislado de CI.

## Flujo principal

1. Root CI descubre el backend como delegado.
2. Despacha `repo-ci.yml` en el commit del submodulo.
3. El workflow instala dependencias, prepara Laravel y ejecuta PHPUnit.
4. Root CI espera resultado binario antes de integracion.

## Contrato funcional

- Install: `composer --working-dir=src install --no-interaction --prefer-dist`.
- Tests: `php -d memory_limit=512M src/vendor/bin/phpunit -c src/phpunit.xml`.
- PHP 8.2 y sus extensiones coinciden con el lockfile y el runtime declarado del proyecto.
- Los fallos de setup, migracion de DB de test o PHPUnit fallan el workflow.

## Criterios de aceptacion

- La matriz CI clasifica el backend como delegado.
- El workflow hijo no contiene triggers `push` ni `pull_request`.
- Composer utiliza `src/composer.lock`.
- PHPUnit puede ejecutar al menos una prueba unitaria y una feature.
- Los gates de spec pasan.

## Test plan

- [@test] ../../plg-platform-backend/src/tests/Unit/Logging/DatadogLoggerTest.php
- [@test] ../../plg-platform-backend/src/tests/Feature/AutoV2ScaffoldTest.php

## Verification Matrix

```yaml
- name: delegated-ci-contract
  level: integration
  command: python3 -m pytest -q flowctl/test_repo_ci_matrix.py
  blocking_on: [ci]
  environments: [local]
- name: backend-acceptance-tests
  level: integration
  command: php -d memory_limit=512M src/vendor/bin/phpunit -c src/phpunit.xml src/tests/Feature/AutoV2ScaffoldTest.php
  blocking_on: [ci]
  environments: [local]
```

## Rollout

Activar primero el workflow delegado y mantener los workflows operativos existentes fuera del gate de pruebas.

## Rollback

Volver temporalmente a CI generica con comandos explicitos bajo `src/`; no eliminar la suite existente.
