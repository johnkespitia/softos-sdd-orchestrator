        # Slice Handoff

        - Feature: `2026-09-16-queue-isolation-and-google-meet-timeout-hardening`
        - Slice: `meet-retry-after-and-stop-conditions`
        - Repo: `plg-platform-backend`
        - Branch: `feat/2026-09-16-queue-isolation-and-google-meet-timeout-hardening-meet-retry-after-and-stop-conditions`
        - Worktree: `/workspace/.worktrees/plg-platform-backend-2026-09-16-queue-isolation-and-google-meet-timeout-hardening-meet-retry-after-and-stop-conditions`

        ## Owned targets

        - `../../plg-platform-backend/src/app/Services/GoogleWorkspace/GoogleMeetTranscriptProvider.php`
- `../../plg-platform-backend/src/app/Services/GoogleWorkspace/GoogleMeetTranscriptIngestionService.php`
- `../../plg-platform-backend/src/app/Jobs/ReconcileMeetConferenceSessionsJob.php`
- `../../plg-platform-backend/src/app/Jobs/IngestGoogleMeetTranscriptJob.php`
- `../../plg-platform-backend/src/app/Services/GoogleWorkspace/GoogleMeetConferenceSessionBindingService.php`
- `../../plg-platform-backend/src/config/google.php`

        ## Linked tests

        - `../../plg-platform-backend/src/tests/Feature/GoogleMeetReconciliationQueueTest.php`
- `../../plg-platform-backend/src/tests/Feature/ProcessQueueCronBatchCommandTest.php`
- `../../plg-platform-backend/src/tests/Feature/GoogleMeetClassSessionBoundaryTest.php`
- `../../plg-platform-backend/src/tests/Feature/GoogleMeetClassTranscriptIngestionTest.php`
- `../../plg-platform-backend/src/tests/Feature/GoogleMeetTranscriptPresentationContractTest.php`

        ## Execution contract

        - Executor mode: `compliance-closeout`
        - Slice mode: `minimal-change`
        - Surface policy: `required`
        - Minimum valid completion: Retry-After parsed and applied via release/delay; no new DB columns; observed_unbound/not_generated paths preserved
        - Validated no-op allowed: `no`
        - Acceptable evidence:
        - `provider unit/feature test with Retry-After header`
- `pagination max-pages stop test`
- `reconcile tries/checkpoint regression assertions`
        - Closeout rule: Tras una revision corta, si no aparece expansion funcional obligatoria, cerrar con el minimo entregable, evidencia aceptable y diff minimo; solo reabrir alcance ante bloqueo tecnico real.

        ## Command

        ```bash
        git -C /workspace/plg-platform-backend worktree add --relative-paths /workspace/.worktrees/plg-platform-backend-2026-09-16-queue-isolation-and-google-meet-timeout-hardening-meet-retry-after-and-stop-conditions -b feat/2026-09-16-queue-isolation-and-google-meet-timeout-hardening-meet-retry-after-and-stop-conditions
        ```

        ## Repo Runtime Command

        Para tests unitarios, linters o cualquier comando del runtime del repo, usa el servicio del repo y el worktree de esta slice:

        ```bash
        python3 ./flow repo exec plg-platform-backend --workdir /workspace/.worktrees/plg-platform-backend-2026-09-16-queue-isolation-and-google-meet-timeout-hardening-meet-retry-after-and-stop-conditions -- <cmd>
        ```
