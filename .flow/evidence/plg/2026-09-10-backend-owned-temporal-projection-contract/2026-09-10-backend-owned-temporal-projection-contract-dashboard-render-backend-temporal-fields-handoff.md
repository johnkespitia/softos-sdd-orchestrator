        # Slice Handoff

        - Feature: `2026-09-10-backend-owned-temporal-projection-contract`
        - Slice: `dashboard-render-backend-temporal-fields`
        - Repo: `dashboard-frontend`
        - Branch: `feat/2026-09-10-backend-owned-temporal-projection-contract-dashboard-render-backend-temporal-fields`
        - Worktree: `/workspace/.worktrees/dashboard-frontend-2026-09-10-backend-owned-temporal-projection-contract-dashboard-render-backend-temporal-fields`

        ## Owned targets

        - `../../dashboard-frontend/src/src/utils/dateUtils.js`
- `../../dashboard-frontend/src/src/utils/dateUtils.test.js`
- `../../dashboard-frontend/src/src/utils/timezoneUtils.js`
- `../../dashboard-frontend/src/src/pages/DiagnosticClass/**`
- `../../dashboard-frontend/src/src/pages/ProfessorsDashboard/DiagnosticClass/**`
- `../../dashboard-frontend/src/src/pages/ProfessorsDashboard/Invoice/**`
- `../../dashboard-frontend/src/src/pages/StudentDashboard/**`
- `../../dashboard-frontend/src/src/components/CreateDiagnosticClassModal.jsx`
- `../../dashboard-frontend/src/src/store/DiagnosticClassSlice.js`

        ## Linked tests

        - `../../dashboard-frontend/src/src/utils/dateUtils.test.js`

        ## Execution contract

        - Executor mode: `implementation`
        - Slice mode: `implementation-heavy`
        - Surface policy: `required`
        - Minimum valid completion: dashboard diagnostic professor admin invoice and student views render viewer_* for display and source_* for edit forms without business timezone conversion as primary behavior
        - Validated no-op allowed: `no`
        - Acceptable evidence:
        - `npm tests for date utilities prove viewer_* precedence and legacy fallback`
- `professor diagnostic list test or equivalent proves Mexico source renders Bogota viewer hour from backend field`
- `edit form tests prove source_* values are submitted for schedule edits`
        - Closeout rule: Implementar el cambio visible requerido y validar con la evidencia declarada por la spec.

        ## Command

        ```bash
        git -C /workspace/dashboard-frontend worktree add --relative-paths /workspace/.worktrees/dashboard-frontend-2026-09-10-backend-owned-temporal-projection-contract-dashboard-render-backend-temporal-fields -b feat/2026-09-10-backend-owned-temporal-projection-contract-dashboard-render-backend-temporal-fields
        ```

        ## Repo Runtime Command

        Para tests unitarios, linters o cualquier comando del runtime del repo, usa el servicio del repo y el worktree de esta slice:

        ```bash
        python3 ./flow repo exec dashboard-frontend --workdir /workspace/.worktrees/dashboard-frontend-2026-09-10-backend-owned-temporal-projection-contract-dashboard-render-backend-temporal-fields -- <cmd>
        ```
