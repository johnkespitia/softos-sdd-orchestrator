        # Slice Handoff

        - Feature: `2026-09-10-backend-owned-temporal-projection-contract`
        - Slice: `hub-render-backend-temporal-fields`
        - Repo: `hub-frontend`
        - Branch: `feat/2026-09-10-backend-owned-temporal-projection-contract-hub-render-backend-temporal-fields`
        - Worktree: `/workspace/.worktrees/hub-frontend-2026-09-10-backend-owned-temporal-projection-contract-hub-render-backend-temporal-fields`

        ## Owned targets

        - `../../hub-frontend/src/features/diagnostic-class-access/**`
- `../../hub-frontend/src/features/professor-dashboard/**`
- `../../hub-frontend/src/features/student-dashboard/**`
- `../../hub-frontend/src/shared/api/timezone.ts`
- `../../hub-frontend/src/shared/api/timezone.test.tsx`
- `../../hub-frontend/src/shared/lib/format.ts`
- `../../hub-frontend/src/test/mocks/handlers.ts`

        ## Linked tests

        - `../../hub-frontend/src/pages/DiagnosticClassAccessPage.test.tsx`
- `../../hub-frontend/src/features/student-dashboard/components/events/calendarItems.test.ts`
- `../../hub-frontend/src/features/student-dashboard/normalizeMyAccountStudent.test.ts`

        ## Execution contract

        - Executor mode: `implementation`
        - Slice mode: `implementation-heavy`
        - Surface policy: `required`
        - Minimum valid completion: Hub diagnostic access student dashboard calendar and future professor diagnostic types render viewer_* and use timezone inputs only as backend request context
        - Validated no-op allowed: `no`
        - Acceptable evidence:
        - `pnpm tests cover diagnostic access modal Mexico/Bogota display from backend fields`
- `student dashboard calendar/card tests prove diagnostic display does not fallback to browser timezone when viewer_* exists`
- `typecheck passes with explicit viewer/source temporal fields`
        - Closeout rule: Implementar el cambio visible requerido y validar con la evidencia declarada por la spec.

        ## Command

        ```bash
        git -C /workspace/hub-frontend worktree add --relative-paths /workspace/.worktrees/hub-frontend-2026-09-10-backend-owned-temporal-projection-contract-hub-render-backend-temporal-fields -b feat/2026-09-10-backend-owned-temporal-projection-contract-hub-render-backend-temporal-fields
        ```

        ## Repo Runtime Command

        Para tests unitarios, linters o cualquier comando del runtime del repo, usa el servicio del repo y el worktree de esta slice:

        ```bash
        python3 ./flow repo exec hub-frontend --workdir /workspace/.worktrees/hub-frontend-2026-09-10-backend-owned-temporal-projection-contract-hub-render-backend-temporal-fields -- <cmd>
        ```
