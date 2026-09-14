---
schema_version: 3
name: "PLG API cache privacy and freshness hardening"
description: "Impedir que respuestas HTTP de la API Laravel con datos autenticados o sensibles de estudiantes y profesores sean almacenadas por caches compartidas, manteniendo intactos payloads, estados, autenticacion, CORS y cookies."
status: approved
owner: platform
depends_on:
  - specs/000-foundation/spec-as-source-operating-model.spec.md
  - specs/000-foundation/spec-driven-delivery-and-infrastructure.spec.md
  - specs/000-foundation/repo-routing-and-worktree-orchestration.spec.md
  - specs/000-foundation/plg-platform-backend-foundation-alignment.spec.md
  - specs/000-foundation/plg-platform-backend-coding-style-and-quality-contract.spec.md
required_runtimes:
  - php-laravel8-apache
required_services: []
required_capabilities:
  - laravel8
targets:
  - ../../plg-platform-backend/src/app/Http/Kernel.php
  - ../../plg-platform-backend/src/app/Http/Middleware/NoStoreApiResponses.php
  - ../../plg-platform-backend/src/tests/Feature/ApiCacheHeadersTest.php
---

# PLG API cache privacy and freshness hardening

## Objetivo

Establecer en el backend Laravel una politica HTTP uniforme que impida el
almacenamiento compartido de respuestas de API y proteja los flujos de Hub V2,
dashboard legacy, Sanctum, descargas y endpoints administrativos frente a
respuestas cruzadas entre usuarios.

La regla externa de Cloudflare ya aplicada por el operador es un prerequisito
de despliegue y queda fuera de los archivos modificados por esta feature. La
defensa en profundidad del origen es obligatoria y debe permanecer correcta
aunque una regla CDN sea cambiada accidentalmente.

## Contexto

Observaciones verificadas en el workspace:

- `plg-platform-backend/src/app/Http/Kernel.php` contiene el middleware global
  de Laravel, pero no una politica global de cache para API.
- `plg-platform-backend/src/app/Support/Hub/HubResponse.php` genera envelopes
  JSON de `/api/v2/hub/**` sin añadir headers de cache.
- `/api/v2/hub/**` contiene rutas autenticadas por `auth:sanctum`, incluyendo
  `/me`, planes, clases, reportes, notificaciones, gamificacion y perfil.
- Hub V2 usa cookies de sesion con `credentials: include`; por tanto, la
  ausencia de `Authorization` no implica que la respuesta sea publica.
- El dashboard legacy envia `Authorization: Bearer` en multiples servicios.
- Existen headers `no-store` en controladores puntuales, pero no cubren todas
  las respuestas de API.
- Hub mantiene algunas consultas en React Query durante cinco minutos. Esa
  cache local es un riesgo de freshness distinto del CDN y no se modifica en
  esta slice backend.
- No hay configuracion versionada de Cloudflare, Workers o `cloudflared` en el
  workspace. La regla Cloudflare se verifica como evidencia operativa externa.

## Foundations Aplicables

Aplican las foundations de modelo source-of-truth, delivery e infraestructura,
routing/worktrees y contratos de calidad/runtime del backend listadas en
`depends_on`. No se crea una foundation nueva porque este cambio es una
correccion de seguridad y transporte dentro del backend existente.

## Domains Aplicables

No aplica una spec de `specs/domains/**` porque no se agregan entidades,
estados de negocio, relaciones persistentes ni vocabulario de dominio. El
contrato modificado es exclusivamente HTTP/transporte y seguridad de cache.

## Problema a resolver

Una respuesta GET personalizada puede llegar a una cache compartida sin un
header de origen que la marque como privada. Esto es especialmente relevante
para las sesiones cookie de Sanctum: la misma URL puede ser solicitada por dos
estudiantes distintos, mientras que una cache compartida no debe usar la
cookie de sesion como identidad de negocio.

La correccion debe garantizar que una respuesta bajo API no se almacene en
browser cache ni en CDN/shared proxy, sin cambiar su body, status, autenticacion
ni cookies.

## Alcance

### Incluye

- Crear `NoStoreApiResponses` como middleware global de Laravel.
- Registrar el middleware en `app/Http/Kernel.php` dentro del stack global.
- Aplicar la politica a requests cuyo path Laravel sea `/api`, `/api/*`,
  `/sanctum/csrf-cookie` o `/sanctum/*`.
- Emitir en esas respuestas los siguientes headers, reemplazando cualquier
  directiva `Cache-Control` previa:

  ```text
  Cache-Control: private, no-store, max-age=0
  Cloudflare-CDN-Cache-Control: no-store
  Pragma: no-cache
  Expires: 0
  ```

- Cubrir respuestas 2xx, 3xx, 4xx, 5xx y OPTIONS que atraviesen el middleware.
- Añadir pruebas Feature focales para headers, body/status y preservacion de
  `Set-Cookie` cuando el endpoint emita cookies.
- Documentar evidencia de la regla Cloudflare externa y del purge como
  prerequisito de rollout, sin guardar tokens ni datos de estudiantes.

### No incluye

- Cambios en rutas, controladores, payloads, serializadores o reglas de negocio.
- Cambios en autenticacion Sanctum, nombres de cookies, CORS o dominios
  `SANCTUM_STATEFUL_DOMAINS`.
- Cambios en `HubResponse` ni refactor de los controladores que ya fijan
  `no-store`; el middleware global debe cubrirlos sin duplicar logica.
- Ajustes a React Query, dashboard legacy, Vite, CRA o clientes frontend.
- Configuracion de Cloudflare mediante API, Terraform, Workers o panel web.
- Cambios de `CACHE_DRIVER`, sesiones, base de datos, migraciones, dependencias,
  despliegues o releases.
- Cachear endpoints publicos de health, contratos o verificacion de certificados.

## Repos afectados

| Repo | Responsabilidad |
| --- | --- |
| `plg-platform-backend` | Middleware global y pruebas Feature del contrato HTTP. |
| `plg-platform-harness` | Spec, gates, handoffs y evidencia SoftOS; no cambia runtime del backend. |

## Inventario de superficies ejecutables

| Superficie | Evidencia actual | Decision |
| --- | --- | --- |
| Global middleware | `src/app/Http/Kernel.php` | Modificar solo para registrar el middleware. |
| Middleware nuevo | `src/app/Http/Middleware/NoStoreApiResponses.php` | Crear con path matching y headers exactos. |
| Hub V2 | `routes/api.php:177-248`, `auth:sanctum` | Cubierto por `/api/*`; payload y auth sin cambios. |
| Legacy API/admin | `routes/api.php:296+`, grupos `auth:sanctum` | Cubierto por `/api/*`; bearer sin cambios. |
| Sanctum CSRF | `/sanctum/csrf-cookie` | Cubierto; no se elimina `Set-Cookie`. |
| PDFs/descargas | Rutas API GET autenticadas | Cubierto; no se cachean respuestas sensibles. |
| Frontend caches | React Query y browser | Fuera de esta slice; se verifica como riesgo residual. |
| Cloudflare | Regla externa `exclusion-api` | Operativamente requerida; no se edita desde repo. |

## Invariantes y contrato HTTP

1. Toda respuesta de `/api`, `/api/*`, `/sanctum/csrf-cookie` y `/sanctum/*`
   devuelve `Cache-Control` con `private`, `no-store` y `max-age=0`.
2. Toda respuesta de esos paths devuelve `Cloudflare-CDN-Cache-Control: no-store`.
3. `Pragma: no-cache` y `Expires: 0` se incluyen como compatibilidad con
   caches/browser legacy.
4. El middleware no elimina, renombra ni modifica `Set-Cookie`.
5. El middleware no cambia body, status, content type, CORS, `Vary`, cookies,
   autenticacion, rate limits ni side effects del endpoint.
6. Los paths fuera de API/Sanctum no reciben esta politica por accidente.
7. No se usa una cache key por estudiante, cookie, bearer token o IP como
   sustituto de `no-store`.
8. Una regla CDN futura no puede convertir una respuesta API en cacheable sin
   que fallen las pruebas de contrato del origen y la verificacion operativa.

## Algoritmo de implementación

1. El middleware recibe el request y llama a `$next($request)` exactamente una
   vez.
2. Evalua el path normalizado mediante las APIs de `Request`, sin inspeccionar
   body, query string, usuario, cookie ni token para decidir la politica.
3. Si el path pertenece a API/Sanctum, fija los cuatro headers del contrato
   sobre la respuesta retornada.
4. Si no pertenece, retorna la respuesta sin añadir headers de API.
5. El registro en `Kernel::$middleware` debe conservar el orden existente de
   TrustProxies, CORS, mantenimiento, trim, conversion y Datadog; el middleware
   puede ejecutarse despues de esos componentes y antes del retorno final.
6. Las pruebas deben demostrar que el middleware se aplica a una respuesta
   exitosa y a una respuesta de autenticacion fallida, y que no rompe cookies.

## Errores, edge cases y prohibiciones

| Caso | Resultado requerido |
| --- | --- |
| GET autenticado con cookie Sanctum | `private, no-store`; body y status intactos. |
| GET autenticado con bearer legacy | `private, no-store`; body y status intactos. |
| POST/PUT/PATCH/DELETE | Misma politica; no altera CSRF ni idempotencia. |
| OPTIONS/preflight API | Misma politica y CORS existente intacto. |
| 401/403/404/422/500 bajo API | Misma politica; no se cachea error personalizado. |
| `/sanctum/csrf-cookie` | Politica de no-store y `Set-Cookie` preservado. |
| Ruta web/static fuera de API/Sanctum | Sin header añadido por este middleware. |
| Controller ya usa `no-store` | Se conserva el resultado seguro sin duplicar directivas. |
| Intento de cambiar rutas/payloads | Detener y reportar scope violation. |
| Necesidad de editar Cloudflare/Workers | Detener slice backend y escalar a infra/operator. |

## Criterios de aceptación

1. `NoStoreApiResponses` existe, es compatible con PHP 8.2/Laravel 8 y está
   registrado en el stack global.
2. Las pruebas prueban `/api/status` o una ruta API equivalente con body/status
   esperado y los headers completos. El valor `Cache-Control` debe contener las
   directivas `private`, `no-store` y `max-age=0`; el orden textual no es parte
   del contrato porque Symfony/Laravel puede normalizarlo.
3. Las pruebas cubren una ruta autenticada que responde 401/403 sin cache y,
   cuando el setup lo permita, `/sanctum/csrf-cookie` conserva `Set-Cookie`.
4. No hay cambios en rutas, controllers, auth, CORS, payloads, dependencias,
   migraciones o frontend.
5. `git diff --check` pasa en el worktree de la slice.
6. PHPUnit focal pasa usando el runtime del backend y la configuración MySQL
   declarada por el repositorio.
7. `flow spec review`, `flow ci spec` y el gate de repo backend pasan.
8. La verificación operativa confirma que Cloudflare mantiene activa una regla
   de bypass para `api.plgeducation.com` y `apitest.plgeducation.com`, ambas
   respuestas purgadas y `CF-Cache-Status` no es `HIT`.

## Stop conditions

- Detener antes de ampliar targets si el cambio requiere modificar frontend,
  Cloudflare como código, Workers, DNS, sesiones o base de datos.
- Detener si una prueba demuestra cambio de body, status, CORS, auth o cookies.
- Detener si el middleware no puede distinguir `/api/*` y `/sanctum/*` sin
  introducir una regla global sobre archivos estáticos.
- Detener si el backend runtime no puede levantar su healthcheck o PHPUnit no
  puede ejecutarse mediante `flow repo exec`.
- No cerrar con `no-op`: la política global y sus pruebas son obligatorias.

## Slice Breakdown

```yaml
- name: backend-api-no-store-middleware
  repo: plg-platform-backend
  targets:
    - ../../plg-platform-backend/src/app/Http/Kernel.php
    - ../../plg-platform-backend/src/app/Http/Middleware/NoStoreApiResponses.php
  hot_area: Laravel global HTTP middleware and API response cache policy
  depends_on: []
  slice_mode: implementation-heavy
  surface_policy: required
  minimum_valid_completion: global middleware registered and applying the exact no-store response contract only to API and Sanctum paths
  validated_noop_allowed: false
  acceptable_evidence:
    - focused PHP syntax validation passes
    - middleware contract can be exercised by the dependent Feature test
    - git diff --check passes for owned files

- name: backend-api-cache-contract-tests
  repo: plg-platform-backend
  targets:
    - ../../plg-platform-backend/src/tests/Feature/ApiCacheHeadersTest.php
  hot_area: API cache header and cookie preservation regression tests
  depends_on:
    - backend-api-no-store-middleware
  slice_mode: implementation-heavy
  surface_policy: required
  minimum_valid_completion: Feature tests prove headers, response invariants, auth error coverage, and CSRF cookie preservation where supported by the existing test setup
  validated_noop_allowed: false
  acceptable_evidence:
    - focused PHPUnit test passes
    - no unrelated tests or source files are modified
    - git diff --check passes for owned files
```

## Mandatory Patch Unit Guidance

La ejecución debe usar una sesión worker nueva por Patch Unit y respetar este
DAG. Ningún worker puede recibir más de un Patch Unit ni escribir targets de
otra unidad. La slice `backend-api-no-store-middleware` se ejecuta en orden
serial porque la segunda unidad depende de la primera; la slice de tests solo
se libera después de que ambas unidades de implementación pasen su verificación
focal.

| Patch Unit | Slice | Authorized target | Objective | Prerequisite | Focused verification |
| --- | --- | --- | --- | --- | --- |
| `pu-no-store-middleware-class` | `backend-api-no-store-middleware` | `src/app/Http/Middleware/NoStoreApiResponses.php` | Crear el middleware Laravel 8 que llama `$next` una vez y aplica el contrato exacto de headers solo a API/Sanctum, preservando la respuesta | Ninguno | `php -l src/app/Http/Middleware/NoStoreApiResponses.php` |
| `pu-register-no-store-middleware` | `backend-api-no-store-middleware` | `src/app/Http/Kernel.php` | Registrar la clase nueva una sola vez al final del stack global, sin reordenar middleware existente | `pu-no-store-middleware-class` | `php -l src/app/Http/Kernel.php` y diff autorizado de una sola línea de registro |
| `pu-api-cache-contract-tests` | `backend-api-cache-contract-tests` | `src/tests/Feature/ApiCacheHeadersTest.php` | Crear pruebas Feature para payload/status, errores auth, CSRF `Set-Cookie` y exclusión web | `pu-register-no-store-middleware` | PHPUnit focal del archivo nuevo usando MySQL del repo |

Cada unidad debe reportar: run id, executor/resource seleccionado, fingerprint
antes/después, diff autorizado no vacío, comando focal y resultado. Un `exit 0`
sin diff autorizado es `INVALID_IMPLEMENTATION`; un cambio fuera del target es
`SCOPE_VIOLATION`. Si el executor falla por disponibilidad/auth, se permite un
fallback acotado al siguiente recurso capaz; si falla por tamaño o contexto, se
debe re-decomponer, no ampliar el prompt.

## Test plan

- [@test] ../../plg-platform-backend/src/tests/Feature/AutoV2ScaffoldTest.php

## Verification Matrix

```yaml
- name: spec-review
  level: custom
  command: python3 ./flow workspace exec -- python3 ./flow spec review specs/features/2026-09-11-api-cache-privacy-hardening.spec.md --json
  blocking_on: [approval]
  environments: [local]

- name: spec-ci
  level: custom
  command: python3 ./flow workspace exec -- python3 ./flow ci spec specs/features/2026-09-11-api-cache-privacy-hardening.spec.md --json
  blocking_on: [ci]
  environments: [local]

- name: backend-cache-contract
  level: integration
  command: python3 ./flow repo exec plg-platform-backend -- php -d memory_limit=512M src/vendor/bin/phpunit -c src/phpunit.xml src/tests/Feature/ApiCacheHeadersTest.php
  blocking_on: [ci]
  environments: [local]
  notes: Ejecutar en el servicio del backend; no sustituir MySQL por SQLite.

- name: backend-regression
  level: integration
  command: python3 ./flow repo exec plg-platform-backend -- php -d memory_limit=512M src/vendor/bin/phpunit -c src/phpunit.xml src/tests/Feature/AutoV2ScaffoldTest.php
  blocking_on: [ci]
  environments: [local]

- name: backend-health
  level: smoke
  command: python3 ./flow repo exec plg-platform-backend -- sh -lc 'curl -fsS http://127.0.0.1:8080/api/v2/auto/health >/dev/null'
  blocking_on: [ci]
  environments: [local]

- name: diff-check
  level: custom
  command: git diff --check
  blocking_on: [ci]
  environments: [local]
```

## Evidencia operativa Cloudflare

Antes de promover el backend, el operador debe adjuntar al handoff o reporte
de cierre, sin secretos:

- captura/export de Cache Rule activa con expresión equivalente a
  `(http.host eq "api.plgeducation.com") or (http.host eq "apitest.plgeducation.com")`;
- acción `Omitir caché`;
- confirmación de purge por hostname o prefijo;
- headers de una petición real a cada hostname con `CF-Cache-Status` igual a
  `DYNAMIC` o `BYPASS`, nunca `HIT`;
- confirmación de que no existen Page Rules, Workers o Snippets que vuelvan a
  habilitar cache para esos hostnames.

Cloudflare documenta que las reglas de bypass hacen que una respuesta pueda
mostrar `DYNAMIC`, y que las reglas coincidentes posteriores pueden sobrescribir
una configuración previa. Esta evidencia es externa a PHPUnit y no se simula
con fixtures.

## Rollout

1. Mantener activa la regla Cloudflare de bypass y purgar los hostnames antes
   de desplegar el backend.
2. Implementar middleware y pruebas en un worktree dedicado.
3. Ejecutar PHPUnit focal, regresion, healthcheck y diff check.
4. Ejecutar CI de repo backend y revisión independiente read-only.
5. Desplegar primero en staging, verificar headers reales y probar dos sesiones
   de estudiantes sin respuestas `HIT`.
6. Promover a producción solo con evidencia de staging y Cloudflare.

## Rollback

Si se detecta una regresión de CORS, auth, cookies, payload o status, revertir
solo el registro del middleware y el archivo nuevo mediante el flujo normal de
la slice, manteniendo la regla Cloudflare de bypass activa. No desactivar el
bypass para restaurar funcionalidad. Reabrir la slice si el problema demuestra
que otra superficie HTTP también requiere una spec separada.
