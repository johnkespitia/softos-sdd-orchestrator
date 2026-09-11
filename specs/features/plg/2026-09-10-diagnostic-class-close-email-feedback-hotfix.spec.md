---
schema_version: 3
name: "Diagnostic class close email feedback hotfix"
description: "Ensure adding final feedback to a closed diagnostic class dispatches the existing close side effects so the owner close email and PDF path run, assuming SMTP and queues are healthy."
status: approved
owner: platform
single_slice_reason: "Narrow backend hotfix over an existing controller side-effect predicate plus focused regression coverage."
multi_domain: false
phases: []
depends_on:
  - specs/000-foundation/spec-as-source-operating-model.spec.md
  - specs/000-foundation/spec-driven-delivery-and-infrastructure.spec.md
  - specs/000-foundation/repo-routing-and-worktree-orchestration.spec.md
  - specs/000-foundation/plg-platform-backend-foundation-alignment.spec.md
  - specs/000-foundation/plg-platform-backend-coding-style-and-quality-contract.spec.md
required_runtimes:
  - php-laravel8-apache
required_services: []
required_capabilities:
  - laravel8
stack_projects: []
stack_services: []
stack_capabilities: []
targets:
  - ../../specs/features/plg/2026-09-10-diagnostic-class-close-email-feedback-hotfix.spec.md
  - ../../plg-platform-backend/src/app/Http/Controllers/DiagnosticClassController.php
  - ../../plg-platform-backend/src/app/Services/DiagnosticClassCloseNotificationService.php
  - ../../plg-platform-backend/src/app/Services/Actions/Publish/ProfessorDiagnosticClassClosePublishService.php
  - ../../plg-platform-backend/src/app/Services/Actions/Publish/ProfessorEntryReportPublishService.php
  - ../../plg-platform-backend/src/tests/Feature/DiagnosticClassCloseNotificationTest.php
  - ../../plg-platform-backend/src/tests/Feature/DiagnosticClassCloseEmailDispatchOnUpdateTest.php
test_refs:
  - ../../plg-platform-backend/src/tests/Feature/DiagnosticClassCloseEmailDispatchOnUpdateTest.php
  - ../../plg-platform-backend/src/tests/Feature/DiagnosticClassCloseNotificationTest.php
---

# Diagnostic class close email feedback hotfix

## Objective

When a diagnostic class is already closed and a professor/admin adds or updates `final_feedback`, the backend must dispatch the existing diagnostic close side effects so the owner close email path runs. This hotfix assumes SMTP and queues are healthy and validates the application-level dispatch condition.

## Context

The close email is sent by `DiagnosticClassCloseNotificationService::dispatch()`. The legacy update path in `DiagnosticClassController::update()` dispatches that service only when the class is closed, `owner` is present, and the saved model reports a relevant change.

The existing Professor Actions `entry-report` path is intentionally feedback-only. It writes final feedback and preserves `class_closed`; it must not generate PDFs, emails, or webhooks. The diagnostic-class close flow and legacy closed-class update path are the surfaces that may dispatch close side effects.

## Problem

Adding feedback to an already closed diagnostic class can leave the owner close email unsent if the update path does not recognize `final_feedback` as a relevant saved change and therefore does not call `DiagnosticClassCloseNotificationService::dispatch()`.

## Scope

Includes:

- Preserve the existing `DiagnosticClassCloseNotificationService` email/PDF dispatch path.
- Ensure the update predicate checks both `class_closed` and `final_feedback` as relevant side-effect fields.
- Add focused backend coverage for:
  - adding feedback to an already closed diagnostic class dispatches close notifications;
  - closing with feedback dispatches close notifications;
  - unrelated updates on a closed class do not dispatch close notifications.

Out of scope:

- SMTP, mail transport, queue worker, queue connection, cron, or infrastructure changes.
- New routes, frontend changes, migrations, or dependency changes.
- Changing `entry-report` semantics; it remains feedback-only.
- Broad temporal projection rollout beyond this close-email side-effect predicate.

## Invariants

- A closed diagnostic class with valid `owner` and changed `final_feedback` must call `DiagnosticClassCloseNotificationService::dispatch()`.
- A diagnostic class changing from open to closed must continue to call `DiagnosticClassCloseNotificationService::dispatch()` when `owner` is present.
- Updating unrelated fields on an already closed diagnostic class must not resend the close email.
- `ProfessorEntryReportPublishService` must remain feedback-only: no close, no PDF, no email, no webhook.
- No schema hardening or rollout-sensitive migrations are involved.

## Slice Breakdown

```yaml
- name: backend-close-email-feedback-hotfix
  repo: plg-platform-backend
  targets:
    - ../../plg-platform-backend/src/app/Http/Controllers/DiagnosticClassController.php
    - ../../plg-platform-backend/src/app/Services/DiagnosticClassCloseNotificationService.php
    - ../../plg-platform-backend/src/app/Services/Actions/Publish/ProfessorDiagnosticClassClosePublishService.php
    - ../../plg-platform-backend/src/app/Services/Actions/Publish/ProfessorEntryReportPublishService.php
    - ../../plg-platform-backend/src/tests/Feature/DiagnosticClassCloseNotificationTest.php
    - ../../plg-platform-backend/src/tests/Feature/DiagnosticClassCloseEmailDispatchOnUpdateTest.php
  hot_area: diagnostic class close email side-effect predicate
  depends_on: []
  slice_mode: minimal-change
  surface_policy: required
  minimum_valid_completion: focused regression coverage proves final_feedback changes on closed diagnostic classes dispatch close notifications without changing entry-report semantics
  validated_noop_allowed: false
  acceptable_evidence:
    - phpunit DiagnosticClassCloseEmailDispatchOnUpdateTest passes
    - phpunit DiagnosticClassCloseNotificationTest passes
    - git diff --check passes for target files
```

## Test Plan

- [@test] ../../plg-platform-backend/src/tests/Feature/DiagnosticClassCloseEmailDispatchOnUpdateTest.php
- [@test] ../../plg-platform-backend/src/tests/Feature/DiagnosticClassCloseNotificationTest.php

## Verification Matrix

```yaml
- name: spec-review
  level: custom
  command: python3 ./flow workspace exec -- python3 ./flow spec review specs/features/plg/2026-09-10-diagnostic-class-close-email-feedback-hotfix.spec.md --json
  blocking_on: [approval]
  environments: [local]
  notes: validates SoftOS spec shape and target routing

- name: spec-ci
  level: custom
  command: python3 ./flow workspace exec -- python3 ./flow ci spec specs/features/plg/2026-09-10-diagnostic-class-close-email-feedback-hotfix.spec.md --json
  blocking_on: [ci]
  environments: [local]
  notes: canonical feature spec CI

- name: backend-close-email-feedback
  level: integration
  command: python3 ./flow repo exec plg-platform-backend -- php -d memory_limit=512M src/vendor/bin/phpunit -c src/phpunit.xml src/tests/Feature/DiagnosticClassCloseEmailDispatchOnUpdateTest.php
  blocking_on: [ci]
  environments: [local]
  notes: proves update-side dispatch cases

- name: backend-close-notification-service
  level: integration
  command: python3 ./flow repo exec plg-platform-backend -- php -d memory_limit=512M src/vendor/bin/phpunit -c src/phpunit.xml src/tests/Feature/DiagnosticClassCloseNotificationTest.php
  blocking_on: [ci]
  environments: [local]
  notes: proves existing email/PDF service behavior remains intact
```

## Acceptance Criteria

1. The backend dispatches close notifications when `final_feedback` is added to an already closed diagnostic class with `owner`.
2. The backend dispatches close notifications when a diagnostic class is closed with feedback and `owner`.
3. The backend does not dispatch close notifications for unrelated closed-class updates.
4. The existing close notification service tests remain green.
5. Staging promotion uses a release manifest that includes a committed source ref for this hotfix and its regression test.
