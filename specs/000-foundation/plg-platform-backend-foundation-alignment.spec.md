---
schema_version: 2
name: PLG Platform Backend Foundation Alignment
description: Integrar el backend Laravel existente al stack, routing y readiness de SoftOS sin duplicar su topologia.
status: approved
owner: platform
depends_on:
  - specs/000-foundation/spec-as-source-operating-model.spec.md
  - specs/000-foundation/spec-driven-delivery-and-infrastructure.spec.md
  - specs/000-foundation/repo-routing-and-worktree-orchestration.spec.md
required_runtimes:
  - php-laravel8-apache
required_services: []
required_capabilities:
  - laravel8
targets:
  - ../../AGENTS.md
  - ../../.devcontainer/**
  - ../../flow
  - ../../flowctl/stack.py
  - ../../flowctl/test_stack_compose_files.py
  - ../../scripts/preflight_env.sh
  - ../../workspace.config.json
  - ../../workspace.preflight.json
  - ../../workspace.secrets.json
  - ../../workspace.stack.json
  - ../../plg-platform-backend/AGENTS.md
  - ../../plg-platform-backend/docker-compose.yaml
  - ../../plg-platform-backend/.env.example
  - ../../plg-platform-backend/config/init.sql
  - ../../plg-platform-backend/.github/**
  - ../../plg-platform-backend/src/**
  - ../../specs/000-foundation/plg-platform-backend-foundation-alignment.spec.md
---

# PLG Platform Backend Foundation Alignment

## Objetivo

Dejar `plg-platform-backend` registrado, ejecutable y verificable desde SoftOS usando su topologia Laravel, Apache y MySQL existente.

## Contexto

El repo es un submodulo con la aplicacion en `src/` y compose propio. El alta inicial agrego un segundo servicio PHP generico al compose raiz y no preservo las rutas relativas del compose del proyecto.

## Problema a resolver

`flow stack` no puede levantar el backend de forma reproducible, `flow repo exec` no dispone de un workdir valido para la aplicacion y no existe readiness de aplicacion configurado.

## Alcance

### Incluye

- federar el compose del repo preservando su directorio de proyecto
- eliminar el servicio PHP duplicado del compose raiz
- alinear la imagen de ejecucion con PHP 8.2, requerido por el lockfile vigente
- registrar servicios, rutas, puertos y readiness efectivos
- declarar una unica plantilla de entorno canonica bajo el application root
- mantener el submodulo como unidad de implementacion independiente
- verificar el endpoint publico `/api/v2/auto/health`

### No incluye

- cambios de negocio, rutas API o migraciones de datos
- upgrade de Laravel o dependencias Composer
- despliegue a staging o produccion

## Repos afectados

| Repo | Responsabilidad |
| --- | --- |
| `plg-platform-harness` | Federacion, routing, manifests y preflight. |
| `plg-platform-backend` | Contrato de agente, CI y configuracion local de la aplicacion. |

## Resultado esperado

`flow stack up` inicia `workspace`, `gateway`, `web-server` y `mysql-server`; el backend queda accesible por un puerto configurable y responde salud HTTP.

## Reglas de negocio

- El compose del proyecto se reutiliza; no se copian sus servicios al compose raiz.
- El estado `Up` no es suficiente: el healthcheck HTTP debe pasar.
- Las rutas relativas de cada compose se resuelven desde el directorio que lo contiene.
- Los comandos de implementacion deben poder ejecutarse sobre el repo base y sobre worktrees.
- `src/.env.example` es la plantilla canonica; cualquier plantilla legado debe declararlo y conservar defaults seguros.

## Flujo principal

1. SoftOS resuelve el compose raiz y el compose registrado del backend.
2. Docker Compose carga cada archivo con su propio project directory.
3. MySQL alcanza estado saludable y Apache sirve `src/public`.
4. Preflight valida runtime, configuracion y endpoint HTTP.

## Contrato funcional

- `workspace.config.json` declara `compose_file` y el servicio web real.
- El compose efectivo no contiene un servicio PHP generico duplicado.
- La federacion no reescribe rutas del compose del proyecto bajo `.devcontainer/`.
- El puerto web es configurable y tiene default local no privilegiado.

## Criterios de aceptacion

- `docker compose config` resuelve `php.Dockerfile`, `src/` e `init.sql` dentro de `plg-platform-backend`.
- `scripts/preflight_env.sh --build` termina sin fallos.
- `flow stack ps` muestra web y MySQL saludables.
- `curl -fsS http://127.0.0.1:8080/api/v2/auto/health` responde correctamente.
- `flow spec review`, `flow spec approve` y `flow ci spec` pasan para esta spec.
- El preflight y la CI materializan `src/.env` desde `src/.env.example`.

## Test plan

- [@test] ../../flowctl/test_stack_compose_files.py
- [@test] ../../plg-platform-backend/src/tests/Feature/AutoV2ScaffoldTest.php

## Verification Matrix

```yaml
- name: compose-federation
  level: integration
  command: python3 -m pytest -q flowctl/test_stack_compose_files.py
  blocking_on: [ci]
  environments: [local]
- name: backend-health
  level: smoke
  command: curl -fsS http://127.0.0.1:8080/api/v2/auto/health
  blocking_on: [ci]
  environments: [local]
```

## Stop conditions

- Detener si la solucion requiere copiar logica de negocio o ejecutar migraciones destructivas.
- Detener si el compose standalone del backend deja de ser utilizable.

## Rollout

Aplicar primero en local, validar compose y health, y habilitar CI solo despues del smoke exitoso.

## Rollback

Restaurar el registro y compose anteriores, retirar la federacion y conservar el submodulo sin cambios de datos.
