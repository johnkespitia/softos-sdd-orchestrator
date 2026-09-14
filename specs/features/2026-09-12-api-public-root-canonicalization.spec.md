---
schema_version: 3
name: "Canonicalizacion de URLs API sin /public"
description: "Publicar Laravel desde src/public y eliminar /public de las URLs API de Dashboard, Hub, backend, callbacks, webhooks, healthchecks y reglas de Cloudflare, con rollout humano por staging y produccion."
status: released
owner: platform
multi_domain: true
phases:
  - intake
  - human-origin-preflight
  - implementation
  - staging
  - production
depends_on:
  - spec-driven-delivery-and-infrastructure
  - dashboard-frontend-foundation-alignment
  - hub-frontend-foundation-alignment
  - plg-platform-backend-foundation-alignment
  - 2026-09-11-api-cache-privacy-hardening
required_runtimes:
  - node-npm-react-cra
  - node
  - php-laravel8-apache
  - generic
required_services: []
required_capabilities:
  - react-cra
  - vite-react
  - typescript
  - laravel8
stack_projects: []
stack_services: []
stack_capabilities: []
targets:
  - ../../dashboard-frontend/.github/workflows/staging.yml
  - ../../dashboard-frontend/.github/workflows/production.yml
  - ../../hub-frontend/.github/workflows/staging.yml
  - ../../hub-frontend/.github/workflows/production.yml
  - ../../plg-platform-backend/.github/workflows/staging.yml
  - ../../plg-platform-backend/.github/workflows/production.yml
  - ../../plg-platform-backend/.github/workflows/deploy-on-pr-merge.yml
  - ../../plg-platform-backend/src/scripts/deploy/ensure_google_workspace_env.sh
  - ../../plg-platform-backend/src/scripts/openapi/configure_chatgpt_import.py
  - ../../specs/features/2026-09-12-api-public-root-canonicalization.spec.md
---

# Canonicalizacion de URLs API sin /public

## Objetivo

Hacer que la URL publica y canonica de Laravel sea `/api/...`, sin exponer el
directorio de filesystem `/public` en la URL. El servidor debe usar
`plg-platform-backend/src/public` como document root. Los frontends deben
compilar contra `/api`, y los valores operativos del backend deben usar la
misma raiz canonica.

Este cambio corrige una desalineacion de despliegue. No agrega ni elimina
`/public` en las rutas Laravel.

## Diagnostico confirmado

- `dashboard-frontend` consume `process.env.REACT_APP_USER_API_URL` y concatena
  las rutas de negocio. Sus workflows de staging y produccion usan hoy
  `https://.../public/api`.
- `dashboard-frontend/src/dev.env` tambien contiene una base local con
  `/public/api`; no participa en los builds de staging/produccion y queda como
  pendiente de alineacion local porque el routing actual del workspace no
  autoriza ese archivo como target de implementacion.
- `hub-frontend` consume `VITE_API_URL` y construye rutas genericas bajo esa
  base. El adaptador Hub agrega `/v2/hub`; su cliente deriva CSRF desde la
  misma base. Sus workflows tambien usan hoy `https://.../public/api`.
- Laravel registra `routes/api.php` bajo el prefijo `/api`. El grupo Hub queda
  en `/api/v2/hub/**`; Laravel no declara un prefijo `/public`.
- El backend de despliegue tambien contiene `APP_URL`, callbacks OAuth,
  webhooks y `CHATGPT_OPENAPI_SERVER_URL` con `/public`. Los workflows
  alimentan un helper de patch remoto con esos valores; por routing del
  workspace, los scripts raiz bajo `plg-platform-backend/scripts/**` no son
  targets de esta feature y deben recibir valores canonicos explicitamente.
- La respuesta publica observada fue `404` con `cf-cache-status: DYNAMIC`.
  Eso debe tratarse primero como problema de document root/origen, no como
  evidencia de que Cloudflare haya servido una respuesta cacheada.

## Foundations y domains

Las foundations aplicables son:

- `specs/000-foundation/spec-driven-delivery-and-infrastructure.spec.md`
- `specs/000-foundation/dashboard-frontend-foundation-alignment.spec.md`
- `specs/000-foundation/hub-frontend-foundation-alignment.spec.md`
- `specs/000-foundation/plg-platform-backend-foundation-alignment.spec.md`
- `specs/features/2026-09-11-api-cache-privacy-hardening.spec.md`

No se declara un domain adicional: el cambio es de despliegue, configuracion
de origen, URLs de cliente y politica de cache, no de entidades de negocio.

## Alcance

### Incluye

- Configurar Hostinger para que staging y produccion publiquen Laravel desde
  `plg-platform-backend/src/public`.
- Cambiar las variables de build de Dashboard y Hub de `/public/api` a `/api`.
- Cambiar en workflows backend `APP_URL`, callbacks OAuth, webhooks y URLs
  operativas que representen el origen Laravel.
- Mantener la ruta de API canonica `/api/**` y la ruta Sanctum canonica
  `/sanctum/csrf-cookie`.
- Configurar manualmente en Cloudflare una regla de bypass para API y Sanctum
  en ambos hosts.
- Validar staging antes de produccion con pruebas de origen, autenticacion,
  CSRF, aislamiento entre estudiantes y frescura de datos.
- Purga controlada de objetos antiguos bajo `/public/*` y registro de
  evidencia sin secretos.

### No incluye

- No modificar `routes/api.php` para introducir o quitar `/public`.
- No modificar `RouteServiceProvider.php`, `hub.ts` ni `client.ts` para
  compensar un document root incorrecto.
- No cambiar DNS, nameservers ni el estado proxied de los registros A.
- No cambiar contratos, controladores, modelos, sesiones o permisos de
  negocio.
- No desplegar produccion sin aprobacion humana explicita posterior a staging.

## Targets y ownership

| Repo | Targets autorizados | Ownership |
| --- | --- | --- |
| `dashboard-frontend` | workflows staging/production | worker Dashboard |
| `hub-frontend` | workflows staging/production | worker Hub |
| `plg-platform-backend` | workflows staging/production/deploy-on-pr-merge, helper de patch remoto y generadores OpenAPI | worker Backend |
| `plg-platform-harness` | esta spec | orchestrator |
| Hostinger | document root y deploy path | humano operador |
| Cloudflare | Cache Rules, purge y verificacion | humano operador |

## Actores y responsabilidades humanas

| Actor | Puede hacer | Evidencia requerida |
| --- | --- | --- |
| Humano propietario de Hostinger | Cambiar document root, revisar permisos y confirmar que Apache/LiteSpeed ejecuta `src/public/index.php` | captura o nota de panel, fecha, host y resultado de curl |
| Humano propietario de Cloudflare | Crear/editar bypass, revisar orden de reglas y purgar cache | expression exportada/copiada, regla activa y resultado de purge |
| Humano propietario de GitHub | Confirmar secrets/vars de deploy y autorizar Actions si aplica | URL del run y estado, sin pegar tokens |
| Humano aprobador | Aprobar cierre de staging y promover produccion | aprobacion identificable en el canal o sistema acordado |
| Orchestrator SoftOS | Revisar spec, dividir Patch Units, verificar evidencia y decidir gates | reportes `.flow` y handoffs |
| Workers | Modificar unicamente sus targets y ejecutar verificaciones del repo | diff, comandos, resultados y handoff |

Los cambios de Hostinger y Cloudflare no deben ser simulados por un executor
ni ejecutados con credenciales no declaradas. Requieren accion humana y
evidencia manual.

## Invariantes

1. `https://api.plgeducation.com/api/...` y
   `https://apitest.plgeducation.com/api/...` son las URLs publicas canonicas.
2. `/public` es solo el document root de filesystem y no forma parte de las
   rutas de API, CSRF, OAuth ni webhooks despues del rollout.
3. Dashboard conserva autenticacion Bearer y Hub conserva cookies Sanctum;
   este cambio no puede alterar esos contratos.
4. Las respuestas privadas y mutaciones no son cacheables por Cloudflare.
5. Un error de document root bloquea el avance aunque el build frontend pase.
6. La falta de evidencia humana de origen o Cloudflare bloquea la promocion.

## Slice Breakdown

```yaml
- name: backend-canonical-url-config
  targets:
    - ../../plg-platform-backend/.github/workflows/staging.yml
    - ../../plg-platform-backend/.github/workflows/production.yml
    - ../../plg-platform-backend/.github/workflows/deploy-on-pr-merge.yml
    - ../../plg-platform-backend/src/scripts/deploy/ensure_google_workspace_env.sh
    - ../../plg-platform-backend/src/scripts/openapi/configure_chatgpt_import.py
  hot_area: plg-platform-backend/workflows
  depends_on: []
  slice_mode: minimal-change
  surface_policy: forbidden
  minimum_valid_completion: backend workflows and authorized src helpers use canonical URLs without /public, including explicit values passed to the remote patch helper
  validated_noop_allowed: false
  acceptable_evidence:
    - static scan of backend workflows
    - workflow syntax review
    - backend regression test result

- name: dashboard-canonical-api-base
  targets:
    - ../../dashboard-frontend/.github/workflows/staging.yml
    - ../../dashboard-frontend/.github/workflows/production.yml
  hot_area: dashboard-frontend/workflows
  depends_on: []
  slice_mode: minimal-change
  surface_policy: forbidden
  minimum_valid_completion: Dashboard builds use /api without /public
  validated_noop_allowed: false
  acceptable_evidence:
    - static scan of frontend workflows
    - CRA test result
    - production build result

- name: hub-canonical-api-base
  targets:
    - ../../hub-frontend/.github/workflows/staging.yml
    - ../../hub-frontend/.github/workflows/production.yml
  hot_area: hub-frontend/workflows
  depends_on: []
  slice_mode: minimal-change
  surface_policy: forbidden
  minimum_valid_completion: Hub builds use /api without /public
  validated_noop_allowed: false
  acceptable_evidence:
    - static scan of frontend workflows
    - Hub API client tests
    - lint and production build result

- name: intake-and-operational-contract
  targets:
    - ../../specs/features/2026-09-12-api-public-root-canonicalization.spec.md
  hot_area: plg-platform-harness/specs
  depends_on:
    - backend-canonical-url-config
    - dashboard-canonical-api-base
    - hub-canonical-api-base
  slice_mode: governance
  surface_policy: forbidden
  minimum_valid_completion: spec, human runbook and evidence contract are reviewable
  validated_noop_allowed: false
  acceptable_evidence:
    - flow spec review result
    - approved plan with disjoint ownership
    - G0-G6 closeout checklist
```

## Decision table

| Situacion | Decision |
| --- | --- |
| Hostinger acepta `src/public` como document root y el healthcheck canonico responde | Continuar con cambio de variables |
| Hostinger no permite document root y requiere mantener `/public` | Detener, escalar al humano y no modificar rutas Laravel |
| Endpoint canonico devuelve 404/HTML | Bloquear frontend y produccion; corregir origen |
| Cloudflare muestra cache para `/api/*` o `/sanctum/*` | Bloquear rollout; corregir regla y purgar |
| Staging falla aislamiento, CSRF o frescura | No promover produccion |
| GitHub Actions no esta autenticado o no existe `source_ref` | Bloquear dispatch y pedir accion humana |

## Flujo operativo completo

### 1. Intake y G0, orchestrator

1. Registrar este intake y conservar el estado generado por `flow`.
2. Resolver repos, runtimes, capabilities y foundations.
3. Capturar fingerprints de root y subrepos antes de crear worktrees.
4. Confirmar que el humano responsable tiene acceso a Hostinger, Cloudflare y
   GitHub, pero no solicitar ni almacenar credenciales en el workspace.

### 2. Preflight humano de origen, G1

1. El humano documenta el document root actual de `api.plgeducation.com` y
   `apitest.plgeducation.com` en Hostinger.
2. El humano confirma que el codigo desplegado contiene `public/index.php` y
   que el servidor puede apuntar a `plg-platform-backend/src/public`.
3. En staging, el humano cambia el document root y guarda el valor anterior
   para rollback.
4. El humano ejecuta:

   ```text
   curl.exe -sS -D - -o NUL https://apitest.plgeducation.com/api/v2/auto/health
   curl.exe -sS -D - -o NUL https://apitest.plgeducation.com/api/v2/hub/health
   curl.exe -sS -D - -o NUL https://apitest.plgeducation.com/sanctum/csrf-cookie
   ```

5. El resultado esperado es una respuesta Laravel/JSON o el status de
   aplicacion documentado, nunca la pagina HTML 404 de Hostinger.
6. Si falla, el humano revierte el document root o corrige el origen y el
   flujo queda bloqueado en G1.

### 3. Plan y Patch Units, G2

El orchestrator debe crear unidades disjuntas:

La definicion canonica de las unidades esta en `## Slice Breakdown`. Cloudflare
y Hostinger permanecen como actividades operativas humanas sin target de repo.

No unit may edit the frontend API clients or Laravel route files.

### 4. Implementacion controlada

1. Backend worker elimina `/public` de `APP_URL`, callbacks OAuth, webhooks y
   `CHATGPT_OPENAPI_SERVER_URL` en los workflows autorizados, pasando valores
   canonicos explicitamente al helper que parchea el `.env` remoto.
2. Dashboard worker cambia las dos configuraciones autorizadas de sus
   workflows a `/api`.
3. Hub worker cambia los dos `VITE_API_URL` autorizados a `/api`.
4. Cada worker ejecuta solo el runtime de su repo mediante `flow repo exec`.
5. El orchestrator verifica que no haya cambios fuera de ownership.

### 5. Cloudflare, accion humana

El humano debe crear o corregir una Cache Rule activa para ambos hosts:

```text
(http.host in {"api.plgeducation.com" "apitest.plgeducation.com"}
 and (starts_with(http.request.uri.path, "/api/")
      or starts_with(http.request.uri.path, "/sanctum/")))
```

Accion: `Omitir cache` / `Bypass cache`.

La regla no debe comparar `http.request.uri` con el nombre del host. El host
se valida con `http.host`. El humano debe revisar el orden de reglas, guardar
la regla y purgar al menos `/public/*` y cualquier objeto API previamente
cacheado. DNS no se modifica.

### 6. Staging, G4

1. CI compila Dashboard y Hub con `/api`.
2. CI despliega backend y frontends a staging mediante el flujo aprobado.
3. El humano valida en DevTools que no existan requests a `/public/api`.
4. El humano ejecuta smoke de health y CSRF.
5. El humano prueba login Dashboard con Bearer.
6. El humano prueba login Hub, `GET /api/v2/hub/me`, una mutacion y el cookie
   `XSRF-TOKEN`.
7. Con dos estudiantes de prueba, el humano verifica que cada sesion solo
   recibe sus propios datos.
8. El humano modifica un dato permitido y confirma que una lectura posterior
   refleja el cambio sin servir una respuesta vieja.
9. El orchestrator registra evidencia y no continua si un resultado es
   ambiguo, HTML, 404, 419, 401 inesperado o cacheado.

### 7. Aprobacion y produccion, G5

1. El orchestrator prepara el handoff de staging con diffs, builds, smoke,
   headers y evidencia humana.
2. Un humano distinto del worker aprueba la promocion a produccion.
3. El humano confirma antes del dispatch que el `source_ref` existe y que
   GitHub Actions esta autenticado dentro del servicio `workspace`.
4. Se promueve backend y frontends con el mismo orden probado en staging.
5. El humano repite health, login, CSRF, aislamiento y frescura en produccion.
6. Se cierra solo con evidencia completa y aprobacion humana registrada.

## Contratos observables

| Cliente | Base canonica | Ejemplo |
| --- | --- | --- |
| Dashboard | `REACT_APP_USER_API_URL=https://host/api` | `https://host/api/my-account` |
| Hub generico | `VITE_API_URL=https://host/api` | `https://host/api/student-app/dashboard` |
| Hub V2 | misma base + `/v2/hub` | `https://host/api/v2/hub/me` |
| Sanctum | raiz del host, fuera de `/api` | `https://host/sanctum/csrf-cookie` |

## Errores y prohibiciones

- Un 404 HTML del proveedor de hosting no se resuelve agregando `/public` a
  `routes/api.php`.
- Un `cf-cache-status: DYNAMIC` no demuestra que el endpoint sea correcto; se
  debe validar status, content-type, route contract y origen.
- No se deben pegar tokens, cookies, DSNs, claves SSH ni respuestas privadas en
  specs, handoffs o reportes.
- No se deben promover builds que aun contengan `/public/api`.
- No se debe purgar toda la zona Cloudflare si basta una purga por URL o
  prefijo.

## Criterios de aceptacion

- Hostinger publica staging y produccion usando `src/public` como document
  root, con evidencia humana.
- Ningun workflow de frontend compila con `/public/api`.
- Los workflows backend no generan `APP_URL`, callbacks, webhooks ni URLs
  operativas con `/public`, salvo una excepcion aprobada y documentada.
- Dashboard usa `/api` y conserva el header Bearer.
- Hub usa `/api`, genera `/api/v2/hub/**` y deriva CSRF en `/sanctum/**`.
- Cloudflare tiene bypass activo para `/api/*` y `/sanctum/*` en ambos hosts.
- Staging pasa health, login, CSRF, aislamiento por estudiante y frescura.
- Produccion solo se ejecuta despues de una aprobacion humana de staging.
- Existe evidencia de rollback y cierre G0-G6.

## Verification Matrix

```yaml
- name: spec-contract
  level: custom
  command: python3 ./flow spec review 2026-09-12-api-public-root-canonicalization
  blocking_on: [review]
  environments: [local]
  notes: validates targets, dependencies, runtimes and acceptance contract

- name: static-no-public-api
  level: integration
  command: "! rg -n 'https://(api|apitest)\\.plgeducation\\.com/public|/public/api|APP_URL=.*\\/public|CHATGPT_OPENAPI_SERVER_URL=.*\\/public|GOOGLE_.*REDIRECT_URI=.*\\/public|GOOGLE_CALENDAR_WEBHOOK_URL=.*\\/public' dashboard-frontend/.github hub-frontend/.github plg-platform-backend/.github plg-platform-backend/src/scripts/deploy plg-platform-backend/src/scripts/openapi"
  blocking_on: [ci, release]
  environments: [local, staging, production]
  notes: no canonical client or backend workflow URL keeps the filesystem prefix

- name: dashboard-repo
  level: custom
  command: python3 ./flow repo exec dashboard-frontend -- sh -lc 'CI=true npm --prefix src test -- --watchAll=false'
  blocking_on: [ci]
  environments: [local]
  notes: preserves legacy CRA behavior after build configuration change

- name: hub-repo
  level: custom
  command: python3 ./flow repo exec hub-frontend -- sh -lc 'pnpm test && pnpm lint && pnpm build'
  blocking_on: [ci]
  environments: [local]
  notes: preserves URL construction, CSRF derivation and Vite build

- name: backend-repo
  level: custom
  command: python3 ./flow repo exec plg-platform-backend -- php -d memory_limit=512M src/vendor/bin/phpunit -c src/phpunit.xml
  blocking_on: [ci]
  environments: [local]
  notes: validates backend regression surface without changing route declarations

- name: human-staging-smoke
  level: e2e
  command: manual curl, browser DevTools and two-student isolation checklist
  blocking_on: [approval, release]
  environments: [staging]
  notes: requires human evidence for origin, auth, CSRF, cache headers and freshness

- name: human-production-smoke
  level: e2e
  command: manual post-deploy smoke after explicit human approval
  blocking_on: [approval, release]
  environments: [production]
  notes: repeats only the approved staging contract
```

## Test references

- [@test] ../../dashboard-frontend/src/src/services/availabilityService.test.js
- [@test] ../../hub-frontend/src/shared/api/client.test.tsx
- [@test] ../../hub-frontend/src/shared/api/hub.test.ts
- [@test] ../../plg-platform-backend/src/tests/Feature/HubV2RouteScaffoldTest.php

## Rollout

- Staging first, production second.
- Backend origin/document root must be healthy before frontend builds are
  promoted.
- Frontend builds are immutable with build-time API URLs; both applications
  must be rebuilt and redeployed after changing variables.
- Cloudflare bypass must be active before freshness and isolation tests.
- The rollout is not complete until the human confirms no `/public/api` calls
  in browser network logs.

## Rollback

1. Stop promotion immediately on any failed gate.
2. Restore the previous frontend artifacts if users cannot authenticate or
   load their application.
3. Restore the previous Hostinger document root only if the new origin mapping
   is the failure cause; record the old value before changing it.
4. Restore previous backend URL variables and callbacks if external providers
   reject canonical URLs.
5. Keep the API cache bypass active while diagnosing; do not re-enable caching
   for private API responses as a rollback shortcut.
6. Purge only affected old/new API URL prefixes and repeat the staging smoke.

## Evidence and closeout

Required evidence:

- intake report and spec review result;
- disjoint worker handoffs and authorized diffs;
- static scan showing no `/public/api` in target workflows;
- Dashboard tests/build and Hub tests/lint/build;
- backend regression evidence;
- Hostinger document root confirmation;
- Cloudflare expression, active state and purge confirmation;
- staging browser/network and two-student isolation checklist;
- human staging approval, production approval and post-deploy smoke;
- rollback values and final G0-G6 state.

The orchestrator must close with a concise handoff. It must not commit, push,
merge, release or publish unless a later approved gate explicitly authorizes
that action.
