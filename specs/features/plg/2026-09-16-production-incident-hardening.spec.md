---
schema_version: 3
name: "Production incident hardening 2026-09-16"
description: "Retrospective governance record for the backend-only fixes deployed to staging and production after the September 2026 Laravel incident."
status: approved
owner: platform
slice_mode: verification-only
surface_policy: required
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
targets:
  - ../../specs/features/plg/2026-09-16-production-incident-hardening.spec.md
  - ../../plg-platform-backend/.github/workflows/staging.yml
  - ../../plg-platform-backend/.github/workflows/production.yml
  - ../../plg-platform-backend/scripts/deploy/build_deploy_env_patch.sh
  - ../../plg-platform-backend/src/app/Http/Controllers/QueueController.php
  - ../../plg-platform-backend/src/app/Jobs/ProvisionClassroomForPlanJob.php
  - ../../plg-platform-backend/src/app/Jobs/ProvisionClassroomForStudentJob.php
  - ../../plg-platform-backend/src/app/Jobs/ReconcileClassroomPlanAssignmentJob.php
  - ../../plg-platform-backend/src/app/Jobs/ReconcileClassroomPlanTeachersJob.php
  - ../../plg-platform-backend/src/app/Jobs/ReconcileMeetConferenceSessionsJob.php
  - ../../plg-platform-backend/src/app/Services/GoogleWorkspace/Calendar/GooglePlanCalendarSyncService.php
  - ../../plg-platform-backend/src/app/Services/GoogleWorkspace/Classroom/GoogleClassroomPlanProvisioningService.php
  - ../../plg-platform-backend/src/app/Services/GoogleWorkspace/GoogleWorkspaceEventsRestClient.php
  - ../../plg-platform-backend/src/scripts/deploy/ensure_google_workspace_env.sh
  - ../../plg-platform-backend/src/tests/Feature/GoogleMeetReconciliationQueueTest.php
test_refs:
  - ../../plg-platform-backend/src/tests/Feature/GoogleCalendarPlanSyncTest.php
  - ../../plg-platform-backend/src/tests/Feature/GoogleClassroomPlanProvisioningTest.php
  - ../../plg-platform-backend/src/tests/Feature/GoogleMeetReconciliationQueueTest.php
  - ../../plg-platform-backend/src/tests/Unit/Scheduling/ConflictValidationServiceTest.php
---

# Production incident hardening 2026-09-16

## Objective

Close the governance record for the backend-only incident fixes deployed from
commit `12254adb5345c77dbb605306890e585132a58644`, without expanding scope to
the harness, dashboard, hub, schema, or unrelated product work.

## Observed incident clusters

- Laravel queue compatibility: old serialized Meet reconciliation jobs could
  access an uninitialized typed property.
- Google Classroom resilience: malformed/null Google error arrays and transient
  503 responses were not handled consistently.
- Google Calendar reconciliation: stale event IDs could mark an entire plan
  calendar as failed instead of recreating the missing event.
- Deployment safety: Google credential paths and notification configuration were
  not validated before remote deployment.
- Queue operations: retry requests for already-removed failed jobs produced an
  error-level log despite being an expected race.

## Scope

- Preserve legacy serialized job compatibility with a nullable checkpoint
  default.
- Make Classroom error extraction null-safe and add bounded transient backoff.
- Recreate a Calendar event once when its persisted Google event ID returns
  `404 not found`.
- Preserve Google Workspace Events response details for diagnosis.
- Validate credential JSON/readability and email notification configuration in
  deployment scripts.
- Record staging and production evidence for the exact backend SHA.

## Explicit exclusions

- No harness/root runtime implementation changes are part of this release.
- No database migrations, schema hardening, seeders, or data repair are included.
- No automatic resolution of stale Classroom IDs, duplicate Classroom courses,
  transcript source changes, invalid scheduling records, or missing Toolyx URLs.
- No change to Google Workspace permissions, Domain-Wide Delegation, service
  account files, or provider-side authorization policy.
- No frontend changes and no additional repositories are deployable from this
  manifest.

## Invariants and stop conditions

1. The deployable source is exactly backend commit `12254adb...`.
2. The release manifest contains only `plg-platform-backend`.
3. Staging and production must reject unreadable or invalid Google credentials.
4. Existing Google and queue behavior remains idempotent on retries.
5. No migration is enabled unless the production workflow explicitly requests
   it; production used the existing migration path and staging used `false`.
6. Manual operational items remain documented rather than silently repaired.

## Slice Breakdown

```yaml
- name: incident-backend-hardening
  repo: plg-platform-backend
  hot_area: production incident runtime hardening
  targets:
    - ../../plg-platform-backend/.github/workflows/staging.yml
    - ../../plg-platform-backend/.github/workflows/production.yml
    - ../../plg-platform-backend/scripts/deploy/build_deploy_env_patch.sh
    - ../../plg-platform-backend/src/app/Http/Controllers/QueueController.php
    - ../../plg-platform-backend/src/app/Jobs/ProvisionClassroomForPlanJob.php
    - ../../plg-platform-backend/src/app/Jobs/ProvisionClassroomForStudentJob.php
    - ../../plg-platform-backend/src/app/Jobs/ReconcileClassroomPlanAssignmentJob.php
    - ../../plg-platform-backend/src/app/Jobs/ReconcileClassroomPlanTeachersJob.php
    - ../../plg-platform-backend/src/app/Jobs/ReconcileMeetConferenceSessionsJob.php
    - ../../plg-platform-backend/src/app/Services/GoogleWorkspace/Calendar/GooglePlanCalendarSyncService.php
    - ../../plg-platform-backend/src/app/Services/GoogleWorkspace/Classroom/GoogleClassroomPlanProvisioningService.php
    - ../../plg-platform-backend/src/app/Services/GoogleWorkspace/GoogleWorkspaceEventsRestClient.php
    - ../../plg-platform-backend/src/scripts/deploy/ensure_google_workspace_env.sh
  slice_mode: verification-only
  surface_policy: forbidden
  minimum_valid_completion: exact backend SHA is committed, deployed, and independently verifiable in staging and production
  validated_noop_allowed: false
  acceptable_evidence:
    - focused PHPUnit evidence
    - successful staging and production workflow runs
    - release verification with required pipelines

- name: governance-closeout
  repo: plg-platform-harness
  hot_area: release traceability and evidence closure
  targets:
    - ../../specs/features/plg/2026-09-16-production-incident-hardening.spec.md
  slice_mode: verification-only
  surface_policy: forbidden
  minimum_valid_completion: release manifest, evidence paths, failed-attempt history, and residual operational debt are recorded without changing deployed code
  validated_noop_allowed: false
  acceptable_evidence:
    - spec review and CI pass
    - manifest references only the backend repository
    - production verification is passed

- name: operational-debt-record
  repo: plg-platform-harness
  hot_area: residual production incident actions
  targets:
    - ../../specs/features/plg/2026-09-16-production-incident-hardening.spec.md
  slice_mode: verification-only
  surface_policy: forbidden
  minimum_valid_completion: residual manual actions are enumerated with owners or explicit operator follow-up and no automatic data repair is implied
  validated_noop_allowed: true
  acceptable_evidence:
    - residual operational actions section
    - release verification has no unresolved deployment findings
```

## Evidence package

- Backend commit and remote branch:
  `fix/2026-09-16-production-incident-hardening` /
  `12254adb5345c77dbb605306890e585132a58644`.
- Focused PHPUnit evidence:
  - Calendar: 30 tests, 82 assertions, passed.
  - Classroom: 30 tests, 90 assertions, passed.
  - Meet reconciliation: 5 tests, 16 assertions, passed.
- Shell validation: `git diff --check` and deploy script `bash -n` passed.
- Staging workflow: run `35155358650`, passed.
- Production workflow: run `35155599331`, passed.
- Release verification artifacts:
  - `releases/promotions/2026.09.16-production-incident-hardening-staging-verification.json`
  - `releases/promotions/2026.09.16-production-incident-hardening-production-verification.json`

The scheduling unit suite was attempted but could not initialize because the
test database `cerrajero_db_test` had no `users` table. This is recorded as an
environment limitation, not as a passing test claim.

## Acceptance criteria

1. The manifest and verification artifacts identify only the backend SHA above.
2. The successful staging and production workflow runs are linked by run ID and
   report zero non-passing checks.
3. The backend working tree is clean after the release commit.
4. The known failed deploy attempts remain distinguishable from the successful
   runs and do not determine release status.
5. Residual manual actions are explicitly listed and do not imply unverified
   automatic data repair.

## Residual operational actions

- Configure Toolyx webhook URLs when the integration is required.
- Review duplicate active Classroom courses and stale/mock course IDs manually.
- Review transcript source-hash changes with the existing professor approval
  guard.
- Investigate the historical intermittent MariaDB connectivity warnings if they
  recur.

## Test References

- [@test] ../../plg-platform-backend/src/tests/Feature/GoogleCalendarPlanSyncTest.php
- [@test] ../../plg-platform-backend/src/tests/Feature/GoogleClassroomPlanProvisioningTest.php
- [@test] ../../plg-platform-backend/src/tests/Feature/GoogleMeetReconciliationQueueTest.php
- [@test] ../../plg-platform-backend/src/tests/Unit/Scheduling/ConflictValidationServiceTest.php

## Verification Matrix

```yaml
- name: backend-focused-tests
  level: integration
  command: docker compose -f plg-platform-backend/docker-compose.yaml exec -T web-server php -d memory_limit=512M vendor/bin/phpunit -c phpunit.xml tests/Feature/GoogleCalendarPlanSyncTest.php tests/Feature/GoogleClassroomPlanProvisioningTest.php tests/Feature/GoogleMeetReconciliationQueueTest.php
  blocking_on: [ci, release]
  environments: [local]

- name: staging-deploy
  level: integration
  command: gh run watch 35155358650 --repo PLGEducation/plg-platform-backend --exit-status
  blocking_on: [release]
  environments: [staging]

- name: production-deploy
  level: integration
  command: gh run watch 35155599331 --repo PLGEducation/plg-platform-backend --exit-status
  blocking_on: [release]
  environments: [production]

- name: release-verification
  level: custom
  command: python3 ./flow release verify --version 2026.09.16-production-incident-hardening --env production --require-pipelines --json
  blocking_on: [release]
  environments: [production]
```
