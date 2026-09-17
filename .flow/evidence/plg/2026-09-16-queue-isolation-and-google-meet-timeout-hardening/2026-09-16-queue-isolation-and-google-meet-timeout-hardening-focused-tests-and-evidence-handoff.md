        # Slice Handoff

        - Feature: `2026-09-16-queue-isolation-and-google-meet-timeout-hardening`
        - Slice: `focused-tests-and-evidence`
        - Repo: `plg-platform-backend`
        - Branch: `feat/2026-09-16-queue-isolation-and-google-meet-timeout-hardening-focused-tests-and-evidence`
        - Worktree: `/workspace/.worktrees/plg-platform-backend-2026-09-16-queue-isolation-and-google-meet-timeout-hardening-focused-tests-and-evidence`

        ## Owned targets

        - `../../plg-platform-backend/src/tests/Feature/GoogleMeetReconciliationQueueTest.php`
- `../../plg-platform-backend/src/tests/Feature/ProcessQueueCronBatchCommandTest.php`

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
        - Minimum valid completion: focused PHPUnit suite for this feature green; evidence directory populated
        - Validated no-op allowed: `no`
        - Acceptable evidence:
        - `PHPUnit focused output`
- `flow ci spec JSON for this spec`
        - Closeout rule: Tras una revision corta, si no aparece expansion funcional obligatoria, cerrar con el minimo entregable, evidencia aceptable y diff minimo; solo reabrir alcance ante bloqueo tecnico real.

        ## Command

        ```bash
        git -C /workspace/plg-platform-backend worktree add --relative-paths /workspace/.worktrees/plg-platform-backend-2026-09-16-queue-isolation-and-google-meet-timeout-hardening-focused-tests-and-evidence -b feat/2026-09-16-queue-isolation-and-google-meet-timeout-hardening-focused-tests-and-evidence
        ```

        ## Repo Runtime Command

        Para tests unitarios, linters o cualquier comando del runtime del repo, usa el servicio del repo y el worktree de esta slice:

        ```bash
        python3 ./flow repo exec plg-platform-backend --workdir /workspace/.worktrees/plg-platform-backend-2026-09-16-queue-isolation-and-google-meet-timeout-hardening-focused-tests-and-evidence -- <cmd>
        ```
