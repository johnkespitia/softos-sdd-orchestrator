---
schema_version: 3
name: "PLG production PDF and mail asset deployment"
description: "Ensure production deploy paths transfer tracked PDF and mail assets required by existing backend flows."
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
  - ../../plg-platform-backend/.github/workflows/production.yml
  - ../../plg-platform-backend/.github/workflows/deploy-on-pr-merge.yml
  - ../../plg-platform-backend/src/storage/app/public/pdf_assets/membrete_page.png
  - ../../plg-platform-backend/src/storage/app/public/mail_assets/mail-bg3.png
test_refs:
  - ../../plg-platform-backend/src/tests/Feature/DiagnosticClassCloseEmailDispatchOnUpdateTest.php
---

# PLG production PDF and mail asset deployment

slice_mode: minimal-change
surface_policy: required

## Objective

Make both production deploy paths transfer the tracked runtime assets required
by the diagnostic-class close PDF and email template.

## Context

The manual production workflow and the post-promote merge workflow both rsync
the application while excluding `storage/*`. The application requires
`storage/app/public/pdf_assets/membrete_page.png` for the entry report PDF and
`storage/app/public/mail_assets/mail-bg3.png` for the close-email background.

## Scope

- Modify only `production.yml` and `deploy-on-pr-merge.yml`.
- Preserve exclusion of generated runtime storage, caches, logs, uploads, and
  secrets.
- Explicitly transfer tracked `pdf_assets/**` and `mail_assets/**`.
- Validate source and remote critical files without printing their contents.

## Out of scope

- Application/PHP behavior, SMTP, queues, database, migrations, or asset content.
- Staging workflow, which is governed by its own spec.
- Any production deploy execution in this implementation slice.

## Acceptance criteria

1. Both production paths transfer the two tracked asset directories.
2. Neither path broadens rsync to all of `storage/`.
3. Required remote directories are created before transfer.
4. Source and remote checks validate `membrete_page.png` and `mail-bg3.png`.
5. YAML/shell validation and `git diff --check` pass.
6. Production deploy verification confirms the files are readable and the PDF
   download succeeds.

## Stop conditions

- Stop before deployment if either source asset is absent or empty.
- Do not change production application behavior or execute production deploy as
  part of implementation.

## Slice Breakdown

```yaml
- name: production-pdf-mail-assets-source
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

- name: production-pdf-mail-assets-workflows
  repo: plg-platform-backend
  targets:
    - ../../plg-platform-backend/.github/workflows/production.yml
    - ../../plg-platform-backend/.github/workflows/deploy-on-pr-merge.yml
  hot_area: production deploy asset inclusion
  depends_on: [production-pdf-mail-assets-source]
  slice_mode: minimal-change
  surface_policy: required
  minimum_valid_completion: both production deploy paths explicitly transfer and validate the tracked PDF and mail assets
  validated_noop_allowed: false
  acceptable_evidence:
    - YAML/shell validation passes
    - git diff --check passes
```

## Test Plan

- [@test] ../../plg-platform-backend/src/tests/Feature/DiagnosticClassCloseEmailDispatchOnUpdateTest.php

## Verification Matrix

```yaml
- name: spec-review
  level: custom
  command: python3 ./flow workspace exec -- python3 ./flow spec review specs/features/plg/2026-09-11-production-pdf-mail-assets-deploy.spec.md --json
  blocking_on: [approval]
  environments: [local]

- name: workflow-contract
  level: custom
  command: git diff --check -- plg-platform-backend/.github/workflows/production.yml plg-platform-backend/.github/workflows/deploy-on-pr-merge.yml
  blocking_on: [ci]
  environments: [local]

- name: source-assets
  level: integration
  command: test -s plg-platform-backend/src/storage/app/public/pdf_assets/membrete_page.png && test -s plg-platform-backend/src/storage/app/public/mail_assets/mail-bg3.png
  blocking_on: [ci]
  environments: [local]

- name: production-deploy-and-pdf
  level: integration
  command: gh run watch production-run-id --repo PLGEducation/plg-platform-backend --exit-status
  blocking_on: [ci]
  environments: [production]
```
