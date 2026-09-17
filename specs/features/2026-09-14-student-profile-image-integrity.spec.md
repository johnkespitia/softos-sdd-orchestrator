---
schema_version: 3
name: "Integridad de imagen de perfil de estudiante"
description: "Investigar y corregir la integridad de las fotos de perfil de estudiantes en el flujo completo de carga, persistencia, respuesta API y renderizado. El incidente observado en producci\u00f3n/staging indica que la imagen puede no guardarse, no reconocerse o no mostrarse despu\u00e9s de la carga. La inspecci\u00f3n inicial encontr\u00f3 que el backend Hub persiste Student.main_photo mediante el disco public en student_photos y devuelve photo_url; GET /api/v2/hub/me lo expone como student.photo_url; POST /api/v2/hub/profile/photo acepta image o main_photo; Hub normaliza photo_url a picture e invalida la consulta de perfil. El Dashboard legado usa StudentController.updateImage y entity.main_photo. El agente debe determinar la causa real entre filesystem/disco public, enlace o document root, URL persistida, serializaci\u00f3n, estado del cliente, CORS/autenticaci\u00f3n o entrega HTTP, y corregir solo las superficies justificadas. Se debe conservar la URL API can\u00f3nica sin /public y no usar una regla de cach\u00e9 como soluci\u00f3n. Los cambios operativos de Hostinger, almacenamiento, permisos o despliegue requieren acci\u00f3n humana y evidencia, no credenciales en el workspace."
status: approved
owner: platform
single_slice_reason: ""
multi_domain: true
phases:
  - intake
  - diagnosis
  - implementation
  - staging
  - production
depends_on:
  - spec-as-source-operating-model
  - spec-driven-delivery-and-infrastructure
  - repo-routing-and-worktree-orchestration
  - dashboard-frontend-foundation-alignment
  - hub-frontend-foundation-alignment
  - plg-platform-backend-foundation-alignment
  - 2026-09-12-api-public-root-canonicalization
required_runtimes:
  - python
  - node-npm-react-cra
  - node
  - php-laravel8-apache
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
  - ../../specs/features/2026-09-14-student-profile-image-integrity.spec.md
  - ../../plg-platform-backend/src/app/Services/Hub/HubProfileService.php
  - ../../plg-platform-backend/src/app/Http/Controllers/Api/V2/Hub/HubProfilePhotoController.php
  - ../../plg-platform-backend/src/app/Http/Controllers/StudentController.php
  - ../../plg-platform-backend/src/config/filesystems.php
  - ../../plg-platform-backend/src/tests/Feature/HubV2ProfilePreferencesTest.php
  - ../../plg-platform-backend/src/tests/Feature/ProfileImageUploadUrlTest.php
  - ../../hub-frontend/src/shared/api/hub.ts
  - ../../hub-frontend/src/shared/api/normalizeHub.ts
  - ../../hub-frontend/src/features/student-dashboard/api.ts
  - ../../hub-frontend/src/features/student-dashboard/components/profile/ProfilePhotoPanel.tsx
  - ../../hub-frontend/src/features/student-dashboard/pages/StudentProfilePage.test.tsx
  - ../../hub-frontend/src/shared/api/hub.test.ts
  - ../../hub-frontend/src/features/student-dashboard/api.test.ts
  - ../../dashboard-frontend/src/src/pages/Students/FormPicture.jsx
  - ../../dashboard-frontend/src/src/pages/Students/index.jsx
  - ../../dashboard-frontend/src/src/pages/Students/StudentRow.jsx
  - ../../dashboard-frontend/src/src/pages/Students/DetailCard.jsx
---

# Integridad de imagen de perfil de estudiante

## Objetivo

Investigar y corregir la integridad de las fotos de perfil de estudiantes en el flujo completo de carga, persistencia, respuesta API y renderizado. El incidente observado en producción/staging indica que la imagen puede no guardarse, no reconocerse o no mostrarse después de la carga. La inspección inicial encontró que el backend Hub persiste Student.main_photo mediante el disco public en student_photos y devuelve photo_url; GET /api/v2/hub/me lo expone como student.photo_url; POST /api/v2/hub/profile/photo acepta image o main_photo; Hub normaliza photo_url a picture e invalida la consulta de perfil. El Dashboard legado usa StudentController.updateImage y entity.main_photo. El agente debe determinar la causa real entre filesystem/disco public, enlace o document root, URL persistida, serialización, estado del cliente, CORS/autenticación o entrega HTTP, y corregir solo las superficies justificadas. Se debe conservar la URL API canónica sin /public y no usar una regla de caché como solución. Los cambios operativos de Hostinger, almacenamiento, permisos o despliegue requieren acción humana y evidencia, no credenciales en el workspace.

## Contexto confirmado

- `HubProfileService::updatePhoto` valida y guarda en el disco `public`, bajo
  `student_photos`, y persiste la URL en `Student.main_photo`.
- `HubProfileService::buildStudentDto` expone ese valor como `photo_url` en
  `GET /api/v2/hub/me`.
- `HubProfilePhotoController` recibe el campo multipart `image` o `main_photo`
  y devuelve `{ data: { photo_url } }`.
- Hub normaliza `photo_url` a `picture`, invalida la consulta de perfil y
  renderiza `student.picture` en `ProfilePhotoPanel`.
- El Dashboard legado usa `POST /hr-management/students-image/{id}` y el campo
  `main_photo`; su formulario y su refresco deben verificarse por separado.
- Existen pruebas de subida Hub y de URL absoluta, pero falta evidencia de que
  la URL sea descargable desde el origen desplegado y de que ambos clientes
  mantengan el mismo dato.

## Foundations y domains

Las foundations aplicables estan declaradas en `depends_on`: modelo de spec,
delivery e infraestructura, routing/worktrees y alineacion de los tres repos.
Tambien depende de `2026-09-12-api-public-root-canonicalization` porque la
imagen debe respetar el origen API canonico ya desplegado.

No aplica un domain nuevo: `Student.main_photo` ya existe y este cambio solo
corrige el transporte y la presentacion de un asset de perfil existente.

## Problema a resolver

La foto puede no persistirse, apuntar a un recurso que el servidor no entrega o
no reflejarse en la UI despues de una subida exitosa. La causa debe demostrarse
antes de modificar el contrato.

Hipotesis permitidas para diagnostico, sin asumir ninguna como causa:

- el disco `public` guarda en una ruta distinta de la ruta servida;
- falta o apunta mal el enlace `public/storage` o el document root;
- `APP_URL` o `filesystems.disks.public.url` genera una URL incorrecta;
- el formulario envia un objeto o un campo distinto al multipart esperado;
- un consumidor espera `main_photo` o `picture` en lugar de `photo_url`;
- el cliente actualiza el servidor pero no vuelve a leer el perfil correcto;
- la URL responde con 404, HTML, MIME incorrecto, CORS o autenticacion inesperada.

## Alcance

### Incluye

- Reproducir la subida autenticada en Hub y la actualizacion administrativa en
  Dashboard.
- Trazar request, respuesta, valor persistido, existencia del archivo y GET de
  la URL de imagen en local/staging segun disponibilidad.
- Corregir solo la causa demostrada en los targets de Backend, Hub o Dashboard.
- Agregar o ajustar pruebas focales de persistencia, contrato API, multipart,
  refresco de estado y renderizado.
- Documentar la accion humana si el origen requiere document root, `storage:link`,
  permisos o configuracion de URL.

### No incluye

- No cambiar rutas Laravel para agregar o quitar `/public`.
- No cambiar DNS, proxy, Cache Rules ni reglas de respuesta de Cloudflare.
- No migrar almacenamiento, cambiar proveedor, modificar schema ni borrar
  masivamente imagenes existentes.
- No modificar imagenes de profesores, eventos, beneficios, rewind, logos o
  assets de correo.
- No cambiar autenticacion o permisos salvo regresion demostrada por prueba.
- No ejecutar acciones de Hostinger o produccion desde un executor.

## Repos afectados y ownership

| Repo | Targets autorizados | Ownership |
| --- | --- | --- |
| `plg-platform-backend` | servicio/controladores/config de filesystem y pruebas de perfil | Worker Backend |
| `hub-frontend` | API, normalizador, hook, panel y pruebas de perfil | Worker Hub |
| `dashboard-frontend` | formulario, refresco y render de foto en `pages/Students` | Worker Dashboard |
| `plg-platform-harness` | esta spec y evidencia del workflow | Orchestrator |

Cada worker escribe unicamente sus targets. No se permiten cambios en otro repo,
workflows de despliegue, `.flow/**` manualmente ni archivos no autorizados.

## Invariantes

1. Un estudiante autenticado solo actualiza su propia foto mediante Hub.
2. Una subida exitosa deja archivo legible y `students.main_photo` igual a la
   URL devuelta.
3. `GET /api/v2/hub/me` devuelve el mismo `photo_url` sin cruzar estudiantes.
4. La URL de imagen responde `200` con `Content-Type: image/*` y sin `/public`
   como prefijo publico.
5. Hub muestra la foto despues de subirla y despues de recargar.
6. Dashboard conserva endpoint, autorizacion y campo multipart actuales, salvo
   correccion justificada y probada.
7. Una subida fallida no deja `main_photo` apuntando a un archivo inexistente.
8. Las APIs privadas y mutaciones siguen siendo dinamicas.

## Contrato funcional

### Hub

- `POST /api/v2/hub/profile/photo`, sesion Sanctum, multipart y campo `image`
  o `main_photo`.
- Imagen JPEG, PNG, JPG o GIF, maximo 2048 KB; errores 401 o 422.
- `200` con `{ "data": { "photo_url": "https://.../storage/student_photos/..." } }`.
- `GET /api/v2/hub/me` refleja el mismo valor despues de la subida.

### Dashboard legado

- `POST /hr-management/students-image/{studentId}`, Bearer, multipart y
  `main_photo`.
- El flujo debe enviar realmente el archivo y refrescar la lista/detalle.
- No renombrar el contrato sin decision explicita y prueba de compatibilidad.

## Flujo de diagnostico y ejecucion

1. Capturar reproduccion con entorno, estudiante de prueba y request id, sin
   tokens, cookies ni datos personales innecesarios.
2. Verificar recepcion, ruta de almacenamiento, URL persistida y respuesta API.
3. Verificar desde HTTP y navegador el estado y MIME de la URL de imagen.
4. Verificar en cada cliente campo enviado, respuesta, invalidacion/refresco y
   campo final usado por `<img>`.
5. Corregir solo la causa demostrada. Si es Hostinger/filesystem, detener el
   worker y producir runbook humano.
6. Ejecutar pruebas focales, revision independiente y smoke humano en staging.

## Slice Breakdown

```yaml
- name: backend-profile-image-contract
  targets:
    - ../../plg-platform-backend/src/app/Services/Hub/HubProfileService.php
    - ../../plg-platform-backend/src/app/Http/Controllers/Api/V2/Hub/HubProfilePhotoController.php
    - ../../plg-platform-backend/src/app/Http/Controllers/StudentController.php
    - ../../plg-platform-backend/src/config/filesystems.php
    - ../../plg-platform-backend/src/tests/Feature/HubV2ProfilePreferencesTest.php
    - ../../plg-platform-backend/src/tests/Feature/ProfileImageUploadUrlTest.php
  hot_area: plg-platform-backend/profile-image-storage
  depends_on: []
  slice_mode: minimal-change
  surface_policy: optional
  minimum_valid_completion: demostrar y corregir, si aplica, persistencia y entrega sin romper contratos Hub y Dashboard
  validated_noop_allowed: true
  acceptable_evidence:
    - pruebas focales PHPUnit
    - comprobacion de archivo y valor persistido con Storage::fake
    - respuesta API y URL verificadas sin secretos
  stop_conditions:
    - detener si la causa exige accion humana de Hostinger, permisos o deploy
    - detener si la correccion requiere cambiar rutas, schema o contratos fuera de estos targets

- name: hub-profile-image-client
  targets:
    - ../../hub-frontend/src/shared/api/hub.ts
    - ../../hub-frontend/src/shared/api/normalizeHub.ts
    - ../../hub-frontend/src/features/student-dashboard/api.ts
    - ../../hub-frontend/src/features/student-dashboard/components/profile/ProfilePhotoPanel.tsx
    - ../../hub-frontend/src/features/student-dashboard/pages/StudentProfilePage.test.tsx
    - ../../hub-frontend/src/shared/api/hub.test.ts
    - ../../hub-frontend/src/features/student-dashboard/api.test.ts
  hot_area: hub-frontend/student-profile-image
  depends_on:
    - backend-profile-image-contract
  slice_mode: minimal-change
  surface_policy: optional
  minimum_valid_completion: enviar el archivo correcto, consumir photo_url, actualizar estado y renderizar la URL vigente
  validated_noop_allowed: true
  acceptable_evidence:
    - pruebas Vitest focales de request, normalizacion, invalidacion y UI
    - typecheck, lint y build del Hub
  stop_conditions:
    - detener si el defecto real esta en origen o filesystem
    - no introducir URLs hardcodeadas ni compensaciones con /public

- name: dashboard-student-image-upload
  targets:
    - ../../dashboard-frontend/src/src/pages/Students/FormPicture.jsx
    - ../../dashboard-frontend/src/src/pages/Students/index.jsx
    - ../../dashboard-frontend/src/src/pages/Students/StudentRow.jsx
    - ../../dashboard-frontend/src/src/pages/Students/DetailCard.jsx
  hot_area: dashboard-frontend/students-profile-image
  depends_on:
    - backend-profile-image-contract
  slice_mode: minimal-change
  surface_policy: optional
  minimum_valid_completion: enviar multipart main_photo y reflejar la imagen persistida sin ampliar la superficie legacy
  validated_noop_allowed: true
  acceptable_evidence:
    - prueba focal o evidencia reproducible del formulario
    - pruebas CRA existentes y diff check
  stop_conditions:
    - detener si exige migrar el Dashboard completo o tocar profesores
    - no modificar contratos no relacionados con estudiantes

- name: human-origin-storage-preflight
  targets:
    - ../../specs/features/2026-09-14-student-profile-image-integrity.spec.md
  hot_area: human/hostinger-storage-delivery
  depends_on:
    - backend-profile-image-contract
  slice_mode: governance
  surface_policy: forbidden
  minimum_valid_completion: runbook humano con comprobacion de document root, storage link, permisos, URL y rollback
  validated_noop_allowed: true
  acceptable_evidence:
    - checklist humano firmado o fechado
    - curl de URL de imagen sin secretos
    - evidencia de rollback disponible
  stop_conditions:
    - el executor no ejecuta Hostinger, Cloudflare, GitHub ni produccion
    - detener si se solicitan credenciales o datos reales de estudiantes
```

## Decision table

| Hallazgo | Decision |
| --- | --- |
| Archivo, URL y GET responden bien, pero Hub no cambia | Corregir Hub y probar estado/renderizado |
| Hub envia multipart incorrecto o no consume `photo_url` | Corregir solo adaptador/hook autorizado |
| `main_photo` es correcto pero la URL responde 404 o HTML | Bloquear parche de cliente y escalar origen/storage a humano |
| Dashboard no envia un multipart real | Corregir formulario y cubrir request |
| Una foto aparece para otro estudiante | Bloquear rollout e investigar ownership/query cache |
| Requiere Cloudflare, DNS o `/public` | Rechazar por fuera de alcance y abrir intake separado |

## Verification Matrix

```yaml
- name: backend-profile-image-tests
  level: custom
  command: python3 ./flow repo exec plg-platform-backend -- php -d memory_limit=512M src/vendor/bin/phpunit -c src/phpunit.xml src/tests/Feature/HubV2ProfilePreferencesTest.php src/tests/Feature/ProfileImageUploadUrlTest.php
  blocking_on: [ci]
  environments: [local]
  notes: valida recepcion, persistencia, URL y respuesta Hub

- name: hub-profile-image-tests
  level: custom
  command: python3 ./flow repo exec hub-frontend -- pnpm test --run src/features/student-dashboard/pages/StudentProfilePage.test.tsx src/shared/api/hub.test.ts src/features/student-dashboard/api.test.ts
  blocking_on: [ci]
  environments: [local]
  notes: valida multipart, normalizacion, invalidacion y UI

- name: hub-quality-gates
  level: integration
  command: python3 ./flow repo exec hub-frontend -- sh -lc 'pnpm lint && pnpm typecheck && pnpm build'
  blocking_on: [ci]
  environments: [local]
  notes: confirma que la correccion Hub no rompe el build

- name: dashboard-profile-image-tests
  level: custom
  command: python3 ./flow repo exec dashboard-frontend -- sh -lc 'CI=true npm --prefix src test -- --watchAll=false'
  blocking_on: [ci]
  environments: [local]
  notes: conserva el comportamiento CRA del Dashboard

- name: human-staging-profile-image-smoke
  level: e2e
  command: manual curl, DevTools y navegador con dos estudiantes de prueba
  blocking_on: [approval, release]
  environments: [staging]
  notes: exige upload, read-after-write, GET 200 image/*, aislamiento y refresco visual

- name: human-production-profile-image-smoke
  level: e2e
  command: repetir el checklist aprobado de staging con datos controlados
  blocking_on: [approval, release]
  environments: [production]
  notes: no se ejecuta sin aprobacion humana posterior a staging
```

## Criterios de aceptacion

- Hub carga una imagen valida y devuelve `photo_url` absoluto; archivo,
  `main_photo` y `GET /api/v2/hub/me` coinciden.
- La URL responde `200` y `Content-Type: image/*` sin `/public` en la URL.
- Hub muestra la imagen despues de subirla y despues de recargar.
- Dos estudiantes de prueba no observan la foto del otro.
- Dashboard envia un archivo multipart real y refleja la imagen actualizada.
- Pasan las pruebas focales y no hay cambios fuera de targets.
- Toda accion humana de Hostinger queda evidenciada con rollback, sin secretos.

## Test plan

- [@test] ../../plg-platform-backend/src/tests/Feature/HubV2ProfilePreferencesTest.php
- [@test] ../../plg-platform-backend/src/tests/Feature/ProfileImageUploadUrlTest.php
- [@test] ../../hub-frontend/src/features/student-dashboard/pages/StudentProfilePage.test.tsx
- [@test] ../../hub-frontend/src/shared/api/hub.test.ts
- [@test] ../../hub-frontend/src/features/student-dashboard/api.test.ts
- [@test] ../../dashboard-frontend/src/src/deploy.ssh-workflows.test.js

## Rollout

1. Aprobar esta spec y crear plan con ownership disjunto.
2. Ejecutar Backend y luego clientes en worktrees separados.
3. Ejecutar CI y revision independiente.
4. Obtener evidencia humana en staging.
5. Promover a produccion solo con aprobacion humana y repetir smoke.

## Rollback

- Revertir el release de codigo que introdujo la regresion sin borrar filas ni
  archivos validos.
- Si hubo accion humana en Hostinger, restaurar el document root o enlace
  anterior documentado.
- No borrar masivamente `student_photos` ni purgar cache como sustituto.

## Handoff para el siguiente agente

Leer esta spec, las foundations de `depends_on`, el `AGENTS.md` del repo y el
contexto de skills con `python3 ./flow skills context --repo <repo> --json`.
Trabajar solo en el slice asignado, sin delegar, commit, push o release.
Entregar archivos modificados, comandos, resultados, riesgos y siguiente gate.
Hostinger, Cloudflare, GitHub y produccion son acciones humanas.
