        # Slice Handoff

        - Feature: `2026-09-10-backend-owned-temporal-projection-contract`
        - Slice: `diagnostic-class-backend-contract`
        - Repo: `plg-platform-backend`
        - Branch: `feat/2026-09-10-backend-owned-temporal-projection-contract-diagnostic-class-backend-contract`
        - Worktree: `/workspace/.worktrees/plg-platform-backend-2026-09-10-backend-owned-temporal-projection-contract-diagnostic-class-backend-contract`

        ## Owned targets

        - `../../plg-platform-backend/src/app/Http/Controllers/DiagnosticClassController.php`
- `../../plg-platform-backend/src/app/Http/Controllers/Actions/Professor/**`
- `../../plg-platform-backend/src/app/Services/Actions/**`
- `../../plg-platform-backend/src/app/Services/Hub/**`
- `../../plg-platform-backend/src/app/Support/DiagnosticClassSchedulePresenter.php`
- `../../plg-platform-backend/src/docs/openapi/**`
- `../../plg-platform-backend/src/resources/views/email/**`
- `../../plg-platform-backend/src/routes/api.php`
- `../../plg-platform-backend/src/tests/Feature/**`

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
        - Minimum valid completion: diagnostic class APIs and scheduled emails return/render viewer-specific fields for professor admin student and public candidate contexts while preserving source-local editing
        - Validated no-op allowed: `no`
        - Acceptable evidence:
        - `feature tests for professor legacy response use professor timezone`
- `feature tests for admin response use authenticated admin timezone`
- `feature tests for public candidate access use request timezone when valid and source timezone otherwise`
- `email tests prove candidate and professor templates differ for Mexico/Bogota when expected`
- `OpenAPI documents viewer/source/UTC fields`
        - Closeout rule: Implementar el cambio visible requerido y validar con la evidencia declarada por la spec.

        ## Command

        ```bash
        git -C /workspace/plg-platform-backend worktree add --relative-paths /workspace/.worktrees/plg-platform-backend-2026-09-10-backend-owned-temporal-projection-contract-diagnostic-class-backend-contract -b feat/2026-09-10-backend-owned-temporal-projection-contract-diagnostic-class-backend-contract
        ```

        ## Repo Runtime Command

        Para tests unitarios, linters o cualquier comando del runtime del repo, usa el servicio del repo y el worktree de esta slice:

        ```bash
        python3 ./flow repo exec plg-platform-backend --workdir /workspace/.worktrees/plg-platform-backend-2026-09-10-backend-owned-temporal-projection-contract-diagnostic-class-backend-contract -- <cmd>
        ```

        ## Executor Context

        - Canonical workspace root: `/home/john/workspace/plg-platform-harness`.
        - Canonical feature spec: `/home/john/workspace/plg-platform-harness/specs/features/plg/2026-09-10-backend-owned-temporal-projection-contract.spec.md`.
        - This handoff is operational context only; `specs/**` is the source of truth and `.flow/**` is not present inside the repo worktree.
        - Required skills: `php-core`, `laravel-8`, `softos-agent-playbook`, `softos-coding-execution-supervisor`.
        - Navigation: use Graphify MCP/code graph when available; otherwise use targeted `rg`, `sed`, and existing tests. Do not broad-scan unrelated repositories.
        - Allowed tools: read/edit owned files, repository runtime commands through the exact command above, focused tests, and git diff/status. Do not commit, push, merge, delegate, or expand scope.

        ## Patch Unit Policy

        - One Patch Unit has one behavioral objective and explicit file ownership.
        - Prefer one or two files per PU, especially for `opencode-local`; split controller work by sequential PUs because the controller is shared ownership.
        - Preserve source-local editing semantics: incoming candidate-local date/time plus candidate timezone is converted to UTC at write time; read/email projection is viewer-specific and backend-owned.
        - Every handoff must state prerequisites, exact targets, verification command, stop conditions, and expected evidence.
        - Accept only an authorized non-empty diff with focused evidence. If an executor times out or stalls, stop it, inspect the diff, and retry with a smaller PU or another executor.
