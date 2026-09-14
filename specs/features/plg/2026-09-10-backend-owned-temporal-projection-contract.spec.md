---
schema_version: 3
name: "Backend Owned Temporal Projection Contract"
description: "Make the backend the single owner of timezone projection for classes, diagnostic classes, events, calendars, invoices and user-facing schedule DTOs across authenticated and public platform surfaces."
status: approved
owner: platform
single_slice_reason: ""
multi_domain: true
phases: []
depends_on:
  - specs/000-foundation/spec-as-source-operating-model.spec.md
  - specs/000-foundation/spec-driven-delivery-and-infrastructure.spec.md
  - specs/000-foundation/repo-routing-and-worktree-orchestration.spec.md
  - specs/000-foundation/plg-platform-backend-foundation-alignment.spec.md
  - specs/000-foundation/plg-platform-backend-coding-style-and-quality-contract.spec.md
  - specs/000-foundation/dashboard-frontend-foundation-alignment.spec.md
  - specs/000-foundation/dashboard-frontend-coding-style-and-quality-contract.spec.md
  - specs/000-foundation/hub-frontend-foundation-alignment.spec.md
  - specs/000-foundation/hub-frontend-coding-style-and-quality-contract.spec.md
required_runtimes:
  - php-laravel8-apache
  - node-npm-react-cra
  - node
required_services: []
required_capabilities:
  - laravel8
  - react-cra
stack_projects: []
stack_services: []
stack_capabilities: []
targets:
  - ../../specs/features/plg/2026-09-10-backend-owned-temporal-projection-contract.spec.md
  - ../../plg-platform-backend/AGENTS.md
  - ../../plg-platform-backend/src/app/Helpers/TimezoneHelper.php
  - ../../plg-platform-backend/src/app/Http/Controllers/DiagnosticClassController.php
  - ../../plg-platform-backend/src/app/Http/Controllers/ImpartedClassController.php
  - ../../plg-platform-backend/src/app/Http/Controllers/EventController.php
  - ../../plg-platform-backend/src/app/Http/Controllers/ProfessorInvoiceController.php
  - ../../plg-platform-backend/src/app/Models/Event.php
  - ../../plg-platform-backend/src/app/Http/Controllers/Api/V2/Hub/**
  - ../../plg-platform-backend/src/app/Http/Controllers/Actions/Professor/**
  - ../../plg-platform-backend/src/app/Models/DiagnosticClass.php
  - ../../plg-platform-backend/src/app/Models/ImpartedClass.php
  - ../../plg-platform-backend/src/app/Models/User.php
  - ../../plg-platform-backend/src/app/Services/Actions/**
  - ../../plg-platform-backend/src/app/Services/Hub/**
  - ../../plg-platform-backend/src/app/Services/Scheduling/**
  - ../../plg-platform-backend/src/app/Support/DiagnosticClassSchedulePresenter.php
  - ../../plg-platform-backend/src/app/Support/ImpartedClassSchedulePresenter.php
  - ../../plg-platform-backend/src/config/actions.php
  - ../../plg-platform-backend/src/config/app.php
  - ../../plg-platform-backend/src/database/migrations/2024_05_03_081918_create_diagnostic_classes_table.php
  - ../../plg-platform-backend/src/database/migrations/2025_11_20_000003_add_candidate_timezone_to_diagnostic_classes_table.php
  - ../../plg-platform-backend/src/database/seeders/ConfigurationTypeSeeder.php
  - ../../plg-platform-backend/src/docs/openapi/**
  - ../../plg-platform-backend/src/resources/views/email/**
  - ../../plg-platform-backend/src/routes/api.php
  - ../../plg-platform-backend/src/tests/Feature/**
  - ../../plg-platform-backend/src/tests/Unit/**
  - ../../dashboard-frontend/src/src/utils/dateUtils.js
  - ../../dashboard-frontend/src/src/utils/dateUtils.test.js
  - ../../dashboard-frontend/src/src/utils/timezoneUtils.js
  - ../../dashboard-frontend/src/src/pages/DiagnosticClass/**
  - ../../dashboard-frontend/src/src/pages/ProfessorsDashboard/DiagnosticClass/**
  - ../../dashboard-frontend/src/src/pages/ProfessorsDashboard/Invoice/**
  - ../../dashboard-frontend/src/src/pages/StudentDashboard/**
  - ../../dashboard-frontend/src/src/components/CreateDiagnosticClassModal.jsx
  - ../../dashboard-frontend/src/src/services/userConfigurationService.js
  - ../../dashboard-frontend/src/src/store/DiagnosticClassSlice.js
  - ../../dashboard-frontend/src/src/routes.js
  - ../../hub-frontend/src/features/diagnostic-class-access/**
  - ../../hub-frontend/src/features/professor-dashboard/**
  - ../../hub-frontend/src/features/student-dashboard/**
  - ../../hub-frontend/src/shared/api/timezone.ts
  - ../../hub-frontend/src/shared/api/timezone.test.tsx
  - ../../hub-frontend/src/shared/lib/format.ts
  - ../../hub-frontend/src/test/mocks/handlers.ts
---

# Backend Owned Temporal Projection Contract

## Objective

Make `plg-platform-backend` the single owner of timezone business transformation for every user-facing schedule surface. Frontends must render backend-projected temporal fields and may only perform cosmetic formatting, not business timezone conversion.

The first defect to close is diagnostic classes showing the same wall-clock hour for Bogota and Mexico, but the contract applies to all platform schedule DTOs: diagnostic classes, regular classes, events, calendar cards, invoices, access windows, emails, actions APIs, Hub V2 and the legacy dashboard.

## Governing Decision

The canonical architecture is backend-owned temporal projection.

| Concern | Owner | Required behavior |
| --- | --- | --- |
| Persisted instant | Backend/database | Store one canonical instant in UTC or derive an equivalent UTC instant from existing date/time columns. |
| Business/source timezone | Backend | Preserve the timezone in which the schedule was created or belongs operationally. |
| Viewer timezone | Backend | Resolve from authenticated user configuration, public request context, or explicit system recipient. |
| User-facing date/time | Backend | Project UTC instant into viewer timezone before returning an API DTO or rendering an email. |
| Frontend display | Frontends | Render `viewer_*` fields; do not convert UTC to local time for business display. |
| Browser timezone | Frontends | May be sent as input/context for public anonymous flows only; it is never authoritative after backend response. |

Prohibited alternatives:

- Do not fix this by adding more ad hoc frontend conversions.
- Do not rely on browser timezone for authenticated users when backend can identify the viewer.
- Do not keep ambiguous `*_display` fields as the only display contract.
- Do not silently fallback to `America/Bogota` when a valid actor/request timezone is available.
- Do not introduce a schema migration unless a slice proves existing columns cannot support the contract.

## Current Observed Inventory

### Backend

| File | Observed behavior | Disposition |
| --- | --- | --- |
| `DiagnosticClassController::store` | Interprets `starting_date`/`starting_time` as candidate-local and stores UTC in existing columns. | Preserve intent, move into canonical projector/normalizer contract. |
| `DiagnosticClassController::update` | Reinterprets schedule fields as candidate-local and stores UTC; timezone-only update changes presentation without changing instant. | Preserve with explicit tests and clearer DTO separation. |
| `DiagnosticClassController::sendEmail` | Uses mutable `Carbon::setTimezone()` for candidate then professor, allowing both projections to collapse to the final timezone. | Must correct with `copy()` or immutable instants. |
| `DiagnosticClassSchedulePresenter` | Projects `starting_*_display` using the provided timezone, usually `candidate_timezone` in legacy list endpoints. | Replace or extend with actor-aware `viewer_*` and `source_*` contract. |
| `ProfessorActionsDiagnosticClassReadService` | Already returns `starting_date`/`starting_time` in professor timezone and UTC fields, but also merges ambiguous display fields. | Use as partial precedent; remove ambiguity. |
| Admin/professor legacy routes | Return diagnostic rows decorated by candidate timezone, while consumers may be professor/admin viewers. | Must become viewer-aware without breaking edit forms. |
| Candidate public access | Uses request timezone or candidate timezone and adds access-window fields. | Preserve public request override with validation and explicit source/viewer fields. |
| Email templates | Print `$class->starting_date` and `$class->starting_time` from cloned/modified model instances. | Use explicit projected DTO/data fields per recipient. |
| Actions filters | Some `from/to` filters use UTC dates while users think in local days. | Must define local-day filter semantics before changing behavior. |

### Dashboard Frontend

| File | Observed behavior | Disposition |
| --- | --- | --- |
| `utils/dateUtils.js` | Converts UTC to `userTimezone`, but `getDiagnosticClassDisplayDateTime` first trusts backend `starting_*_display`. | Keep only cosmetic helpers for fallback/tests; business conversion must not be primary path. |
| Admin diagnostic list | Displays `starting_*_display` when present, otherwise converts in frontend. | Render backend `viewer_*`; fallback only for transitional compatibility. |
| Professor diagnostic list | Same display pattern and uses converted/display values to decide start/close/edit button state. | Button gating must be driven by backend capability/temporal state fields or backend-projected viewer fields. |
| Diagnostic edit forms | Need candidate/source-local values for editing because backend interprets schedule edits in source timezone. | Use `source_*` fields, not `viewer_*`. |
| Public diagnostic access | May collect browser/user-selected timezone. | Send selected timezone; render backend response. |

### Hub Frontend

| File | Observed behavior | Disposition |
| --- | --- | --- |
| `diagnostic-class-access` | Sends selected timezone and then prefers backend display fields over recalculation. | Preserve request context; render backend `viewer_*`. |
| `student-dashboard` | Preserves `display_timezone` but many views use student/browser timezone or raw display fields inconsistently. | Render backend `viewer_*`; use student timezone only as request/config source. |
| `professor-dashboard` | Diagnostic API hook exists but current tab is not active. | Do not expand UI scope unless required; update types/contracts to prevent future drift. |
| Shared `format.ts` | Some helpers preserve wall-clock and ignore timezone argument. | Keep only for cosmetic local formatting where no business projection is needed. |

## Target Contract

Every backend schedule DTO touched by this spec must expose canonical, source, and viewer fields with stable names. Existing legacy aliases may remain during migration, but they cannot be the only correct fields.

```json
{
  "starts_at_utc": "2026-05-28T16:00:00Z",
  "viewer_timezone": "America/Bogota",
  "viewer_date": "2026-05-28",
  "viewer_time": "11:00",
  "viewer_datetime": "2026-05-28 11:00",
  "source_timezone": "America/Mexico_City",
  "source_date": "2026-05-28",
  "source_time": "10:00"
}
```

Required naming rules:

- `starts_at_utc` is an ISO-8601 UTC instant with `Z`.
- `viewer_timezone` is the IANA timezone used for `viewer_*`.
- `viewer_date` and `viewer_time` are what the requester/recipient must see.
- `source_timezone` is the business timezone of the scheduled object.
- `source_date` and `source_time` are for edit forms and audit context.
- Legacy `starting_date`, `starting_time`, `scheduled_class`, `class_time`, `*_display`, and `display_timezone` remain compatibility aliases only when a slice explicitly maps them.
- Any field named `*_display` must either be deprecated or documented as an alias of `viewer_*`, never silently candidate-local in a professor/admin response.

## Viewer Timezone Resolution Algorithm

Apply this algorithm for every API response or email recipient.

1. Identify response context:
   - authenticated user response;
   - public candidate/diagnostic access response;
   - outbound email/ICS recipient;
   - system/internal command or audit report.
2. Resolve viewer timezone:
   - authenticated user: `TimezoneHelper::getUserTimezone($user, fallback)` using that exact user;
   - professor recipient: professor user's timezone;
   - student recipient: student/account user's timezone;
   - admin/HR recipient: authenticated admin user's timezone;
   - public diagnostic candidate: valid request `timezone`, else diagnostic `candidate_timezone`, else explicit configured fallback;
   - system/internal report: explicit report timezone parameter, else configured system timezone, not browser data.
3. Validate timezone with IANA validation.
4. If timezone is invalid:
   - for user-saved configuration, use configured fallback and include a non-sensitive warning path in logs/tests;
   - for public request timezone, ignore request value and use source timezone when valid;
   - for source timezone, use `America/Bogota` only as legacy fallback and record the fallback in a non-user-facing diagnostic field or log.
5. Build canonical UTC instant from persisted columns.
6. Project canonical instant into viewer timezone.
7. Project canonical instant into source timezone.
8. Return or render explicit fields; never mutate one date object for multiple projections.

## Temporal Projection Algorithm By Object

| Object | Canonical instant source | Source timezone | Viewer timezone | Required output |
| --- | --- | --- | --- | --- |
| Diagnostic class | `starting_date` + `starting_time` interpreted as UTC | `candidate_timezone`, fallback `America/Bogota` | requester/recipient algorithm | `starts_at_utc`, `viewer_*`, `source_*`; compatibility aliases. |
| Regular/imparted class | `scheduled_class` + `class_time` or existing UTC presenter contract | plan/student/professor contract if present; else UTC | requester/recipient algorithm | same field family, using class-specific aliases only for compatibility. |
| Event/calendar item | event stored instant/date fields | event timezone if present; else UTC | requester timezone | viewer-local calendar DTO. |
| Professor invoice class rows | class canonical instant | class source timezone | professor user timezone | invoice rows in professor timezone plus UTC/source audit fields. |
| Student Hub diagnostic card | diagnostic canonical instant | candidate/student diagnostic timezone | student user timezone for authenticated views, public request timezone for public access | no frontend conversion needed. |
| Emails and ICS | canonical instant | object source timezone | recipient timezone | recipient-specific date/time and ICS start/end from independent immutable/copy projections. |

## Actor Matrix

| Actor/context | Example route/surface | Viewer timezone must be |
| --- | --- | --- |
| Professor authenticated legacy dashboard | `/professor-app/diagnostic-class/{professor}` | Authenticated professor user's saved timezone, not candidate timezone. |
| Professor actions/GPT API | `/api/v1/actions/professor/diagnostic-classes` | Token owner professor user's saved timezone. |
| Admin/HR dashboard | `/hr-management/diagnostic-class` | Authenticated admin/HR user's saved timezone. |
| Student authenticated Hub | `/v2/hub/me`, student dashboard cards/calendar | Student user's saved timezone. |
| Public candidate access | `/diagnostic-class-access` | Valid request timezone, else class source timezone. |
| Candidate email | scheduled/reminder/close email to candidate | Candidate/source timezone unless candidate is linked to a user with an explicit timezone. |
| Professor email | scheduled/reminder email to professor | Professor user's saved timezone. |
| System command/audit | reminders/audits/readiness commands | Explicit command/config timezone; no browser fallback. |

## Scope

### Includes

- Create or harden a backend temporal projection service/presenter that takes a canonical instant, source timezone and viewer context.
- Replace diagnostic-class ambiguous display behavior with actor-aware `viewer_*` and `source_*` fields.
- Fix diagnostic scheduled email timezone mutation by using independent `Carbon` copies or immutable instances.
- Apply the same backend-owned projection contract to regular class, event, invoice and Hub DTO surfaces touched by the tests.
- Preserve source-local edit behavior for diagnostic class forms.
- Update OpenAPI/docs for affected API response fields.
- Update frontends to render backend-projected fields and remove business timezone conversion from primary display paths.
- Add cross-timezone tests for `America/Mexico_City`, `America/Bogota`, `Europe/Madrid` and `UTC`.
- Keep legacy fields as compatibility aliases where existing consumers require them.

### Excludes

- No dependency upgrades, framework migrations, or date library replacement.
- No broad UI redesign.
- No destructive data migration.
- No production command, seeder, or destructive migration as validation.
- No change to who is allowed to create, update, close or attend classes.
- No automatic correction of historical rows unless a later spec defines data remediation.
- No removal of legacy aliases until all known consumers are migrated and a deprecation spec exists.

## Invariants

- The backend owns business timezone transformation.
- Frontends must not compute business timezone conversions for class/event/invoice display after the backend contract is present.
- UTC canonical instants must remain stable when only viewer timezone changes.
- Source-local edit forms must not accidentally submit viewer-local values as source-local values.
- Bogota/Mexico same-instant projections must differ when their UTC offsets differ.
- Multiple projections from one instant must use immutable values or object copies.
- Missing or invalid timezone values must follow the disposition matrix; no silent actor-agnostic fallback.
- Legacy compatibility aliases cannot contradict canonical `viewer_*` and `source_*` values.
- Date filters must declare whether they are UTC-day or viewer-local-day before implementation changes them.

## Disposition Matrix

| Condition | Required disposition | Blocks closure |
| --- | --- | --- |
| Authenticated user has valid timezone configuration | Use it as viewer timezone. | Yes, if ignored. |
| Authenticated user has missing timezone | Use configured fallback and expose deterministic test coverage. | No, if fallback is explicit. |
| Authenticated user has invalid timezone | Use configured fallback and log non-sensitive warning. | Yes, if it crashes or silently uses browser timezone. |
| Public request includes valid timezone | Use it as viewer timezone for that response/access check. | Yes, if ignored. |
| Public request timezone invalid but source timezone valid | Use source timezone. | No. |
| Source timezone invalid or missing | Use legacy fallback `America/Bogota`, log warning, keep UTC stable. | No for compatibility; yes if no warning/test exists. |
| Stored UTC date/time unparsable | Return null projected fields and fail focused test for affected flow, or surface deterministic domain error where mutation occurs. | Yes for write paths; conditional for read compatibility. |
| Frontend needs edit values | Use backend `source_*` fields. | Yes, if it uses `viewer_*` for source-local edit submission. |
| Frontend lacks new fields during transition | May use legacy fallback behind one helper with tests. | No if transitional and covered. |
| Legacy alias contradicts `viewer_*` | Treat as implementation defect. | Yes. |

## Slice Breakdown

```yaml
- name: backend-temporal-projection-core
  repo: plg-platform-backend
  targets:
    - ../../plg-platform-backend/src/app/Helpers/TimezoneHelper.php
    - ../../plg-platform-backend/src/app/Support/DiagnosticClassSchedulePresenter.php
    - ../../plg-platform-backend/src/app/Support/ImpartedClassSchedulePresenter.php
    - ../../plg-platform-backend/src/app/Services/Scheduling/**
    - ../../plg-platform-backend/src/app/Models/DiagnosticClass.php
    - ../../plg-platform-backend/src/app/Models/ImpartedClass.php
    - ../../plg-platform-backend/src/tests/Unit/**
  hot_area: canonical UTC/source/viewer temporal projection service
  depends_on: []
  slice_mode: implementation-heavy
  surface_policy: required
  minimum_valid_completion: one backend projection contract that independently produces UTC source and viewer fields for diagnostic and regular class examples
  validated_noop_allowed: false
  acceptable_evidence:
    - PHPUnit unit tests prove Mexico candidate 10:00 projects to Bogota viewer 11:00 for the same UTC instant
    - invalid/missing timezone disposition matrix is covered
    - no mutable Carbon projection reuse remains in the core service

- name: diagnostic-class-backend-contract
  repo: plg-platform-backend
  targets:
    - ../../plg-platform-backend/src/app/Http/Controllers/DiagnosticClassController.php
    - ../../plg-platform-backend/src/app/Http/Controllers/Actions/Professor/**
    - ../../plg-platform-backend/src/app/Services/Actions/**
    - ../../plg-platform-backend/src/app/Services/Hub/**
    - ../../plg-platform-backend/src/app/Support/DiagnosticClassSchedulePresenter.php
    - ../../plg-platform-backend/src/docs/openapi/**
    - ../../plg-platform-backend/src/resources/views/email/**
    - ../../plg-platform-backend/src/routes/api.php
    - ../../plg-platform-backend/src/tests/Feature/**
  hot_area: diagnostic class API email and action projections
  depends_on:
    - backend-temporal-projection-core
  slice_mode: implementation-heavy
  surface_policy: required
  minimum_valid_completion: diagnostic class APIs and scheduled emails return/render viewer-specific fields for professor admin student and public candidate contexts while preserving source-local editing
  validated_noop_allowed: false
  acceptable_evidence:
    - feature tests for professor legacy response use professor timezone
    - feature tests for admin response use authenticated admin timezone
    - feature tests for public candidate access use request timezone when valid and source timezone otherwise
    - email tests prove candidate and professor templates differ for Mexico/Bogota when expected
    - OpenAPI documents viewer/source/UTC fields

- name: backend-broader-schedule-surfaces
  repo: plg-platform-backend
  targets:
    - ../../plg-platform-backend/src/app/Http/Controllers/ImpartedClassController.php
    - ../../plg-platform-backend/src/app/Http/Controllers/EventController.php
    - ../../plg-platform-backend/src/app/Http/Controllers/ProfessorInvoiceController.php
    - ../../plg-platform-backend/src/app/Models/Event.php
    - ../../plg-platform-backend/src/app/Http/Controllers/Api/V2/Hub/**
    - ../../plg-platform-backend/src/app/Services/Hub/**
    - ../../plg-platform-backend/src/app/Support/ImpartedClassSchedulePresenter.php
    - ../../plg-platform-backend/src/tests/Feature/**
    - ../../plg-platform-backend/src/tests/Unit/**
  hot_area: non-diagnostic schedule DTO parity under backend-owned projection
  depends_on:
    - backend-temporal-projection-core
  slice_mode: implementation-heavy
  surface_policy: required
  minimum_valid_completion: regular classes events invoices and Hub schedule DTOs either adopt viewer/source/UTC fields or document tested compatibility where no schedule instant is exposed
  validated_noop_allowed: false
  acceptable_evidence:
    - tests cover at least one regular class DTO and one Hub student DTO in non-Bogota timezone
    - invoice rows render professor timezone from backend fields
    - any intentionally deferred surface is listed with exact route/file and reason

- name: dashboard-render-backend-temporal-fields
  repo: dashboard-frontend
  targets:
    - ../../dashboard-frontend/src/src/utils/dateUtils.js
    - ../../dashboard-frontend/src/src/utils/dateUtils.test.js
    - ../../dashboard-frontend/src/src/utils/timezoneUtils.js
    - ../../dashboard-frontend/src/src/pages/DiagnosticClass/**
    - ../../dashboard-frontend/src/src/pages/ProfessorsDashboard/DiagnosticClass/**
    - ../../dashboard-frontend/src/src/pages/ProfessorsDashboard/Invoice/**
    - ../../dashboard-frontend/src/src/pages/StudentDashboard/**
    - ../../dashboard-frontend/src/src/components/CreateDiagnosticClassModal.jsx
    - ../../dashboard-frontend/src/src/store/DiagnosticClassSlice.js
  hot_area: legacy CRA render-only migration for backend-projected temporal fields
  depends_on:
    - diagnostic-class-backend-contract
    - backend-broader-schedule-surfaces
  slice_mode: implementation-heavy
  surface_policy: required
  minimum_valid_completion: dashboard diagnostic professor admin invoice and student views render viewer_* for display and source_* for edit forms without business timezone conversion as primary behavior
  validated_noop_allowed: false
  acceptable_evidence:
    - npm tests for date utilities prove viewer_* precedence and legacy fallback
    - professor diagnostic list test or equivalent proves Mexico source renders Bogota viewer hour from backend field
    - edit form tests prove source_* values are submitted for schedule edits

- name: hub-render-backend-temporal-fields
  repo: hub-frontend
  targets:
    - ../../hub-frontend/src/features/diagnostic-class-access/**
    - ../../hub-frontend/src/features/professor-dashboard/**
    - ../../hub-frontend/src/features/student-dashboard/**
    - ../../hub-frontend/src/shared/api/timezone.ts
    - ../../hub-frontend/src/shared/api/timezone.test.tsx
    - ../../hub-frontend/src/shared/lib/format.ts
    - ../../hub-frontend/src/test/mocks/handlers.ts
  hot_area: Hub V2 render-only migration for backend-projected temporal fields
  depends_on:
    - diagnostic-class-backend-contract
    - backend-broader-schedule-surfaces
  slice_mode: implementation-heavy
  surface_policy: required
  minimum_valid_completion: Hub diagnostic access student dashboard calendar and future professor diagnostic types render viewer_* and use timezone inputs only as backend request context
  validated_noop_allowed: false
  acceptable_evidence:
    - pnpm tests cover diagnostic access modal Mexico/Bogota display from backend fields
    - student dashboard calendar/card tests prove diagnostic display does not fallback to browser timezone when viewer_* exists
    - typecheck passes with explicit viewer/source temporal fields

- name: temporal-contract-integration-review
  repo: plg-platform-harness
  targets:
    - ../../specs/features/plg/2026-09-10-backend-owned-temporal-projection-contract.spec.md
  hot_area: cross-repo contract evidence and residual debt review
  depends_on:
    - diagnostic-class-backend-contract
    - backend-broader-schedule-surfaces
    - dashboard-render-backend-temporal-fields
    - hub-render-backend-temporal-fields
  slice_mode: verification-only
  surface_policy: forbidden
  minimum_valid_completion: integrated evidence package proves backend-owned projection across backend dashboard and hub without additional product changes
  validated_noop_allowed: true
  acceptable_evidence:
    - all focused slice evidence is present
    - flow ci spec passes for this spec
    - flow ci repo passes for affected repos or each failure is linked to pre-existing unrelated debt
    - reviewer confirms no frontend business timezone conversion remains on migrated display paths
```

## Mandatory Patch Unit Guidance

Implementation agents must decompose slices into Patch Units with one objective each. The following Patch Units are mandatory minimums unless a reviewer approves a narrower equivalent:

| Slice | Patch Unit | Required result |
| --- | --- | --- |
| backend-temporal-projection-core | projector-contract | Introduce/extend a backend projector API that accepts UTC instant, source timezone and viewer timezone. |
| backend-temporal-projection-core | timezone-resolution | Centralize viewer timezone resolution for authenticated, public and system contexts. |
| backend-temporal-projection-core | projector-tests | Unit tests for Bogota/Mexico/Madrid/UTC and invalid timezone dispositions. |
| diagnostic-class-backend-contract | diagnostic-api-dto | Diagnostic APIs expose `starts_at_utc`, `viewer_*`, `source_*`. |
| diagnostic-class-backend-contract | diagnostic-email-fix | Email/ICS use independent projections per recipient. |
| diagnostic-class-backend-contract | diagnostic-edit-compat | Source-local edit payload behavior remains correct. |
| backend-broader-schedule-surfaces | class-event-invoice-inventory | Produce exact list of changed/adopted/deferred schedule DTOs. |
| dashboard-render-backend-temporal-fields | display-render | Lists/cards render `viewer_*`; legacy conversion is fallback only. |
| dashboard-render-backend-temporal-fields | edit-render | Forms render/submit `source_*` for schedule edits. |
| hub-render-backend-temporal-fields | diagnostic-access-render | Public diagnostic access renders backend `viewer_*`. |
| hub-render-backend-temporal-fields | student-calendar-render | Student calendar/cards render backend `viewer_*`. |

## Stop Conditions

Stop implementation and escalate to the orchestrator if any condition occurs:

- A target schedule surface cannot identify the authenticated user or public viewer context.
- A frontend must continue converting business time because the backend response cannot be changed without a broader contract.
- A route exposes user-facing schedule fields but cannot be tested without production-only dependencies.
- Existing persisted data is ambiguous between UTC and local time for the same column and no deterministic compatibility rule can be proven.
- Fixing a field requires a destructive data migration.
- Two slices need to write the same file or change the same response contract in incompatible ways.
- A legacy alias would contradict canonical `viewer_*` fields.

## Acceptance Criteria

1. Backend is the only owner of business timezone projection on migrated schedule display paths.
2. Diagnostic class professor/admin/student/public candidate responses include UTC, source and viewer fields.
3. Professor viewing a Mexico-source diagnostic class from Bogota sees the Bogota-projected hour.
4. Candidate/public views preserve candidate/request timezone semantics.
5. Candidate and professor emails use independent projections and cannot collapse through mutable `Carbon`.
6. Diagnostic edit forms use source-local date/time values, not viewer-local values.
7. Dashboard display paths render backend-projected fields as primary behavior.
8. Hub display paths render backend-projected fields as primary behavior.
9. Legacy compatibility aliases, where retained, match canonical viewer fields or are explicitly source/edit aliases.
10. Invalid/missing timezone behavior follows the disposition matrix.
11. Date filters touched by implementation declare UTC-day vs viewer-local-day semantics and have tests.
12. OpenAPI/docs describe the new response fields for affected public or actions APIs.
13. Focused backend PHPUnit tests pass.
14. Focused dashboard npm tests pass.
15. Focused hub pnpm tests/typecheck pass.
16. `flow ci spec` passes for this spec.
17. No dependency upgrade, broad UI redesign, destructive migration, production command, commit, push, merge, release or publish is part of this work.

## Test Plan

- [@test] ../../plg-platform-backend/src/tests/Unit/Scheduling/DiagnosticClassScheduleNormalizerTest.php
- [@test] ../../plg-platform-backend/src/tests/Feature/ProfessorActionsDiagnosticClassReadTest.php
- [@test] ../../plg-platform-backend/src/tests/Feature/DiagnosticClassSchedulingAuthorizationTest.php
- [@test] ../../plg-platform-backend/src/tests/Feature/ProfessorInvoiceTimezoneTest.php
- [@test] ../../plg-platform-backend/src/tests/Unit/ImpartedClassDateTimeTest.php
- [@test] ../../dashboard-frontend/src/src/utils/dateUtils.test.js
- [@test] ../../hub-frontend/src/pages/DiagnosticClassAccessPage.test.tsx
- [@test] ../../hub-frontend/src/features/student-dashboard/components/events/calendarItems.test.ts
- [@test] ../../hub-frontend/src/features/student-dashboard/normalizeMyAccountStudent.test.ts

## Verification Matrix

```yaml
- name: spec-review
  level: custom
  command: python3 ./flow workspace exec -- python3 ./flow spec review specs/features/plg/2026-09-10-backend-owned-temporal-projection-contract.spec.md --json
  blocking_on: [approval]
  environments: [local]
  notes: validates governance shape, targets and dependency contract

- name: spec-ci
  level: custom
  command: python3 ./flow workspace exec -- python3 ./flow ci spec specs/features/plg/2026-09-10-backend-owned-temporal-projection-contract.spec.md --json
  blocking_on: [ci]
  environments: [local]
  notes: validates canonical spec contract before planning

- name: backend-focused
  level: integration
  command: python3 ./flow repo exec plg-platform-backend -- php -d memory_limit=512M src/vendor/bin/phpunit -c src/phpunit.xml --filter "DiagnosticClass|Timezone|ImpartedClass|ProfessorInvoice"
  blocking_on: [ci]
  environments: [local]
  notes: proves backend projection, diagnostic emails/API and related schedule DTO behavior

- name: dashboard-focused
  level: integration
  command: python3 ./flow repo exec dashboard-frontend -- npm --prefix src test -- --watchAll=false dateUtils
  blocking_on: [ci]
  environments: [local]
  notes: proves dashboard renders backend-projected temporal fields and keeps source-local edit behavior

- name: hub-focused
  level: integration
  command: python3 ./flow repo exec hub-frontend -- pnpm test -- --run diagnostic-class-access student-dashboard
  blocking_on: [ci]
  environments: [local]
  notes: proves Hub diagnostic access and student schedule surfaces consume backend-projected fields

- name: affected-repo-ci
  level: integration
  command: python3 ./flow ci repo plg-platform-backend --json && python3 ./flow ci repo dashboard-frontend --json && python3 ./flow ci repo hub-frontend --json
  blocking_on: [ci]
  environments: [local]
  notes: final repo-level evidence before closeout
```

## Evidence Package

Closeout must include:

- before/after examples for the same diagnostic instant:
  - source `America/Mexico_City` `10:00`;
  - viewer `America/Bogota` `11:00`;
  - UTC `16:00Z`;
- API response excerpts for professor, admin, student and public candidate contexts;
- email/ICS assertion summary for candidate and professor recipients;
- exact commands run and exit status;
- list of migrated surfaces and explicitly deferred surfaces;
- reviewer confirmation that frontends no longer own business timezone conversion for migrated display paths;
- residual debt list limited to named routes/files with reasons.

## Rollout

1. Ship backend fields with compatibility aliases.
2. Migrate dashboard and Hub to render `viewer_*`/`source_*`.
3. Keep legacy aliases until observability or downstream consumer review confirms no active dependency.
4. Later removal of aliases requires a separate deprecation spec.

## Rollback

Rollback must preserve persisted UTC data. If frontend rollout must be reverted, backend compatibility aliases remain available. If backend projector rollout is reverted, frontends may temporarily use legacy fallbacks but must not introduce new business conversion behavior without updating this spec.
