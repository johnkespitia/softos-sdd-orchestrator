---
schema_version: 3
name: "PLG staging PDF and mail asset deployment"
description: "Ensure tracked PDF and mail assets required by existing backend flows are transferred during staging deployment."
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
  - ../../plg-platform-backend/.github/workflows/staging.yml
  - ../../plg-platform-backend/src/storage/app/public/pdf_assets/membrete_page.png
  - ../../plg-platform-backend/src/storage/app/public/mail_assets/mail-bg3.png
test_refs:
  - ../../plg-platform-backend/src/tests/Feature/DiagnosticClassCloseEmailDispatchOnUpdateTest.php
---

# PLG staging PDF and mail asset deployment

slice_mode: minimal-change
surface_policy: required

## Objective

Make the existing staging deploy transfer the tracked runtime assets required by
the diagnostic-class close PDF and its email template.

## Context

The staging workflow rsyncs `src/` while excluding `storage/*`. The application
requires `storage/app/public/pdf_assets/membrete_page.png` to generate the entry
report PDF and `storage/app/public/mail_assets/mail-bg3.png` for the close-email
background. The assets exist in the repository but are absent on a fresh or
reset staging host.

## Scope

- Modify only `../../plg-platform-backend/.github/workflows/staging.yml`.
- Preserve exclusion of generated runtime storage, caches, logs, and secrets.
- Explicitly transfer tracked `storage/app/public/pdf_assets/**` and
  `storage/app/public/mail_assets/**`.
- Ensure the remote directories exist before transfer and remain readable by the
  application process.

## Out of scope

- Application/PHP behavior.
- SMTP, queue, database, migrations, or healthcheck changes.
- Adding new image assets or changing their contents.
- Production deployment workflow.

## Acceptance criteria

1. The staging workflow transfers the existing tracked PDF and mail asset paths.
2. The workflow does not transfer generated storage state or secret files.
3. The remote deploy creates required asset directories before transfer.
4. The workflow validates the two critical files after transfer without printing
   file contents or secrets.
5. YAML/shell validation and `git diff --check` pass.
6. A successful staging run plus a PDF download confirms the asset is available.

## Stop conditions

- Stop before deploy if either source asset is absent from the checkout.
- Do not broaden rsync to all of `storage/`.
- Do not modify application code or email logic.

## Slice Breakdown

```yaml
- name: staging-pdf-mail-assets-source
  repo: plg-platform-backend
  targets:
    - ../../plg-platform-backend/src/storage/app/public/pdf_assets/membrete_page.png
    - ../../plg-platform-backend/src/storage/app/public/mail_assets/mail-bg3.png
  hot_area: source asset availability
  depends_on: []
  slice_mode: minimal-change
  surface_policy: required
  minimum_valid_completion: both tracked source assets exist and are non-empty
  validated_noop_allowed: false
  acceptable_evidence:
    - source asset presence checks pass

- name: staging-pdf-mail-assets-workflow
  repo: plg-platform-backend
  targets:
    - ../../plg-platform-backend/.github/workflows/staging.yml
  hot_area: staging rsync asset inclusion
  depends_on: [staging-pdf-mail-assets-source]
  slice_mode: minimal-change
  surface_policy: required
  minimum_valid_completion: workflow explicitly transfers and validates the tracked PDF and mail asset directories without syncing generated storage
  validated_noop_allowed: false
  acceptable_evidence:
    - YAML/shell validation passes
    - source asset presence checks pass
    - git diff --check passes
```

## Verification Matrix

```yaml
- name: spec-review
  level: custom
  command: python3 ./flow workspace exec -- python3 ./flow spec review specs/features/plg/2026-09-11-staging-pdf-mail-assets-deploy.spec.md --json
  blocking_on: [approval]
  environments: [local]

- name: workflow-contract
  level: custom
  command: git diff --check -- plg-platform-backend/.github/workflows/staging.yml
  blocking_on: [ci]
  environments: [local]

- name: source-assets
  level: integration
  command: test -s plg-platform-backend/src/storage/app/public/pdf_assets/membrete_page.png && test -s plg-platform-backend/src/storage/app/public/mail_assets/mail-bg3.png
  blocking_on: [ci]
  environments: [local]

- name: staging-deploy-and-pdf
  level: integration
  command: gh run watch staging-run-id --repo PLGEducation/plg-platform-backend --exit-status
  blocking_on: [ci]
  environments: [staging]
```

## Test Plan

- [@test] ../../plg-platform-backend/src/tests/Feature/DiagnosticClassCloseEmailDispatchOnUpdateTest.php
