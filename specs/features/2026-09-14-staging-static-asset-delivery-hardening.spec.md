---
schema_version: 3
name: "Hardening de entrega de assets estaticos en staging y produccion"
description: "Garantizar que los deploys Laravel de staging y produccion materialicen y verifiquen public/storage, que Hostinger publique desde src/public y que la entrega de imagenes tenga evidencia HTTP."
status: released
owner: platform
single_slice_reason: ""
multi_domain: true
phases:
  - intake
  - diagnosis
  - human-origin-preflight
  - implementation
  - staging
  - production
depends_on:
  - ../../specs/000-foundation/spec-as-source-operating-model.spec.md
  - ../../specs/000-foundation/spec-driven-delivery-and-infrastructure.spec.md
  - ../../specs/000-foundation/repo-routing-and-worktree-orchestration.spec.md
  - ../../specs/000-foundation/plg-platform-backend-foundation-alignment.spec.md
  - ../../specs/features/2026-09-12-api-public-root-canonicalization.spec.md
  - ../../specs/features/2026-09-14-student-profile-image-integrity.spec.md
required_runtimes:
  - php-laravel8-apache
  - generic
required_services: []
required_capabilities:
  - laravel8
stack_projects: []
stack_services: []
stack_capabilities: []
targets:
  - ../../specs/features/2026-09-14-staging-static-asset-delivery-hardening.spec.md
  - ../../plg-platform-backend/.github/workflows/deploy-on-pr-merge.yml
  - ../../plg-platform-backend/.github/workflows/staging.yml
  - ../../plg-platform-backend/.github/workflows/production.yml
infra_targets:
  - ../../plg-platform-backend/.github/workflows/deploy-on-pr-merge.yml
  - ../../plg-platform-backend/.github/workflows/staging.yml
  - ../../plg-platform-backend/.github/workflows/production.yml
test_refs:
  - ../../plg-platform-backend/src/tests/Feature/ProfileImageUploadUrlTest.php
---

# Hardening de entrega de assets estaticos en staging y produccion

## Objetivo

Cerrar la brecha entre una subida de archivo exitosa y una imagen realmente
descargable desde staging y produccion. Cada deploy debe materializar el
enlace publico de Laravel, validar que el enlace apunta al directorio correcto
y bloquear el rollout si el origen de Hostinger no publica desde `src/public`.
Staging debe agregar una prueba HTTP de asset sintetico; produccion debe
conservar un smoke post-deploy aprobado y no usar datos reales para probar el
deploy.

Esta spec gobierna el hardening del flujo de despliegue. No reabre la
implementacion de perfil de estudiante ni autoriza cambios en controladores,
clientes frontend, rutas API, schema o almacenamiento externo.

## Diagnostico confirmado

- El disco Laravel `public` usa `storage/app/public` como root y genera URLs
  bajo `APP_URL/storage`.
- Las fotos de estudiante se guardan bajo
  `storage/app/public/student_photos/<filename>`.
- La URL canonica esperada es
  `https://apitest.plgeducation.com/storage/student_photos/<filename>`.
- `src/config/filesystems.php` declara el enlace
  `src/public/storage -> src/storage/app/public` cuando se ejecuta
  `php artisan storage:link`.
- El deploy por merge, el workflow legacy de staging y el workflow manual de
  produccion no ejecutan
  `php artisan storage:link`.
- El healthcheck actual valida liveness de Laravel, pero no la entrega de
  archivos estaticos.
- En staging, una ruta `/storage/student_photos/...` inexistente respondio
  `404`; una ruta antigua `/public/storage/...` redirigio a
  `/storage/app/public/...` y tambien termino en `404`.
- El servidor reporta Hostinger/LiteSpeed/Cloudflare y el contrato de la spec
  de URLs canonicas exige que el document root sea `src/public`.

La evidencia anterior demuestra una falla de entrega del origen, pero no
demuestra por si sola si falta el symlink, si el document root esta mal
configurado o si ambas condiciones ocurren a la vez. La ejecucion debe
conservar esa distincion.

## Foundations y domains

Las foundations aplicables son:

- `specs/000-foundation/spec-as-source-operating-model.spec.md`
- `specs/000-foundation/spec-driven-delivery-and-infrastructure.spec.md`
- `specs/000-foundation/repo-routing-and-worktree-orchestration.spec.md`
- `specs/000-foundation/plg-platform-backend-foundation-alignment.spec.md`

La dependencia de `2026-09-12-api-public-root-canonicalization` es obligatoria:
el document root es parte del contrato de origen y no puede corregirse
agregando `/public` a la URL devuelta.

La dependencia de `2026-09-14-student-profile-image-integrity` vincula esta
spec con la evidencia de upload, persistencia y respuesta API ya ejecutada.
No se declara un domain nuevo porque no cambia el modelo de `Student` ni el
contrato de negocio de la foto.

## Alcance

### Incluye

- Agregar al deploy por merge de staging la materializacion idempotente de
  `public/storage` mediante Artisan.
- Agregar al deploy legacy/manual de staging la misma materializacion y
  validacion.
- Verificar que `public/storage` sea un symlink y que su destino resuelto sea
  `storage/app/public` dentro del mismo `APP_PATH`.
- Agregar un gate de entrega estatica que pruebe un asset controlado y no
  exponga secretos, tokens, cookies ni PII.
- Documentar y validar los document roots de
  `apitest.plgeducation.com` y `api.plgeducation.com` en Hostinger.
- Mantener la URL canonica sin `/public` y la ruta de almacenamiento vigente.
- Dejar evidencia separada para workflow, origen Hostinger y prueba HTTP.

### No incluye

- No modificar `StudentController`, `HubProfileService`,
  `HubProfilePhotoController` ni rutas Laravel.
- No modificar Dashboard, Hub, contratos multipart, autenticacion o CORS.
- No cambiar `APP_URL` para introducir `/public`.
- No agregar una ruta Laravel alternativa para servir imagenes.
- No copiar archivos de `storage/app/public` a `public/storage` como workaround.
- No migrar a S3, CDN, object storage ni otro proveedor.
- No modificar schema, migraciones, base de datos o filas existentes.
- No ejecutar comandos de Hostinger, Cloudflare o produccion desde executors.
- No declarar staging saludable solo porque `/api/v2/auto/health` responde 200.
- No purgar cache como sustituto de una correccion de origen.

## Superficies y ownership

| Superficie | Target o sistema | Responsable | Permiso |
| --- | --- | --- | --- |
| Workflow por merge | `plg-platform-backend/.github/workflows/deploy-on-pr-merge.yml` | Worker Backend | Escribir solo este workflow |
| Workflow manual legacy staging | `plg-platform-backend/.github/workflows/staging.yml` | Worker Backend | Escribir solo este workflow |
| Workflow manual production | `plg-platform-backend/.github/workflows/production.yml` | Worker Backend | Escribir solo este workflow |
| Contrato Laravel | `plg-platform-backend/src/config/filesystems.php` | Orchestrator/Worker Backend | Lectura de referencia; no es target de escritura de esta spec |
| Origen web | Hostinger `apitest.plgeducation.com` | Humano operador | Cambiar y evidenciar document root/permisos |
| Verificacion | root reports y evidencia de staging | Orchestrator | Consolidar, no cambiar producto |

El orchestrator conserva ownership de esta spec, plan, reportes y estado
`.flow`. Los executors no pueden editar esta spec, workflows, secretos,
document root, datos, ni crear despliegues por cuenta propia durante la fase
de definicion y revision.

## Actores y responsabilidades

| Actor | Accion autorizada | Evidencia minima |
| --- | --- | --- |
| Worker Backend | Implementar el guard del symlink en los workflows autorizados | diff acotado, validacion YAML/shell y handoff |
| Executor de investigacion | Inspeccionar superficies y riesgos sin escribir producto | reporte read-only con archivos y hallazgos |
| Executor revisor | Revisar la spec y el plan sin modificar archivos | review PASS/FAIL y riesgos |
| Humano Hostinger | Configurar document root y permisos del origen | valor anterior/nuevo, fecha, host y resultado HTTP |
| Humano de staging | Ejecutar upload y seleccionar un asset controlado | request id sin secretos y URL redactada |
| Orchestrator | Resolver DAG, gates, evidencia y decision de release | reportes G0-G6 |

## Invariantes

1. El archivo se guarda en `storage/app/public/student_photos`.
2. `public/storage` existe como enlace simbolico, no como copia materializada.
3. El destino resuelto del enlace es `storage/app/public` bajo el `APP_PATH`
   desplegado.
4. La URL persistida y devuelta conserva el origen canonico y no contiene
   `/public` como prefijo publico.
5. Un deploy con symlink ausente, roto o mal apuntado falla antes de declarar
   el entorno listo, tanto en staging como en produccion.
6. Un document root distinto de `src/public` bloquea el rollout aunque el
   symlink local del proyecto sea correcto, tanto en staging como en
   produccion.
7. Un asset real de prueba debe responder `200` y `Content-Type: image/*`.
8. La prueba de asset no puede depender de un nombre de archivo, estudiante,
   token o cookie pegado en un repositorio o log.
9. Ningun workflow agrega migraciones, seeders ni comandos de datos como parte
   de este hardening.
10. La API privada y las mutaciones siguen siendo dinamicas y no cacheadas.

## Contrato de deploy

Los workflows de staging y produccion deben ejecutar, en este orden, dentro del
`APP_PATH` remoto:

1. resolver y conservar el `.env` remoto;
2. instalar la version desplegada;
3. limpiar configuracion cacheada;
4. ejecutar `php artisan storage:link` de forma idempotente;
5. verificar:
   - `public/storage` es symlink;
   - el destino resuelto es `storage/app/public`;
   - el directorio destino existe y es legible;
6. cachear config/rutas/vistas;
7. ejecutar el healthcheck Laravel;
8. en staging, ejecutar el gate de asset estatico usando una fixture efimera
   controlada;
9. en produccion, conservar el smoke post-deploy autorizado sin crear datos de
   estudiantes;
10. escribir el release marker solo despues de todos los gates, en los
    workflows que ya tienen release marker.

La fixture preferida y obligatoria por defecto es un PNG sintetico de 1x1,
creado temporalmente en:

```text
storage/app/public/.softos/staging-asset-fixture.png
```

El workflow debe crearla solo durante el deploy, verificar su URL bajo
`/storage/.softos/staging-asset-fixture.png`, registrar status y MIME sin
contenido binario, y eliminarla despues de la prueba. Si se ofrece un input
alternativo en el futuro, debe rechazar cualquier ruta fuera de
`storage/app/public` y requerir una decision aprobada en esta spec.

No se permite crear una foto de un estudiante real solo para satisfacer el
gate. El endpoint de subida y el read-after-write con dos estudiantes siguen
siendo evidencia humana de la spec de integridad de imagen.

El workflow `deploy-on-pr-merge.yml` sirve ambos entornos. La operacion
`storage:link` y su asercion deben ejecutarse para `DEPLOY_ENV=staging` y
`DEPLOY_ENV=production`. La fixture sintetica HTTP es obligatoria solo para
staging en esta spec; el camino productivo no debe crear fixtures ni datos de
estudiantes. La spec autoriza cambiar el workflow productivo unicamente para
materializar y verificar el symlink, sin modificar migraciones, rutas,
variables de negocio o el orden restante del deploy.

## Contrato de origen Hostinger

El operador humano debe verificar en staging y produccion:

```text
Document root = <APP_PATH>/public
Symlink       = <APP_PATH>/public/storage
Target        = <APP_PATH>/storage/app/public
```

El valor exacto de `<APP_PATH>` no se guarda en la spec ni en reportes
publicos. Se documentan solo el entorno, el host, el valor anterior y el
resultado.

Si Hostinger no permite apuntar el dominio a `<APP_PATH>/public`, el operador
debe detener la ejecucion y escalar la limitacion. No se autoriza introducir
`/public` en `photo_url`, copiar storage al document root ni agregar rewrites
que expongan rutas internas.

## Matriz de diagnostico y decision

| Observacion | Diagnostico | Decision |
| --- | --- | --- |
| `public/storage` no existe | Falta materializacion del enlace | Corregir workflow y bloquear hasta verificar |
| `public/storage` no es symlink | Deploy incorrecto o artefacto manual | Detener, reparar de forma idempotente y registrar |
| Symlink apunta fuera de `APP_PATH/storage/app/public` | Configuracion/ruta peligrosa | Bloquear y escalar, no seguir |
| Symlink correcto pero `/storage/...` devuelve 404 | Document root o permisos | Bloquear y exigir verificacion Hostinger |
| `/storage/...` devuelve HTML 404 | El request cae al front controller/origen equivocado | Bloquear y corregir document root |
| `/storage/...` devuelve 200 no-image | MIME/asset boundary incorrecto | Bloquear, no aceptar por status solamente |
| `/storage/...` devuelve 200 `image/*` | Entrega estatica confirmada | Permitir siguiente gate |
| Healthcheck 200 pero asset falla | Liveness sin entrega estatica | Staging no esta listo |
| `storage:link` falla por permisos | Accion humana/infraestructura | Detener y escalar a Hostinger |
| Asset real no coincide con archivo persistido | Falla de upload o contrato API | Reabrir spec de integridad de imagen |

## Stop conditions

- Detener antes de modificar workflows si los targets no coinciden con los
  workflows activos del backend.
- Detener antes de rollout si el document root real no esta confirmado.
- Detener si `storage:link` requiere borrar un enlace o archivo cuya propiedad
  no se puede resolver de forma segura.
- Detener si el destino del enlace queda fuera de `APP_PATH/storage/app/public`.
- Detener si el gate de asset necesita credenciales de estudiante o PII.
- Detener si la solucion propuesta cambia rutas API, contratos frontend o
  URLs para compensar Hostinger.
- Detener si el deploy intenta ejecutar migraciones, seeders o tareas de
  produccion.
- Detener si falta evidencia persistente del run de GitHub Actions o del
  origen HTTP.

## Slice Breakdown

```yaml
- name: staging-static-link-workflow-guard
  repo: plg-platform-backend
  targets:
    - ../../plg-platform-backend/.github/workflows/deploy-on-pr-merge.yml
    - ../../plg-platform-backend/.github/workflows/staging.yml
    - ../../plg-platform-backend/.github/workflows/production.yml
  hot_area: staging deploy static asset boundary
  depends_on:
    - hostinger-document-root-preflight
  slice_mode: minimal-change
  surface_policy: required
  minimum_valid_completion: all staging and production workflows materialize and verify public/storage before declaring the environment ready
  validated_noop_allowed: false
  acceptable_evidence:
    - workflow diff limited to authorized steps
    - YAML/shell validation
    - dry-run or focused workflow contract test
    - local workflow contract evidence
    - successful staging workflow with symlink evidence before rollout
  stop_conditions:
    - stop rollout on unresolved Hostinger document root
    - stop on unsafe symlink replacement

- name: staging-static-asset-gate
  repo: plg-platform-backend
  targets:
    - ../../plg-platform-backend/.github/workflows/deploy-on-pr-merge.yml
    - ../../plg-platform-backend/.github/workflows/staging.yml
  hot_area: staging static asset HTTP verification
  depends_on:
    - staging-static-link-workflow-guard
  slice_mode: minimal-change
  surface_policy: required
  minimum_valid_completion: one controlled image fixture is verified over HTTP as 200 image/* without secrets
  validated_noop_allowed: false
  acceptable_evidence:
    - fixture path and MIME contract test
    - workflow logs without secret values
    - staging HTTP headers and status
  stop_conditions:
    - stop if evidence requires real student credentials or PII
    - stop if the origin serves HTML or redirects to internal storage paths

- name: hostinger-document-root-preflight
  repo: plg-platform-harness
  targets:
    - ../../specs/features/2026-09-14-staging-static-asset-delivery-hardening.spec.md
  hot_area: Hostinger staging and production origins
  depends_on: []
  slice_mode: governance
  surface_policy: forbidden
  minimum_valid_completion: human runbook and evidence contract distinguish document root from symlink readiness in both environments
  validated_noop_allowed: true
  acceptable_evidence:
    - human preflight record
    - public healthcheck and asset probe
    - rollback value recorded without secrets
  stop_conditions:
    - stop when Hostinger access or document-root capability is unavailable

- name: cross-repo-release-evidence
  repo: plg-platform-harness
  targets:
    - ../../specs/features/2026-09-14-staging-static-asset-delivery-hardening.spec.md
  hot_area: cross-repo staging release evidence
  depends_on:
    - staging-static-asset-gate
    - hostinger-document-root-preflight
  slice_mode: verification-only
  surface_policy: forbidden
  minimum_valid_completion: root evidence links workflow, origin and HTTP asset results without claiming code changes
  validated_noop_allowed: true
  acceptable_evidence:
    - workflow run URL and conclusion
    - Hostinger document-root record
    - static asset HTTP probe
    - G0-G6 closeout report
  stop_conditions:
    - stop if workflow and origin evidence refer to different commits or environments

```

## Gate Mapping

| Gate | Required evidence | Owner | Blocking rule |
| --- | --- | --- | --- |
| G0 intake | spec path, incident context, executor request and authority boundary | Orchestrator | no planning without captured scope |
| G1 research/preflight | refreshed backend graph, current workflows, Engram recall, Hostinger document-root record | Orchestrator + Humano Hostinger | workflow implementation may proceed; rollout is blocked until origin capability is confirmed |
| G2 plan | approved spec, disjoint slices, target ownership and fixture algorithm | Orchestrator | no implementation with overlapping ownership |
| G3 review artifact | executor handoffs, workflow diff, production-path impact review | Worker Backend + Reviewer | no validation with unauthorized diff |
| G4 validation | workflow contract checks, symlink assertion, healthcheck and asset `200 image/*` | Worker Backend + Orchestrator | no promotion on any failed check |
| G5 release readiness | matching commit, staging run, origin evidence and human smoke | Orchestrator + Humano de staging | no production action from this spec |
| G6 closeout | reports, rollback value, residual risks and final state consistency | Orchestrator | no closeout with healthcheck-only evidence |

## Verification Matrix

```yaml
- name: spec-review
  level: custom
  command: python3 ./flow workspace exec -- python3 ./flow spec review specs/features/2026-09-14-staging-static-asset-delivery-hardening.spec.md --json
  blocking_on: [review]
  environments: [local]

- name: spec-ci
  level: custom
  command: python3 ./flow workspace exec -- python3 ./flow ci spec specs/features/2026-09-14-staging-static-asset-delivery-hardening.spec.md --json
  blocking_on: [ci]
  environments: [local]

- name: backend-workflow-contract
  level: custom
  command: python3 ./flow repo exec plg-platform-backend -- sh -lc 'git diff --check && test -f .github/workflows/deploy-on-pr-merge.yml && test -f .github/workflows/staging.yml && test -f .github/workflows/production.yml'
  blocking_on: [ci]
  environments: [local]
  notes: la validacion final debe anadir parser YAML o test de contrato si el repo lo soporta

- name: storage-link-contract
  level: custom
  command: "manual remote assertion: test -L public/storage && test \"$(readlink -f public/storage)\" = \"$(readlink -f storage/app/public)\""
  blocking_on: [release]
  environments: [staging, production]

- name: staging-health
  level: smoke
  command: curl --fail --silent --show-error --location https://apitest.plgeducation.com/api/v2/auto/health
  blocking_on: [release]
  environments: [staging]

- name: staging-static-asset
  level: e2e
  command: manual HTTP HEAD/GET against a controlled image fixture; require 200 and image/*
  blocking_on: [release]
  environments: [staging]

- name: production-health
  level: smoke
  command: manual post-deploy healthcheck for api.plgeducation.com
  blocking_on: [release]
  environments: [production]

- name: production-static-asset-smoke
  level: e2e
  command: manual approved smoke against an existing controlled image; require 200 and image/*
  blocking_on: [approval, release]
  environments: [production]
  notes: no fixture creation and no student upload from the deploy workflow

- name: human-profile-read-after-write
  level: e2e
  command: manual Hub upload, GET /api/v2/hub/me, browser reload and two-student isolation
  blocking_on: [approval, release]
  environments: [staging]
  notes: pertenece tambien a 2026-09-14-student-profile-image-integrity

- name: cross-repo-static-delivery-evidence
  level: integration
  command: "link backend deploy evidence with root spec evidence; require matching commit, environment and asset probe"
  blocking_on: [release]
  environments: [staging]
  notes: cruza el workflow del backend con la evidencia operacional de Hostinger sin editar producto
```

## Test Plan

- [@test] ../../plg-platform-backend/src/tests/Feature/ProfileImageUploadUrlTest.php

## Acceptance criteria

1. Los workflows de staging y produccion ejecutan `storage:link` antes de
   declarar disponibilidad del entorno.
2. Ambos entornos fallan ante un symlink ausente, roto o mal apuntado.
3. Los document roots de `apitest.plgeducation.com` y
   `api.plgeducation.com` estan confirmados como `<APP_PATH>/public` por
   evidencia humana.
4. `public/storage` resuelve exactamente a `storage/app/public` en ambos
   entornos.
5. Una imagen controlada responde `200` con `Content-Type: image/*` desde
   `/storage/...` en staging, y el smoke aprobado se conserva para produccion.
6. La URL verificada no contiene `/public` como prefijo publico ni expone
   `/storage/app/public`.
7. El healthcheck y el gate estatico de staging se ejecutan antes del release
   marker; el workflow compartido aplica el symlink tambien a produccion sin
   crear fixtures.
8. No se agregan migraciones, seeders ni comandos de datos como parte de este
   hardening; los inputs y comandos existentes de cada workflow permanecen
   compatibles y conservan su contrato previo.
9. No se modifican rutas, controladores, clientes o schema.
10. La evidencia no contiene secretos, cookies, tokens, credenciales ni PII.
11. La spec, su review y su CI pasan; los executors entregan handoffs
    read-only completos antes de cualquier worker de implementacion.

## Rollout

1. Revisar y aprobar esta spec.
2. Confirmar los document roots de staging y produccion y guardar rollback.
3. Implementar el guard en los tres workflows, en worktrees separados si el
   runtime lo exige, sin tocar codigo de negocio.
4. Ejecutar CI y revision independiente.
5. Promover a staging y validar symlink, health y asset estatico.
6. Repetir el smoke humano de la spec de integridad de imagen.
7. Promover a produccion solo con aprobacion humana posterior a staging y
   validar symlink, health y smoke de asset existente.

## Rollback

- Revertir el cambio de workflow si introduce fallos en el deploy.
- Restaurar el document root anterior solo con el valor previamente registrado.
- No borrar imagenes, filas, `storage/app/public` ni enlaces sin determinar su
  ownership.
- No usar `/public` en URLs ni copiar assets como rollback funcional.

## Evidence and closeout

El paquete minimo de cierre debe incluir:

- review de spec y `flow ci spec`;
- inventario de executors y handoffs read-only;
- diff autorizado de workflows, si la implementacion se aprueba despues;
- evidencia de `storage:link` y `readlink`;
- evidencia humana de document root y rollback;
- URL de workflow de staging y resultado final;
- headers/status del asset controlado, sin URL con PII;
- smoke humano de upload y read-after-write;
- estado G0-G6 y riesgos residuales.

La spec no se considera cerrada por un healthcheck 200 aislado.
