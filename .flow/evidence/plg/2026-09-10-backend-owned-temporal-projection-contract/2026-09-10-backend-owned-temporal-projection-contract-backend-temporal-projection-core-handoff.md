        # Slice Handoff

        - Feature: `2026-09-10-backend-owned-temporal-projection-contract`
        - Slice: `backend-temporal-projection-core`
        - Repo: `plg-platform-backend`
        - Branch: `feat/2026-09-10-backend-owned-temporal-projection-contract-backend-temporal-projection-core`
        - Worktree: `/workspace/.worktrees/plg-platform-backend-2026-09-10-backend-owned-temporal-projection-contract-backend-temporal-projection-core`

        ## Owned targets

        - `../../plg-platform-backend/src/app/Helpers/TimezoneHelper.php`
- `../../plg-platform-backend/src/app/Support/DiagnosticClassSchedulePresenter.php`
- `../../plg-platform-backend/src/app/Support/ImpartedClassSchedulePresenter.php`
- `../../plg-platform-backend/src/app/Services/Scheduling/**`
- `../../plg-platform-backend/src/app/Models/DiagnosticClass.php`
- `../../plg-platform-backend/src/app/Models/ImpartedClass.php`
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
        - Minimum valid completion: one backend projection contract that independently produces UTC source and viewer fields for diagnostic and regular class examples
        - Validated no-op allowed: `no`
        - Acceptable evidence:
        - `PHPUnit unit tests prove Mexico candidate 10:00 projects to Bogota viewer 11:00 for the same UTC instant`
- `invalid/missing timezone disposition matrix is covered`
- `no mutable Carbon projection reuse remains in the core service`
        - Closeout rule: Implementar el cambio visible requerido y validar con la evidencia declarada por la spec.

        ## Command

        ```bash
        git -C /workspace/plg-platform-backend worktree add --relative-paths /workspace/.worktrees/plg-platform-backend-2026-09-10-backend-owned-temporal-projection-contract-backend-temporal-projection-core -b feat/2026-09-10-backend-owned-temporal-projection-contract-backend-temporal-projection-core
        ```

        ## Repo Runtime Command

        Para tests unitarios, linters o cualquier comando del runtime del repo, usa el servicio del repo y el worktree de esta slice:

        ```bash
        python3 ./flow repo exec --workdir /workspace/.worktrees/plg-platform-backend-2026-09-10-backend-owned-temporal-projection-contract-backend-temporal-projection-core plg-platform-backend -- <cmd>
        ```

        ## Executor Context

        - Required runtime skills: `.agents/skills/php-core/SKILL.md`, `.agents/skills/laravel-8/SKILL.md`, `.agents/skills/softos-agent-playbook/SKILL.md`, `.agents/skills/softos-coding-execution-supervisor/SKILL.md`.
        - Navigation and impact analysis: use the configured Graphify MCP/code graph first when available, then `rg`/targeted reads. Do not infer storage semantics from the frontend.
        - Canonical references live in the workspace root. The worktree does not contain `.flow/**`; resolve the handoff from `/workspace` or the host workspace root.
        - The executor may use repository reads, Graphify MCP, `python3 ./flow repo exec`, PHP lint, PHPUnit, and git diff/status checks only within the assigned scope.
        - Do not use host PHP or host-relative `./flow` from inside the worktree. Runtime verification must use the repository service command above.

        ## Patch Unit Policy

        - One intent per Patch Unit, preferably one or two files for `opencode-local`.
        - Report tools used, files changed, exact commands/results, pending risks, and next gate.
        - A zero exit code is insufficient: accept only an authorized non-empty diff plus focused evidence, unless the spec explicitly allows a verified no-op.
        - On timeout or step exhaustion, preserve the worktree and retry the same unit with a smaller scope or another configured executor. Do not duplicate writes concurrently.
