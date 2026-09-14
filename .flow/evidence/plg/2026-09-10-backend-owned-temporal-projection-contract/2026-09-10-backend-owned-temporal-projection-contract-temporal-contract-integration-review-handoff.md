        # Slice Handoff

        - Feature: `2026-09-10-backend-owned-temporal-projection-contract`
        - Slice: `temporal-contract-integration-review`
        - Repo: `plg-platform-harness`
        - Branch: `feat/2026-09-10-backend-owned-temporal-projection-contract-temporal-contract-integration-review`
        - Worktree: `/workspace/.worktrees/plg-platform-harness-2026-09-10-backend-owned-temporal-projection-contract-temporal-contract-integration-review`

        ## Owned targets

        - `../../specs/features/plg/2026-09-10-backend-owned-temporal-projection-contract.spec.md`

        ## Linked tests

        - Ninguno declarado.

        ## Execution contract

        - Executor mode: `compliance-closeout`
        - Slice mode: `verification-only`
        - Surface policy: `forbidden`
        - Minimum valid completion: integrated evidence package proves backend-owned projection across backend dashboard and hub without additional product changes
        - Validated no-op allowed: `yes`
        - Acceptable evidence:
        - `all focused slice evidence is present`
- `flow ci spec passes for this spec`
- `flow ci repo passes for affected repos or each failure is linked to pre-existing unrelated debt`
- `reviewer confirms no frontend business timezone conversion remains on migrated display paths`
        - Closeout rule: Tras una revision corta, si no aparece expansion funcional obligatoria, cerrar con el minimo entregable, evidencia aceptable y diff minimo; solo reabrir alcance ante bloqueo tecnico real.

        ## Command

        ```bash
        git -C /workspace worktree add --relative-paths /workspace/.worktrees/plg-platform-harness-2026-09-10-backend-owned-temporal-projection-contract-temporal-contract-integration-review -b feat/2026-09-10-backend-owned-temporal-projection-contract-temporal-contract-integration-review
        ```

        ## Repo Runtime Command

        Para tests unitarios, linters o cualquier comando del runtime del repo, usa el servicio del repo y el worktree de esta slice:

        ```bash
        python3 ./flow repo exec plg-platform-harness --workdir /workspace/.worktrees/plg-platform-harness-2026-09-10-backend-owned-temporal-projection-contract-temporal-contract-integration-review -- <cmd>
        ```
