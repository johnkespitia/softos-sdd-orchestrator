---
schema_version: 3
name: "Plan Scoped Meet Transcript Lifecycle"
description: "Replace professor-global Meet links with plan-owned spaces, verified cohosts, recoverable transcript capture and efficient versioned consumption."
status: draft
owner: platform
single_slice_reason: ""
multi_domain: true
phases: []
depends_on:
  - specs/000-foundation/spec-as-source-operating-model.spec.md
  - specs/000-foundation/repo-routing-and-worktree-orchestration.spec.md
  - specs/000-foundation/plg-platform-backend-coding-style-and-quality-contract.spec.md
  - specs/000-foundation/dashboard-frontend-coding-style-and-quality-contract.spec.md
  - specs/000-foundation/hub-frontend-coding-style-and-quality-contract.spec.md
required_runtimes: [php-laravel8-apache, node-npm-react-cra, node]
required_services: []
required_capabilities: [laravel8, react-cra, vite-react, typescript]
stack_projects: []
stack_services: []
stack_capabilities: []
targets:
  - ../../specs/features/plg/2026-09-11-plan-scoped-meet-transcript-lifecycle.spec.md
  - ../../plg-platform-backend/src/app/Services/GoogleWorkspace/**
  - ../../plg-platform-backend/src/app/Services/Actions/**
  - ../../plg-platform-backend/src/app/Services/Hub/HubPlansPresentationService.php
  - ../../plg-platform-backend/src/app/Services/Hub/HubProfileService.php
  - ../../plg-platform-backend/src/app/Support/CanonicalMeetLinkResolver.php
  - ../../plg-platform-backend/src/app/Models/GoogleMeet*.php
  - ../../plg-platform-backend/src/app/Models/GoogleWorkspace*.php
  - ../../plg-platform-backend/src/app/Models/ImpartedClass.php
  - ../../plg-platform-backend/src/app/Models/ContratedPlan.php
  - ../../plg-platform-backend/src/app/Models/ProfessorActionDraft.php
  - ../../plg-platform-backend/src/app/Http/Controllers/GoogleWorkspace/**
  - ../../plg-platform-backend/src/app/Http/Controllers/Actions/Professor/**
  - ../../plg-platform-backend/src/app/Http/Controllers/Api/V2/Hub/HubClassesController.php
  - ../../plg-platform-backend/src/app/Http/Controllers/ContratedPlanController.php
  - ../../plg-platform-backend/src/app/Http/Controllers/ImpartedClassController.php
  - ../../plg-platform-backend/src/app/Http/Controllers/ProfessorController.php
  - ../../plg-platform-backend/src/app/Jobs/*Meet*.php
  - ../../plg-platform-backend/src/app/Jobs/*Workspace*.php
  - ../../plg-platform-backend/src/app/Console/Commands/*Meet*.php
  - ../../plg-platform-backend/src/app/Console/Kernel.php
  - ../../plg-platform-backend/src/app/Providers/AppServiceProvider.php
  - ../../plg-platform-backend/src/config/google.php
  - ../../plg-platform-backend/src/.env.example
  - ../../plg-platform-backend/src/routes/api.php
  - ../../plg-platform-backend/src/database/migrations/**
  - ../../plg-platform-backend/src/docs/openapi/**
  - ../../plg-platform-backend/src/public/docs/openapi/**
  - ../../plg-platform-backend/src/tests/Feature/**
  - ../../plg-platform-backend/src/tests/Unit/**
  - ../../dashboard-frontend/src/src/pages/ProfessorsDashboard/ClassScreen/**
  - ../../dashboard-frontend/src/src/pages/Plans/ClassScreen/**
  - ../../dashboard-frontend/src/src/services/transcriptService.js
  - ../../hub-frontend/src/features/class-management/**
  - ../../hub-frontend/src/features/student-class-process/**
  - ../../hub-frontend/src/shared/api/hub.ts
  - ../../hub-frontend/src/shared/i18n/**
test_refs:
  - ../../plg-platform-backend/src/tests/Unit/GoogleMeetPersistentSpaceCreatorTest.php
  - ../../plg-platform-backend/src/tests/Feature/GoogleMeetClassSessionBoundaryTest.php
  - ../../plg-platform-backend/src/tests/Feature/GoogleMeetClassTranscriptIngestionTest.php
  - ../../plg-platform-backend/src/tests/Feature/GoogleMeetTranscriptPresentationContractTest.php
  - ../../plg-platform-backend/src/tests/Feature/ProfessorActionsClassTranscriptTest.php
  - ../../dashboard-frontend/src/src/pages/Plans/ClassScreen/TranscriptPanel.test.jsx
  - ../../dashboard-frontend/src/src/pages/ProfessorsDashboard/ClassScreen/TranscriptPanel.test.jsx
  - ../../hub-frontend/src/features/class-management/components/ClassTranscriptPanel.test.tsx
  - ../../hub-frontend/src/features/student-class-process/components/ClassTranscriptSection.test.tsx
---

# Plan Scoped Meet Transcript Lifecycle

## Objective

Un espacio de Google Meet por plan contratado, propiedad del organizador institucional,
con profesor/cohost asignado por API aunque use cuenta Google personal. Cada clase
conserva sus conferencias y versiones de transcripcion sin depender del enlace global
del profesor. Recuperacion y consumo deben ser acotados, auditables y eficientes.

## Governing decision

- Plan significa `ContratedPlan`, no el producto de catalogo ni el profesor.
- Esta entrega reutiliza un espacio durante el plan; no crea uno por clase.
- La asignacion de COHOST ya existe por API: no introducir un proceso manual como camino normal.
- Persistir espacio, conferencia, clase, artefacto y version como conceptos distintos.
- Mantener el ingreso por las pantallas autenticadas de plan/clase actuales. No crear un redirect publico ni un nuevo sistema de enlaces cortos.
- Corte directo con migracion unica de planes, clases, transcripts y drafts existentes al nuevo modelo. Despues del corte hay una sola arquitectura, sin dual-read, modo legacy ni fallback por profesor.
- Todos los planes con clases pendientes y todas esas clases quedan preparados antes de reabrir el servicio. No recrear las clases ni cambiar sus IDs, fechas, asistencia o saldo academico.
- Migrar historia significa conservar su fuente real en el modelo nuevo, nunca atribuir una reunion pasada a un space recien creado. El tooling de conversion no forma parte de la lectura normal posterior.
- Los borradores basados en transcripts referencian versiones verificadas por backend.
- El alcance IA es contexto determinista acotado y procedencia; resumen generativo, embeddings y nuevos proveedores quedan diferidos.

## Context and observed inventory

Revision inicial sobre backend HEAD `eb515612f6ac4de80997d7eafdc179ec81cb75c9`.
La suite base paso por `flow ci repo`: 1361 tests, 6751 assertions, 2 skipped,
2026-09-12T01:56:52Z. Es evidencia del estado previo, no de esta feature.
`specs/domains/` solo contiene README al redactar: exclusion justificada de dependencia
de dominio inexistente; el vocabulario y las invariantes se definen aqui.

| Superficie observada | Problema | Disposicion obligatoria |
| --- | --- | --- |
| GoogleMeetPersistentSpaceCreator / PreviewCohostAssignmentClient | requestId v2 ignorado; GET/POST/GET verifica rol | Conservar verificacion; etapas recuperables y member identity |
| GoogleMeetProfessorProvisioningService | active con warnings; retorno temprano no repara rol | Nuevo servicio por plan; reparar mismo recurso |
| CanonicalMeetLinkResolver / HubPlansPresentationService | URL por usuario/profesor | Resolucion exclusiva por plan/clase |
| GoogleMeetClassLinkGate / ConferenceSessionBindingService | filtro por plan sin mapping, heuristica temporal | Plan derivado del space; cuarentena ante conflicto |
| GoogleMeetConferenceBoundaryService | reintentos por espacio pueden terminar siguiente llamada | Deshabilitar cierre remoto automatico en espacios compartidos |
| WorkspaceEventProcessor / ReconcileMeetConferenceSessionsJob | orden de eventos y primer available cortan recuperacion | Upsert monotono e inventario completo |
| TranscriptProvider / IngestionService | descarta state, vacio available, descargas repetidas | Estado remoto, versiones atomicas y exclusividad |
| TranscriptPresentationService | get/sort/slice completo por pagina | SQL keyset y metadata versionada |
| ProfessorTranscriptDraftProvenance / servicios de drafts y publish | procedencia declarada por cliente | Validacion de pertenencia y snapshot |
| TranscriptParticipantResolver | COHOST por email no vincula identidad PLG | Reproyeccion independiente del texto |
| TranscriptPanel de dashboard (profesor y HR) | efecto vuelve a intentar tras cualquier error | Reintentos finitos y reset de contexto |

## Scope and exclusions

Incluye clases regulares de planes contratados, docente titular y sustituciones ya
representadas por el sistema, vistas Hub/profesor/HR y acciones existentes de comentario
y cierre. Cambios a controladores de planes/profesores solo para lifecycle Meet y DTO de
enlace. Los globs de Services, migraciones, tests y OpenAPI autorizan exclusivamente este
contrato, no refactors de Classroom, OAuth general, scheduling, reportes o notificaciones.

Excluye clases diagnosticas, precios, asistencia academica, calificaciones, generacion
de informes ajenos al transcript, cambios de framework/lockfiles, pipelines de deploy,
grabaciones de audio/video y publicacion automatica de comentarios. Incluye conversion
unica de datos anteriores y verificacion antes del corte; excluye adaptadores permanentes
para clientes o enlaces anteriores. Tampoco revoca enlaces viejos en Google ni elimina
datos historicos masivamente. La historia verificable se sirve desde snapshots del modelo
nuevo; inconsistencias se conservan en cuarentena identificada, sin inventar evidencia.
Los timestamps de proveedor
permanecen UTC; no cambiar contratos de proyeccion temporal de otras specs.

## Actors and invariants

| Actor | Permisos y limites |
| --- | --- |
| Organizador institucional | Crea/configura space usando sujeto configurado, nunca impersona email personal externo |
| Profesor asignado | COHOST con email Google personal; lectura identificada solo para clases autorizadas |
| Sustituto vigente | Rol por intervalo de asignacion; misma politica de lectura actual, sin ampliar permisos |
| Alumno del plan | Transcript solo de clase cerrada; etiquetas ajenas seudonimizadas; sin IDs/provider URLs |
| HR/admin | Lectura/reparacion mediante permisos existentes; no acceso administrativo para alumnos |
| Consumidor de acciones | Misma autorizacion de clase; no puede declarar una fuente arbitraria ni publicar sin aprobacion |

1. Un space operativo nuevo no puede pertenecer a dos planes. Un conference_record no puede pertenecer a dos clases. El space original de historia importada es procedencia, no mapping operativo; puede haber sido compartido por varios planes.
2. Una clase puede tener varias conferencias; una conferencia puede tener varios artefactos.
3. Tener URL no significa ready: cohost y auto-transcripcion deben estar confirmados.
4. Cohost por correo no prueba identidad del hablante. Solo provider_id Google vinculado/verificado permite resolver identidad PLG.
5. Ningun reintento puede cambiar una asociacion visible o usada por un borrador sin flujo auditado; conflictos van a cuarentena.
6. Cierre academico no espera transcripcion ni se revierte por fallo de Google.
7. Ningun contenido parcial se declara completo. Fuente previa usada por borrador es reconstruible.
8. Lectura normal usa BD local, no Google; toda cache se consulta despues de autorizar.

## Data contract

Migraciones aditivas nuevas; no editar migraciones historicas. Restricciones sobre datos
legados quedan candidate-gated bajo `database/migrations/candidates/meet-transcripts/`.
No activar FKs/NOT NULL en legado sin readiness real del ambiente.

| Entidad nueva o extension | Contrato minimo |
| --- | --- |
| google_workspace_plan_meets | contrated_plan_id, generation, google_space_name unico nullable mientras se crea, meet_url, organizer_subject, provisioning_state, creation_attempt_id, next_attempt_at, last_error_code, retired_at; unico (plan,generation) |
| ContratedPlan | active_meet_mapping_id nullable mientras se aprovisiona; ready exige mapping nuevo, sin selector legacy/plan |
| ImpartedClass | meet_mapping_id nullable e inmutable al iniciar; no rebinding de historico al space actual |
| Cohost confirmado | mapping_id, professor_id, normalized_email, Google member.name, assignment interval, status, verified_at; registro propio GoogleMeet* |
| ConferenceSession | mapping_id nullable solo para historia importada, origin_type native/imported, original google_space_name y conference_record_name inmutables, class_id validado, timestamps remotos, inventory_checked_at, next_attempt_at, deadline_at, attempts, discovery_complete_at |
| Transcript | identidad remota unica, provider_state, active_version_id; no confundir identidad con version |
| Transcript version | transcript_id, source_hash, entry_count, char_count, imported_at, estado staging/committed; unico (transcript_id,hash); entradas inmutables por version |
| Class transcript snapshot | class_id, ordered version IDs, aggregate hash, coverage, manifest sequence; inmutable |
| Projection version | Identidades/etiquetas por snapshot y revision; no altera source_hash |
| ProfessorActionDraft | snapshot_id y versiones exactas; draft anterior se enlaza solo si su fuente coincide de forma demostrable; si no, provenance_unverifiable |
| Cutover manifest | cutover_id, source watermark, cohort de planes/clases, IDs de origen/destino, conteos, hashes, disposicion por registro y etapas; unico por cutover_id y entidad origen |

Modelo fisico nuevo bajo Models/GoogleMeet* o Models/GoogleWorkspace* y logica en
Services/GoogleWorkspace. Las referencias a objetos nuevos son entregables, no APIs existentes.
Snapshot hash: SHA-256 de JSON canonico con class_id y lista ordenada de
conference_record_name, transcript_name, source_hash; orden por inicio remoto UTC,
nombre de conferencia, inicio de transcript, nombre de transcript. Entradas usan orden
total por ordinal de artefacto, inicio UTC (null al final), sequence, entry_name.

## Algorithms

### A. Provision and repair

1. Al crear plan con profesor o al asignar/cambiar profesor, encolar afterCommit usando plan ID. Una tarea periodica recupera planes pendientes; nada depende exclusivamente del hook HTTP.
2. Reservar generation y creation_attempt_id con lock corto. No mantener transaccion de BD durante llamadas Google.
3. Persistir space.name tras creacion exitosa antes de configurar miembros/transcripcion. Si timeout deja resultado desconocido: creation_uncertain, sin recrear automaticamente; reparar con recurso confirmado por operador.
4. Confirmar TRUSTED/moderation ON y COHOST mediante lectura del proveedor. Persistir member.name; paginar lists y actualizar rol de miembro existente. No repetir POST si ya existe COHOST.
5. Confirmar autoTranscriptionGeneration=ON por lectura; fallo no activa el mapping. Mantener modo v2beta actual hasta prueba de compatibilidad del tenant; migrar version de members no es requisito de esta entrega.
6. Ready exige space verificado, docente vigente cohost confirmado, transcripcion confirmada y organizador/subscripcion saludable. Activar mapping solo despues.
7. Reparar etapa fallida sobre mismo space. Ante 429/5xx: 1, 5, 15, 60 minutos, maximo 5 intentos totales; 403/credenciales -> repair_required sin bucle. Guardar codigos, no tokens ni cuerpos con PII.
8. Cambio de docente: no durante conferencia activa. Confirmar nuevo cohost, retirar miembro anterior si no tiene otra asignacion vigente en el plan, verificar retiro, luego ready. Sustituciones se obtienen de asignaciones existentes, no se inventan por horario. Si falta forma inequívoca de obtener intervalo, bloquear ese plan para reparacion.
9. No exponer URL global como fallback; responder meet_ready=false y razon operacional si falta mapping nuevo, incluso para plan existente. Profile sin contexto de plan no ofrece enlace de clase. Retirar creacion automatica de enlaces por profesor para clases regulares; no borrar datos viejos ni reutilizar sus spaces.

### B. Bind and boundary

1. Resolver space exclusivamente en mappings del contrato nuevo, incluyendo sus generaciones retired. Eventos de conferencias historicas importadas pueden resolver por conference_record_name exacto ya registrado; usan la misma ingestion versionada, nunca heuristica por profesor ni busqueda de mapping antiguo. Evento de space anterior sin conferencia importada -> historical_event_quarantined, alerta y recibo durable; no descartar texto conocido ni asociar automaticamente. Otro unknown space -> unbound para diagnostico.
2. Upsert completo de startTime/endTime desde conferencia; ended antes de started no se descarta. No retroceder estados finales por duplicados.
3. Derivar plan desde mapping; luego filtrar candidatos con profesor/asignacion autorizada, marcador LMS y ventana existente de 15 minutos. Sin mapping por plan no ejecutar heuristica sobre clases del profesor.
4. Un candidato -> bind con lock y revalidacion de conflicto. Cero -> unbound; varios -> ambiguous. No elegir por proximidad cuando hay conflicto.
5. No ejecutar endActiveConference automaticamente al cerrar/reintentar clase: la API no ofrece precondicion atomica por conference_record. Mostrar boundary_pending mientras la conferencia anterior siga activa; docente termina reunion desde Meet. Bloquear inicio LMS siguiente hasta fin observado/reconciliado.
6. El URL directo de Google puede permitir continuidad fuera del LMS: si la conferencia cruza dos ventanas, cuarentena y sin transcript consumible para una clase elegida por conjetura. No prometer aislamiento por clase con space compartido.
7. Cancelar/no-op auditado para jobs antiguos que intenten cierre remoto automatico. Este es un limite de seguridad de efectos pendientes, no soporte del contrato anterior. Academic close permanece exitoso.

### C. Discover and ingest

1. Recibo de evento y artefacto anunciado son durables incluso sin binding; enqueue afterCommit. Deduplicar cloud_event_id y transcript_name por separado.
2. Reconciliar con next_attempt_at y limite 50 por tick, reservando 25 cupos para unbound y 25 para bound; capacidad libre puede prestarse. Orden next_attempt_at,id; no seleccionar items agotados.
3. Checkpoints desde fin: 1,3,5,10,15,30,60,120,360 minutos, despues cada 24h hasta dia 29. Una proxima tarea por item, jitter maximo 10%; manual repair no borra historial. Al dia 29: expired_recovery y alerta, sin polling indefinido.
4. Listar todos los artefactos aunque alguno ya sea available. Conservar provider state. Procesar FILE_GENERATED; STARTED/ENDED esperan. EMPTY solo si FILE_GENERATED y lectura completa confirmada sin texto, nunca a partir de estado desconocido.
5. Cobertura complete operacional exige conferencia terminada, dos inventarios exitosos iguales separados por al menos 10 minutos, todos los artefactos listados comprometidos/empty y ningun unbound/ambiguous del mapping que solape ventana. No equivale a garantia de que Google nunca produzca otro artefacto; reconciliacion diaria puede crear snapshot posterior.
6. Cero artefactos despues de 6h -> not_generated observado, continuar recuperacion diaria hasta deadline. Error de proveedor nunca se convierte en not_generated.
7. Exclusion por transcript durante ejecucion, staging por version, paginas hasta token final, detector de token repetido y upsert en lotes <=500. Transaccion atomica de version activa + snapshot + auditoria; fallo deja version anterior intacta.
8. Duplicado de evento procesado no descarga fuente otra vez. Revalidacion deliberada puede leer fuente; registrar motivo. Reusar participantes por conferencia y permitir refresh de proyeccion sin reingestion del texto.
9. Cambio de fuente: clase abierta sin drafts puede activar nueva version; cerrada o usada necesita aprobacion sobre version candidata exacta. Guardar ambas; mostrar diff paginado autorizado. Estado applied solo tras commit exitoso. Rechazo no se sobrescribe por duplicado.

### D. Read and consume

1. Conservar rutas y envelopes existentes: HubClassesController::transcript, ProfessorAppClassTranscriptController::show, lectura HR y ProfessorActionsReadController (incluido view=transcript).
2. metadata.status usa available/processing/not_generated/unavailable. coverage partial/complete/empty/unknown es obligatorio; snapshot_id y revision solo en vista identificada; al alumno solo coverage y contadores seguros. available significa hay texto, no complete. Frontends y acciones se actualizan coordinadamente; no se exige soporte de clientes previos.
3. limit 1..100, default 100. Keyset SQL sobre orden persistido y snapshot; prohibido get de todas las entradas antes de slice. Cursor HMAC ligado a clase, actor, visibilidad, snapshot, projection revision y ultima posicion.
4. Cursor de version obsoleta -> 422 invalid_cursor, sin mezclar versiones. Frontend reinicia una vez desde primera pagina; despues ofrece reintento explicito.
5. Cache privada en servidor por snapshot+proyeccion+modo+actor+limit+cursor, TTL 5 minutos, autorizacion antes de acceder. No cache compartida HTTP de contenido sensible. Invalidar al cambiar permisos/proyeccion/version; no usar cache como autorizacion.
6. Acciones aceptan format=compact opcional en lectura transcript: omitir metadatos repetidos de entradas, conservar speaker, text, entry_ref estable y tiempos. max_chars 1000..12000, default 8000 para compact; no cortar una entrada silenciosamente, usar continuacion firmada si una entrada excede presupuesto. Default mantiene formato previo.
7. Toda pagina identificada incluye coverage, returned_chars, next_cursor y truncated. No atribuir lectura completa por el mero envio de provenance. Texto del alumno conserva seudonimizacion de etiquetas, no promete anonimizar contenido hablado.
8. Draft create exige snapshot_id para fuente transcript y resuelve IDs/hash del lado servidor; comprueba clase autorizada, conjunto exacto de versiones y pertenencia de todas las conferencias. Falta de snapshot o IDs/hash contradictorios -> 422 invalid_transcript_provenance. No adaptar payload antiguo automaticamente.
9. Publicacion requiere snapshot fijado aun actual y coverage complete; fuente parcial puede generar borrador marcado incomplete_source pero no publicarse como basado en transcript. Version nueva -> 409 transcript_source_changed, requiere regenerar/revisar y nueva aprobacion. Comentario manual sin provenance mantiene contrato actual.
10. Draft anterior se convierte una vez durante cutover si puede probarse su fuente exacta. Si no, 409 transcript_provenance_unverifiable; no reconstruccion en tiempo de lectura. Usuario crea nuevo borrador manual o basado en snapshot validado. Publicaciones historicas conservan texto, estado y evidencia original aun cuando su fuente ya no sea reconstruible; se marcan unverifiable, no se despublican ni se reetiquetan como verificadas.

### E. Frontend

Paneles de profesor/HR y Hub muestran parcialidad y boundary_pending. Obtener enlace desde
DTO de clase/plan, nunca professor.user.links. No cambiar calendarios o correos
fuera de estas superficies sin actualizar targets primero.
Lectura bajo demanda; cancelar/ignorar respuestas de classId/usuario anterior y limpiar
estado al cambiar contexto. Maximo 2 reintentos automaticos (1s,3s) solo red/429/5xx;
403/404 no reintentan. Error persistente corta el efecto. Paginas quedan en cache de cliente
solo por clase+usuario+version, borrada al logout. No agregar nueva libreria de estado.

## Operational commands and rollout

Entregables nuevos bajo Console/Commands/*Meet*.php, no afirmar que existen hoy:

- `google-workspace:plan-meet-readiness --manifest=PATH --json`: solo lectura; exit 0 si cumple todos los gates de cutover descritos abajo; no crea recursos Google.
- `google-workspace:provision-plan-meet --plan-id=ID`: dry-run por defecto; `--apply` reserva/provisiona solo ese plan bajo contrato nuevo, sea plan nuevo o existente. No importa enlace ni bindings anteriores. Activacion solo ready y sin clase en curso; idempotente sobre mapping nuevo existente.
- `google-workspace:check-plan-meet-canary --manifest=PATH --json`: solo lectura sobre manifiesto de cohorte y recursos confirmados; no cambia roles/enlaces. Exit no cero ante evidencia faltante o mapeo inconsistente.
- `google-workspace:prepare-meet-cutover --manifest=PATH --json`: dry-run por defecto; inventaria datos y genera manifiesto versionado. `--apply` materializa modelo nuevo sin activar lectores ni enlaces. `--resume` exige mismo cutover_id y verifica cada etapa; no duplica spaces/versions.
- `google-workspace:activate-meet-cutover --manifest=PATH --json`: verifica watermark y readiness otra vez y activa la release coordinada mediante marcador durable de cutover. No inicia despliegues ni cambia infraestructura; falla si los binarios/clientes requeridos no estan instalados. Un unico marcador de readiness es gate de ingreso, no selector de implementaciones.

Flag `GOOGLE_MEET_PLAN_LINKS_ENABLED=false` por defecto pausa creacion/activacion nueva,
no selecciona arquitectura anterior. Mappings nuevos ya ready se mantienen resolubles.
Rollback pausa aprovisionamiento e ingreso de planes afectados; no vuelve al enlace del
profesor ni requiere implementar dual-read. La lectura posterior, incluida la historia
convertida, usa exclusivamente el modelo nuevo.

Secuencia: ensayo de migracion en copia aislada -> canary institucional con profesor
personal y 2 planes/4 clases -> 48h observacion -> preaprovisionamiento de todos los planes
con clases pendientes -> ventana de mantenimiento -> delta final y validacion -> corte
coordinado -> reapertura. No dejar planes usados operando con mecanismo anterior.

### One-time cutover algorithm

1. Construir manifiesto con todos los planes/clases regulares, sesiones, transcripts,
   entradas, revisiones y drafts existentes. Cohorte operacional: planes con alguna clase
   no cerrada, aunque el plan este expirado. Plan solo historico no necesita crear space
   nuevo hasta programar otra clase. IDs ausentes o asociaciones contradictorias se listan,
   no se omiten silenciosamente.
2. Preparar un space nuevo por plan operacional y confirmar titular/sustitutos vigentes y
   transcripcion. Esto puede ocurrir antes del mantenimiento, sin exponer enlaces nuevos.
3. Pausar nuevas aperturas, cambios de planes/clases, publicaciones y workers que escriban
   estas entidades; esperar conferencias en curso terminadas en Google y en LMS. Mantener
   ingreso durable de eventos en cola, sin perderlos por apagar el webhook. Tomar backup
   verificable y watermark de datos/recibos; ejecutar delta final bajo pausa.
4. Clases pendientes sin sesion activa reciben meet_mapping_id del space nuevo de su plan.
   Conservar IDs, horarios, duracion, profesor, alumnos y datos academicos. Una clase en
   curso bloquea el corte: no mover participantes ni transcripcion entre spaces.
5. Clases cerradas conservan sus conference_record_names, artefactos y espacio original
   como origin_type=imported. No insertar un mapping operativo compartido para ese space.
   Su binding historico se valida por las relaciones persistidas; ambiguos se preservan
   en cuarentena y no se corrigen por proximidad de horario.
6. Copiar texto local a versiones inmutables y comprobar conteos, orden y hash recalculado.
   Conservar hash anterior y registrar version del algoritmo cuando cambie la serializacion.
   Crear snapshots legibles con coverage unknown/partial salvo completitud demostrada.
   No consultar Google para recrear texto ya persistido ni inventar versiones perdidas.
7. Relacionar drafts/revisiones con snapshot solo cuando las versiones exactas y clase
   concuerden con la evidencia previa; mantener hashes/IDs originales en auditoria.
   Fuente perdida -> unverifiable con razon. Cero perdida de texto publicado.
8. Consumir/reconciliar backlog conocido mediante conversion a los mismos records del
   modelo nuevo. Conferencias ya importadas admiten artefactos tardios por su ID exacto
   con el pipeline comun y deadline normal; no se mantiene un consumidor antiguo.
   Desconocidas quedan en cuarentena con alerta y recuperacion manual auditada, nunca
   como eventos descartados exitosamente. No asumir que cola vacia significa que Google
   ya genero todos los artefactos.
9. Readiness exige 100% de clases pendientes con mapping ready, cero sesiones activas,
   cero perdidas de filas/texto/hash, cero bindings contradictorios expuestos y 100% de
   registros de origen con disposicion accounted (migrated/empty/quarantined/unverifiable).
   Cualquier quarantined/unverifiable exige detalle y aceptacion del responsable en el
   manifiesto; sin aceptacion bloquea, nunca se declara migracion plenamente verificada.
10. Activar un solo contrato de backend/frontend y retirar resolucion/creacion global del
    flujo regular. Invalidar caches y verificar que todas las pantallas de clase usan
    mapping nuevo. Comunicar fuera de la app los enlaces nuevos segun operacion; no
    prometer que bookmarks/calendarios externos viejos redirigen automaticamente.
11. Reabrir solo tras smoke de login, ingreso por plan, transcript historico convertido y
    borrador con provenance. Reejecutar preparacion no duplica ni cambia IDs; verificar
    segunda corrida con cero cambios. Retirar tooling de escritura de la operacion normal;
    conservar manifiesto, verificadores y datos de origen para auditoria.

Abortar antes de reapertura permite restaurar backup/release anterior con cola durable
preservada y reconciliacion de delta; no borrar espacios remotos creados para compensar
rollback. Despues de admitir escrituras nuevas no restaurar backup a ciegas: pausar,
preservar/reconciliar delta y reparar hacia adelante. No hay fallback automatico al URL
del profesor ni dos arquitecturas sirviendo trafico.

## Acceptance criteria

1. Dos planes del mismo profesor reciben spaces diferentes; cuatro clases en dos planes reutilizan solo su space de plan.
2. Cohost con cuenta personal se confirma por API y reparacion no recrea espacio. Cambio docente revoca rol anterior cuando corresponde.
3. Evento atrasado de generation retired o conferencia importada conocida conserva plan/clase por ID exacto; historico desconocido se conserva en cuarentena; eventos invertidos no pierden endTime.
4. Ningun cierre/reintento automatico termina otra conferencia; continuidad ambigua queda en cuarentena.
5. Segundo artefacto sin evento se recupera; vacio transitorio no se declara completo; 50 unbound no bloquean bound.
6. Ingestion concurrente produce una version atomica y auditoria verdadera; fuente previa usada por draft sigue consultable.
7. Provenance de otra clase/hash inventado se rechaza; cambio posterior bloquea publicacion hasta nueva aprobacion.
8. Con fixtures 2000 y 20000 entradas, una pagina 100 hidrata <=101 entradas (+1 lookahead), <=12 consultas SQL, sin ordenar corpus en PHP. Compact respeta max_chars y no pierde texto entre continuaciones.
9. Lectura repetida no llama a Google; carga frontend con 403 termina tras una solicitud y 500 tras tres como maximo.
10. Permisos de Hub/profesor/HR no se amplian; cache nunca mezcla actores, clases ni modos.
11. Suite existente y regresiones pasan; prueba real canary documenta email personal sin exponerlo en reportes publicos.
12. Ensayo convierte clases existentes sin recrearlas; conserva 100% del texto y datos academicos, sirve historia desde snapshots y segunda corrida no duplica registros.
13. Corte no reabre con una sola clase pendiente sin mapping ready ni una sesion activa. Fallo parcial se reanuda desde manifiesto; fuente incomprobable no se presenta como validada.

## Slice Breakdown

```yaml
- name: meet-plan-provisioning
  repo: plg-platform-backend
  targets:
    - ../../plg-platform-backend/src/app/Services/GoogleWorkspace/**
    - ../../plg-platform-backend/src/app/Models/GoogleWorkspace*.php
    - ../../plg-platform-backend/src/app/Models/ContratedPlan.php
    - ../../plg-platform-backend/src/database/migrations/**
  hot_area: plan mapping and verified cohost lifecycle
  depends_on: []
  slice_mode: implementation-heavy
  surface_policy: required
  minimum_valid_completion: plan provisioning and repair with additive schema and no professor-link fallback for any plan
  validated_noop_allowed: false
  acceptable_evidence: [provisioning tests, schema readiness fixtures, no remote effects in tests]
- name: meet-capture-and-snapshots
  repo: plg-platform-backend
  targets:
    - ../../plg-platform-backend/src/app/Services/GoogleWorkspace/**
    - ../../plg-platform-backend/src/app/Jobs/*Meet*.php
    - ../../plg-platform-backend/src/app/Models/GoogleMeet*.php
    - ../../plg-platform-backend/src/database/migrations/**
  hot_area: association recovery and immutable source
  depends_on: [meet-plan-provisioning]
  slice_mode: implementation-heavy
  surface_policy: required
  minimum_valid_completion: monotone events fair recovery atomic versions and no automatic shared-space termination
  validated_noop_allowed: false
  acceptable_evidence: [out-of-order tests, two-artifact recovery, concurrent ingestion, snapshot audit tests]
- name: meet-consumption-contract
  repo: plg-platform-backend
  targets:
    - ../../plg-platform-backend/src/app/Services/GoogleWorkspace/**
    - ../../plg-platform-backend/src/app/Services/Actions/**
    - ../../plg-platform-backend/src/app/Http/Controllers/Actions/Professor/**
    - ../../plg-platform-backend/src/docs/openapi/**
  hot_area: bounded pagination and validated provenance
  depends_on: [meet-capture-and-snapshots]
  slice_mode: implementation-heavy
  surface_policy: required
  minimum_valid_completion: SQL pagination compact context and source-bound draft publication
  validated_noop_allowed: false
  acceptable_evidence: [query budget tests, authorization and provenance tests, OpenAPI parity]
- name: meet-dashboard-consumption
  repo: dashboard-frontend
  targets:
    - ../../dashboard-frontend/src/src/pages/ProfessorsDashboard/ClassScreen/**
    - ../../dashboard-frontend/src/src/pages/Plans/ClassScreen/**
    - ../../dashboard-frontend/src/src/services/transcriptService.js
  hot_area: class links and bounded transcript retries
  depends_on: [meet-consumption-contract]
  slice_mode: implementation-heavy
  surface_policy: required
  minimum_valid_completion: plan DTO links partial state finite retries and context reset
  validated_noop_allowed: false
  acceptable_evidence: [CRA focused tests, desktop mobile journey]
- name: meet-existing-data-cutover
  repo: plg-platform-backend
  targets:
    - ../../plg-platform-backend/src/app/Services/GoogleWorkspace/**
    - ../../plg-platform-backend/src/app/Console/Commands/*Meet*.php
    - ../../plg-platform-backend/src/app/Models/GoogleMeet*.php
    - ../../plg-platform-backend/src/app/Models/GoogleWorkspace*.php
    - ../../plg-platform-backend/src/app/Models/ImpartedClass.php
    - ../../plg-platform-backend/src/app/Models/ProfessorActionDraft.php
    - ../../plg-platform-backend/src/tests/Feature/**
  hot_area: one-time conversion and cutover readiness
  depends_on: [meet-consumption-contract]
  slice_mode: implementation-heavy
  surface_policy: required
  minimum_valid_completion: resumable manifest conversion preserves existing classes and history with binary readiness and no legacy reader
  validated_noop_allowed: false
  acceptable_evidence: [isolated migration rehearsal, zero-loss counts and hashes, idempotent second run, interrupted resume, rollback rehearsal]
- name: meet-hub-consumption
  repo: hub-frontend
  targets:
    - ../../hub-frontend/src/features/class-management/**
    - ../../hub-frontend/src/features/student-class-process/**
    - ../../hub-frontend/src/shared/api/hub.ts
    - ../../hub-frontend/src/shared/i18n/**
  hot_area: student professor transcript views
  depends_on: [meet-consumption-contract]
  slice_mode: implementation-heavy
  surface_policy: required
  minimum_valid_completion: authorized plan links version-aware pages and visible coverage
  validated_noop_allowed: false
  acceptable_evidence: [Vitest focused tests, typecheck, mobile desktop journey]
- name: meet-integration-evidence
  repo: plg-platform-harness
  targets:
    - ../../specs/features/plg/2026-09-11-plan-scoped-meet-transcript-lifecycle.spec.md
  hot_area: gate evidence and rollout readiness
  depends_on: [meet-dashboard-consumption, meet-hub-consumption, meet-existing-data-cutover]
  slice_mode: verification-only
  surface_policy: forbidden
  minimum_valid_completion: CI and real canary evidence linked with rollback and residual risks
  validated_noop_allowed: false
  acceptable_evidence: [spec CI, all affected repo CI, canary report, independent review]
```

Slice targets son anchors iniciales; al planificar, distribuir TODOS los targets del
frontmatter implicados en cada algoritmo (hooks, DTO, jobs, commands, config, routes,
tests, OpenAPI publicado) en ownership explicito. No permitir trabajo sin owner.
Las cuatro slices backend son secuenciales por archivos compartidos; no se permite
ownership concurrente sobre Services/GoogleWorkspace o migraciones.

## Verification Matrix

```yaml
- name: spec-review
  level: custom
  command: python3 ./flow workspace exec -- python3 ./flow spec review specs/features/plg/2026-09-11-plan-scoped-meet-transcript-lifecycle.spec.md --json
  blocking_on: [approval]
  environments: [local]
- name: spec-ci
  level: custom
  command: python3 ./flow workspace exec -- python3 ./flow ci spec specs/features/plg/2026-09-11-plan-scoped-meet-transcript-lifecycle.spec.md --json
  blocking_on: [ci]
  environments: [local]
- name: backend-ci
  level: integration
  command: python3 ./flow workspace exec -- python3 ./flow ci repo plg-platform-backend --skip-install --json
  blocking_on: [ci, release]
  environments: [local]
- name: dashboard-ci
  level: integration
  command: python3 ./flow workspace exec -- python3 ./flow ci repo dashboard-frontend --skip-install --json
  blocking_on: [ci, release]
  environments: [local]
- name: hub-ci
  level: integration
  command: python3 ./flow workspace exec -- python3 ./flow ci repo hub-frontend --skip-install --json
  blocking_on: [ci, release]
  environments: [local]
```

## Test Plan

- [@test] ../../plg-platform-backend/src/tests/Unit/GoogleMeetPersistentSpaceCreatorTest.php
- [@test] ../../plg-platform-backend/src/tests/Feature/GoogleMeetClassSessionBoundaryTest.php
- [@test] ../../plg-platform-backend/src/tests/Feature/GoogleMeetClassTranscriptIngestionTest.php
- [@test] ../../plg-platform-backend/src/tests/Feature/GoogleMeetTranscriptPresentationContractTest.php
- [@test] ../../plg-platform-backend/src/tests/Feature/ProfessorActionsClassTranscriptTest.php
- [@test] ../../dashboard-frontend/src/src/pages/Plans/ClassScreen/TranscriptPanel.test.jsx
- [@test] ../../dashboard-frontend/src/src/pages/ProfessorsDashboard/ClassScreen/TranscriptPanel.test.jsx
- [@test] ../../hub-frontend/src/features/class-management/components/ClassTranscriptPanel.test.tsx
- [@test] ../../hub-frontend/src/features/student-class-process/components/ClassTranscriptSection.test.tsx

Extender regresiones CRA en ambos TranscriptPanel.test.jsx; extender suites GoogleMeet
para cubrir A-D, permisos, agotamiento, concurrencia, profesor personal y cambio de
docente. Tests remotos son canary separado, no requisito de credenciales para unit tests.

## Evidence package and stop conditions

G0-G2: intake reflejado aqui, inventario revisado, review/CI de spec y aprobacion explicita
antes de implementar. Esta creacion de spec no autoaprueba producto ni plan.
G3: revision independiente de mapping, locks, fuente/caches y diff de APIs.
G4: CI por repo, query counts para 2k/20k, escenarios negativos y capturas desktop/mobile.
G5: SHAs exactos, migrations aditivas y rollback documentados; nada de secretos en evidencia.
G6: canary real, readiness del ambiente y metricas de cohorte; no cerrar por tests simulados.

Evidencia persistente en `.flow/reports/plg/2026-09-11-plan-scoped-meet-transcript-lifecycle/`:
`review.md`, `verification.json`, `query-budget.json`, `canary.json`, `rollout.md`,
`cutover-manifest.json`, `migration-rehearsal.json`, `cutover-readiness.json`.
Cada reporte registra SHA, comando, ambiente, fecha, resultado y limitaciones; canary
incluye IDs opacos de dos planes/cuatro clases y recursos Google, roles confirmados,
artefactos recuperados, snapshots y cero asociaciones cruzadas. Restringir acceso al
detalle operacional; no guardar texto de alumnos ni emails personales en reportes.

Bloquear rollout si falla API members, auto-transcripcion, permisos, igualdad de hashes,
coverage, historial, migracion sin perdida o presupuesto SQL. No reabrir con clases
pendientes sin mapping ready, sesiones activas, delta no reconciliado o excepciones sin
disposicion aceptada en manifiesto. Si Google no permite verificar un resultado,
repair_required; no inventar ready. Si hace falta una superficie fuera de targets,
actualizar esta spec antes de editar. No activar constraints legados sin readiness.
Deuda permitida al cierre: resumen generativo/embeddings y space por clase, expresamente
diferidos. No son deuda permitida los cruces de planes, fuentes no reconstruibles nuevas,
retries infinitos o procedencia no validada.

## Provider references

- https://developers.google.com/workspace/meet/api/guides/meeting-space-members
- https://developers.google.com/workspace/meet/api/reference/rest/v2/spaces/endActiveConference
- https://developers.google.com/workspace/meet/api/reference/rest/v2/conferenceRecords.transcripts
- https://developers.google.com/workspace/meet/api/guides/artifacts

Consultar contrato vigente al implementar; disponibilidad del tenant se demuestra en
canary. El deadline de recuperacion de 29 dias deja margen frente a retencion REST
documentada de entradas de 30 dias tras fin de conferencia.
