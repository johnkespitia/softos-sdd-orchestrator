        # Slice Handoff

        - Feature: `2026-09-16-queue-isolation-and-google-meet-timeout-hardening`
        - Slice: `queue-isolation-invariant-and-caps`
        - Repo: `plg-platform-backend`
        - Branch: `feat/2026-09-16-queue-isolation-and-google-meet-timeout-hardening-queue-isolation-invariant-and-caps`
        - Worktree: `/workspace/.worktrees/plg-platform-backend-2026-09-16-queue-isolation-and-google-meet-timeout-hardening-queue-isolation-invariant-and-caps`

        ## Owned targets

        - `../../plg-platform-backend/src/app/Console/Kernel.php`
- `../../plg-platform-backend/src/app/Console/Commands/ProcessQueueCronBatchCommand.php`
- `../../plg-platform-backend/src/app/Http/Controllers/CronjobController.php`
- `../../plg-platform-backend/src/app/Http/Controllers/QueueController.php`
- `../../plg-platform-backend/src/config/queue.php`

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
        - Minimum valid completion: dual-batch isolation preserved; locks/caps explicit; timeout < connection retry_after
        - Validated no-op allowed: `no`
        - Acceptable evidence:
        - `focused ProcessQueueCronBatchCommand / schedule isolation tests pass`
- `config or command evidence showing timeout/retry_after alignment`
        - Closeout rule: Tras una revision corta, si no aparece expansion funcional obligatoria, cerrar con el minimo entregable, evidencia aceptable y diff minimo; solo reabrir alcance ante bloqueo tecnico real.

        ## Command

        ```bash
        git -C /workspace/plg-platform-backend worktree add --relative-paths /workspace/.worktrees/plg-platform-backend-2026-09-16-queue-isolation-and-google-meet-timeout-hardening-queue-isolation-invariant-and-caps -b feat/2026-09-16-queue-isolation-and-google-meet-timeout-hardening-queue-isolation-invariant-and-caps
        ```

        ## Repo Runtime Command

        Para tests unitarios, linters o cualquier comando del runtime del repo, usa el servicio del repo y el worktree de esta slice:

        ```bash
        python3 ./flow repo exec plg-platform-backend --workdir /workspace/.worktrees/plg-platform-backend-2026-09-16-queue-isolation-and-google-meet-timeout-hardening-queue-isolation-invariant-and-caps -- <cmd>
        ```
