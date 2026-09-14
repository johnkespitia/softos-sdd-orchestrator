---
schema_version: 3
name: "PLG staging deploy env and healthcheck hardening"
description: "Ensure the backend staging deploy materializes runtime database configuration and validates a resolvable healthcheck before remote execution."
status: approved
owner: platform
depends_on:
  - specs/000-foundation/spec-as-source-operating-model.spec.md
  - specs/000-foundation/spec-driven-delivery-and-infrastructure.spec.md
  - specs/000-foundation/repo-routing-and-worktree-orchestration.spec.md
  - specs/000-foundation/plg-platform-backend-foundation-alignment.spec.md
required_runtimes:
  - php-laravel8-apache
required_services: []
required_capabilities:
  - laravel8
targets:
  - ../../specs/features/plg/2026-09-11-staging-deploy-env-healthcheck-hardening.spec.md
  - ../../plg-platform-backend/.github/workflows/staging.yml
  - ../../plg-platform-backend/scripts/deploy/build_deploy_env_patch.sh
  - ../../plg-platform-backend/src/scripts/deploy/ensure_google_workspace_env.sh
test_refs: []
---

# PLG staging deploy env and healthcheck hardening

slice_mode: minimal-change
surface_policy: required

## Objective

Make the backend staging deploy fail-safe for runtime configuration: the remote
Laravel process must receive the intended staging database variables, and the
post-deploy healthcheck must target a resolvable staging endpoint. Runtime PDF
and mail assets required by existing application flows must also survive the
deploy transfer.

## Scope

- `../../plg-platform-backend/.github/workflows/staging.yml`
- `../../plg-platform-backend/src/scripts/deploy/build_deploy_env_patch.sh`
- `../../plg-platform-backend/src/scripts/deploy/ensure_google_workspace_env.sh`
- existing tracked assets under `../../plg-platform-backend/src/storage/app/public/pdf_assets/**`
- existing tracked assets under `../../plg-platform-backend/src/storage/app/public/mail_assets/**`
- focused deployment evidence/tests where already supported by the repository

Do not change application behavior, migrations, SMTP configuration, or unrelated
frontend/root files.

## Acceptance criteria

1. The deploy path cannot silently continue with a stale or incomplete remote
   `DB_HOST`, `DB_DATABASE`, `DB_USERNAME`, or `DB_PASSWORD`.
2. Runtime database configuration is applied through the existing deploy
   mechanism without exposing secret values in logs.
3. The staging healthcheck URL is validated before deploy and is resolvable from
   the GitHub runner, or the workflow stops with an actionable error.
4. Existing rsync, env assertions, and deploy behavior remain intact.
5. The deploy transfers the existing tracked `pdf_assets` and `mail_assets`
   required by the application, while continuing to exclude runtime-generated
   storage state and secrets.
6. `git diff --check`, relevant shell/workflow validation, and a successful
   staging workflow run provide evidence.

## Stop conditions

- Stop before remote deployment if required DB variables are absent or the
  healthcheck host cannot resolve.
- Do not run migrations for this hardening change unless explicitly requested.

## Evidence

- Failed staging run: `34554123144`
- Failure: Laravel used `forge@127.0.0.1` with no password during seed/materialize;
  healthcheck returned curl error 6 for `apitest.plgeducation.com`.

## Slice Breakdown

```yaml
- name: staging-deploy-env-patch
  repo: plg-platform-backend
  targets:
    - ../../plg-platform-backend/scripts/deploy/build_deploy_env_patch.sh
    - ../../plg-platform-backend/src/scripts/deploy/ensure_google_workspace_env.sh
  hot_area: staging remote runtime environment materialization
  depends_on: []
  slice_mode: minimal-change
  surface_policy: required
  minimum_valid_completion: deploy patch applies DB runtime configuration explicitly without logging secret values
  validated_noop_allowed: false
  acceptable_evidence:
    - shell validation passes
    - git diff --check passes for target files
  
- name: staging-deploy-workflow-guard
  repo: plg-platform-backend
  targets:
    - ../../plg-platform-backend/.github/workflows/staging.yml
  hot_area: staging workflow preflight and remote deploy ordering
  depends_on: [staging-deploy-env-patch]
  slice_mode: minimal-change
  surface_policy: required
  minimum_valid_completion: workflow verifies required runtime variables and does not deploy with stale or incomplete environment state
  validated_noop_allowed: false
  acceptable_evidence:
    - workflow syntax/contract validation passes
    - git diff --check passes for target files

- name: staging-runtime-assets
  repo: plg-platform-backend
  targets:
    - ../../plg-platform-backend/.github/workflows/staging.yml
  hot_area: staging application PDF and mail asset transfer
  depends_on: [staging-deploy-workflow-guard]
  slice_mode: minimal-change
  surface_policy: required
  minimum_valid_completion: tracked pdf_assets and mail_assets required by current application flows are transferred to staging without syncing generated runtime storage
  validated_noop_allowed: false
  acceptable_evidence:
    - workflow transfer contract explicitly includes required asset paths
    - workflow or focused shell validation proves the paths are present after transfer
    - git diff --check passes for target files

- name: staging-healthcheck-guard
  repo: plg-platform-backend
  targets:
    - ../../plg-platform-backend/.github/workflows/staging.yml
  hot_area: staging post-deploy health verification
  depends_on: [staging-deploy-workflow-guard]
  slice_mode: minimal-change
  surface_policy: required
  minimum_valid_completion: healthcheck host is validated as resolvable before remote deployment or the workflow stops with an actionable error
  validated_noop_allowed: false
  acceptable_evidence:
    - healthcheck validation is covered by workflow evidence
    - git diff --check passes for target files
```

## Test Plan

- [@test] ../../plg-platform-backend/src/tests/Feature/DiagnosticClassCloseNotificationTest.php
- [@test] ../../plg-platform-backend/src/tests/Feature/DiagnosticClassCloseEmailDispatchOnUpdateTest.php

## Verification Matrix

```yaml
- name: spec-review
  level: custom
  command: python3 ./flow workspace exec -- python3 ./flow spec review specs/features/plg/2026-09-11-staging-deploy-env-healthcheck-hardening.spec.md --json
  blocking_on: [approval]
  environments: [local]

- name: spec-ci
  level: custom
  command: python3 ./flow workspace exec -- python3 ./flow ci spec specs/features/plg/2026-09-11-staging-deploy-env-healthcheck-hardening.spec.md --json
  blocking_on: [ci]
  environments: [local]

- name: backend-runtime-regression
  level: integration
  command: python3 ./flow repo exec plg-platform-backend -- php -d memory_limit=512M src/vendor/bin/phpunit -c src/phpunit.xml src/tests/Feature/DiagnosticClassCloseEmailDispatchOnUpdateTest.php src/tests/Feature/DiagnosticClassCloseNotificationTest.php
  blocking_on: [ci]
  environments: [local]

- name: staging-deploy
  level: integration
  command: gh run watch <staging-run-id> --repo PLGEducation/plg-platform-backend --exit-status
  blocking_on: [ci]
  environments: [staging]

- name: staging-runtime-assets
  level: integration
  command: test -r storage/app/public/pdf_assets/membrete_page.png && test -r storage/app/public/mail_assets/mail-bg3.png
  blocking_on: [ci]
  environments: [staging]
```
