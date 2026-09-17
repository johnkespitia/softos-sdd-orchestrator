        # Slice Handoff

        - Feature: `2026-09-10-backend-owned-temporal-projection-contract`
        - Slice: `backend-broader-schedule-surfaces`
        - Repo: `plg-platform-backend`
        - Branch: `feat/2026-09-10-backend-owned-temporal-projection-contract-backend-broader-schedule-surfaces`
        - Worktree: `/workspace/.worktrees/plg-platform-backend-2026-09-10-backend-owned-temporal-projection-contract-backend-broader-schedule-surfaces`

        ## Owned targets

        - `../../plg-platform-backend/src/app/Http/Controllers/ImpartedClassController.php`
- `../../plg-platform-backend/src/app/Http/Controllers/EventController.php`
- `../../plg-platform-backend/src/app/Http/Controllers/ProfessorInvoiceController.php`
- `../../plg-platform-backend/src/app/Http/Controllers/Api/V2/Hub/**`
- `../../plg-platform-backend/src/app/Services/Hub/**`
- `../../plg-platform-backend/src/app/Support/ImpartedClassSchedulePresenter.php`
- `../../plg-platform-backend/src/tests/Feature/**`
- `../../plg-platform-backend/src/tests/Unit/**`

        ## Linked tests

        - `../../plg-platform-backend/src/tests/Unit/Scheduling/DiagnosticClassScheduleNormalizerTest.php`
- `../../plg-platform-backend/src/tests/Feature/ProfessorActionsDiagnosticClassReadTest.php`
- `../../plg-platform-backend/src/tests/Feature/DiagnosticClassSchedulingAuthorizationTest.php`
- `../../plg-platform-backend/src/tests/Feature/ProfessorInvoiceTimezoneTest.php`
- `../../plg-platform-backend/src/tests/Unit/ImpartedClassDateTimeTest.php`

        ## Execution contract

        - Executor mode: `implementation`
        - Slice mode: `implementation-heavy`
        - Surface policy: `required`
        - Minimum valid completion: regular classes events invoices and Hub schedule DTOs either adopt viewer/source/UTC fields or document tested compatibility where no schedule instant is exposed
        - Validated no-op allowed: `no`
        - Acceptable evidence:
        - `tests cover at least one regular class DTO and one Hub student DTO in non-Bogota timezone`
- `invoice rows render professor timezone from backend fields`
- `any intentionally deferred surface is listed with exact route/file and reason`
        - Closeout rule: Implementar el cambio visible requerido y validar con la evidencia declarada por la spec.

        ## Command

        ```bash
        git -C /workspace/plg-platform-backend worktree add --relative-paths /workspace/.worktrees/plg-platform-backend-2026-09-10-backend-owned-temporal-projection-contract-backend-broader-schedule-surfaces -b feat/2026-09-10-backend-owned-temporal-projection-contract-backend-broader-schedule-surfaces
        ```

        ## Orchestrator checkpoint 2026-09-11

        - B-001/B-002 regular-class DTO: accepted after presenter repair and focused evidence.
        - B-003/B-005 EventController: B-005 accepted after source/write repair; B-006 evidence adds 2 tests / 17 assertions for Mexico City store and index projection.
        - B-004 invoices: accepted; 2 tests / 24 assertions.
        - B-007b/B-008b Hub event DTO: accepted; Hub focal suite 14 tests / 64 assertions, including Mexico City viewer projection.
        - Independent reviews: PASS for B-006 and B-007b/B-008b. All accepted executor/reviewer runs used ACP transport.
        - OpenCode local ACP runs were attempted for B-006, B-007 and B-008; they ended without an actionable handoff or diff, so they were not accepted as implementation evidence.
        - B-009b Carbon/CarbonImmutable compatibility: accepted after repair and independent PASS; projector suite is now 9 tests / 60 assertions green.
        - R-010b Event partial update: accepted after independent PASS; EventController test file is now 3 tests / 21 assertions.
        - R-011b Hub persistence immutability: accepted after focused PASS; Hub test now asserts UTC columns remain unchanged after Mexico City projection (1 test / 6 assertions).
        - R-012 raw Hub `listItem`: accepted after independent PASS; direct callers now receive explicit viewer context and raw Events are cloned/projected without mutation.
        - R-013 test teardown: accepted after independent PASS; the test uses normal Laravel teardown and isolates the legacy shutdown logging callback.
        - Residual low risks: nullable viewer compatibility, partial projection-attribute edge cases, and the production mail shutdown callback remain documented; full backend suite has unrelated baseline failures and is not green evidence.
        - Next gate after risk remediation: integrated G4 validation of the added tests, then G5 re-review of the complete slice.

        ## Surface inventory / deferred contract

        | Status | Surface | Route/file | Decision and reason |
        |---|---|---|---|
        | adopted | Regular class DTO | `ImpartedClassController.php`, `ImpartedClassSchedulePresenter.php` | Emits source/viewer/UTC fields through the shared projector; covered by focused tests. |
        | adopted | Diagnostic class reads | `DiagnosticClassController.php`, `DiagnosticClassSchedulePresenter.php` | Authenticated viewer projection; owned by the diagnostic backend slice and integrated here as dependency. |
        | adopted | HR events | `EventController.php`, `/api/hr-management/events` | UTC canonical storage, requester-context writes, viewer/source response fields, partial-update coverage. |
        | adopted | Hub student events | `HubEventPresentationService.php`, `/api/v2/hub/events` | Clone-based viewer projection with source/viewer/UTC fields and persistence immutability test. |
        | adopted | Professor invoices | `ProfessorInvoiceController.php`, invoice preview/list | Viewer timezone rendered from backend projection; focused invoice evidence green. |
        | dependency | Shared temporal projector | `src/app/Services/Scheduling/TemporalScheduleProjection.php` | Implemented and accepted by the core slice; consumed here, therefore referenced as a cross-slice dependency rather than re-owned. |
        | deferred | Contrated plan legacy decoration | `src/app/Http/Controllers/ContratedPlanController.php`, legacy plan routes | No schedule DTO surface in this slice's accepted contract; remains outside broader-schedule ownership and requires a separate inventory/compatibility decision. |
        | deferred | Diagnostic legacy email projection | `DiagnosticClassController.php`, legacy notification paths | Out of this slice's write ownership; diagnostic backend slice owns its follow-up and must preserve recipient-specific rendering. |
        | hardened | Hub direct `listItem` reuse | `HubEventPresentationService::listItem()` | Accepts explicit viewer context and projects raw Events on a clone; current controller passes the authenticated user. |

        The deferred entries are intentional, have exact paths/reasons, and are not release blockers for this slice's declared minimum completion. The hardened `listItem` surface is no longer deferred.

        ## Repo Runtime Command

        Para tests unitarios, linters o cualquier comando del runtime del repo, usa el servicio del repo y el worktree de esta slice:

        ```bash
        python3 ./flow repo exec plg-platform-backend --workdir /workspace/.worktrees/plg-platform-backend-2026-09-10-backend-owned-temporal-projection-contract-backend-broader-schedule-surfaces -- <cmd>
        ```
