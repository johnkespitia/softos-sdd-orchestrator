---
schema_version: 3
name: "Diagnostic class HR attendance correction"
description: "Allow HR to correct diagnostic-class candidate attendance after closure while preserving entry-report availability."
status: approved
owner: platform
single_slice_reason: "Small cross-surface contract with an existing backend endpoint and one dashboard form."
multi_domain: false
phases: []
depends_on:
  - specs/000-foundation/spec-as-source-operating-model.spec.md
  - specs/000-foundation/repo-routing-and-worktree-orchestration.spec.md
  - specs/000-foundation/dashboard-frontend-coding-style-and-quality-contract.spec.md
  - specs/000-foundation/plg-platform-backend-coding-style-and-quality-contract.spec.md
required_runtimes:
  - node-npm-react-cra
  - php-laravel8-apache
required_services: []
required_capabilities:
  - react-cra
  - laravel8
stack_projects: []
stack_services: []
stack_capabilities: []
targets:
  - ../../specs/features/plg/2026-09-11-diagnostic-class-hr-attendance-correction.spec.md
  - ../../dashboard-frontend/src/src/pages/DiagnosticClass/Form.jsx
  - ../../dashboard-frontend/src/src/pages/DiagnosticClass/List.jsx
  - ../../plg-platform-backend/src/app/Http/Controllers/DiagnosticClassController.php
  - ../../plg-platform-backend/src/tests/Feature/DiagnosticClassNoShowDiscountTest.php
test_refs:
  - ../../dashboard-frontend/src/src/pages/DiagnosticClass/DiagnosticClassAssignment.test.jsx
  - ../../plg-platform-backend/src/tests/Feature/DiagnosticClassNoShowDiscountTest.php
---

# Diagnostic class HR attendance correction

## Objective

Allow an authorized HR operator to change `candidate_attended` for a diagnostic
class from the existing diagnostic-class edit flow, including after the class
is closed. A closed class must continue to expose its existing entry-report PDF
download when its current PDF prerequisites are satisfied.

## Current contract

The backend already validates and persists `candidate_attended` on the HR
`PUT /api/hr-management/diagnostic-class/{diagClass}` route. The existing PDF
route requires a closed class, final feedback, and a complete professor profile;
it does not require candidate attendance to be true. This feature adds the
missing HR form control and preserves those backend contracts.

## Scope

- Add a boolean attendance control to the HR diagnostic-class edit form.
- Initialize it from the API value and include it in the existing update payload.
- Make the control usable for open and closed classes.
- Preserve the existing list status rendering and closed-class PDF action.
- Add or retain focused evidence for the existing HR update and PDF contracts.

## Out of scope

- New database columns, routes, permissions, or API payload names.
- Changes to professor-app attendance authority.
- Recalculation or reversal of historical no-show pricing.
- Changes to email, webhook, report-generation, or scheduling services.

## Invariants

- Only the existing HR permission-protected update route persists the correction.
- `candidate_attended` remains a boolean in API payloads and responses.
- Closing a class remains independent from the HR attendance correction.
- PDF availability remains governed by `class_closed`, feedback, and professor
  profile completeness, not by attendance truth value.
- Existing unrelated working-tree changes remain outside this slice.

## Acceptance criteria

1. HR sees the current attendance state when editing a diagnostic class.
2. HR can set attended or absent and save it for an already closed class.
3. The updated state is reflected in the diagnostic-class list after refresh.
4. A qualifying closed class still exposes and generates its entry-report PDF.
5. Existing focused frontend and backend tests pass, and `git diff --check`
   is clean for the authorized product files.

## Slice Breakdown

```yaml
- name: diagnostic-class-hr-attendance
  repo: dashboard-frontend
  targets:
    - ../../dashboard-frontend/src/src/pages/DiagnosticClass/Form.jsx
    - ../../dashboard-frontend/src/src/pages/DiagnosticClass/List.jsx
  hot_area: HR diagnostic class edit form
  depends_on: []
  slice_mode: minimal-change
  surface_policy: required
  minimum_valid_completion: attendance control initializes from API data and is sent through the existing HR update flow for open and closed classes
  validated_noop_allowed: false
  acceptable_evidence:
    - focused diagnostic dashboard tests pass
    - staging dashboard workflow and smoke check pass
    - git diff --check passes

- name: diagnostic-class-hr-attendance-backend-contract
  repo: plg-platform-backend
  targets:
    - ../../plg-platform-backend/src/app/Http/Controllers/DiagnosticClassController.php
    - ../../plg-platform-backend/src/tests/Feature/DiagnosticClassNoShowDiscountTest.php
  hot_area: existing HR attendance update and PDF contract
  depends_on: [diagnostic-class-hr-attendance]
  slice_mode: verification-only
  surface_policy: forbidden
  minimum_valid_completion: existing backend route and PDF prerequisites are verified without backend surface expansion
  validated_noop_allowed: true
  acceptable_evidence:
    - focused PHPUnit tests pass
    - no unauthorized backend diff

- name: diagnostic-class-hr-attendance-governance
  repo: plg-platform-harness
  targets:
    - ../../specs/features/plg/2026-09-11-diagnostic-class-hr-attendance-correction.spec.md
  hot_area: feature evidence and release traceability
  depends_on: [diagnostic-class-hr-attendance-backend-contract]
  slice_mode: verification-only
  surface_policy: forbidden
  minimum_valid_completion: canonical spec review, plan, verification evidence, independent review, and staging run are recorded
  validated_noop_allowed: false
  acceptable_evidence:
    - spec review and spec CI pass
    - independent read-only review passes
    - staging workflow succeeds
```

## Verification Matrix

```yaml
- name: spec-review
  level: custom
  command: python3 ./flow workspace exec -- python3 ./flow spec review specs/features/plg/2026-09-11-diagnostic-class-hr-attendance-correction.spec.md --json
  blocking_on: [approval]
  environments: [local]

- name: spec-ci
  level: custom
  command: python3 ./flow workspace exec -- python3 ./flow ci spec specs/features/plg/2026-09-11-diagnostic-class-hr-attendance-correction.spec.md --json
  blocking_on: [ci]
  environments: [local]

- name: dashboard-tests
  level: integration
  command: python3 ./flow repo exec dashboard-frontend -- npm --prefix src test -- --watchAll=false --runInBand src/src/pages/DiagnosticClass/DiagnosticClassAssignment.test.jsx
  blocking_on: [ci]
  environments: [local]

- name: backend-tests
  level: integration
  command: python3 ./flow repo exec plg-platform-backend -- php -d memory_limit=512M src/vendor/bin/phpunit -c src/phpunit.xml src/tests/Feature/DiagnosticClassNoShowDiscountTest.php
  blocking_on: [ci]
  environments: [local]

- name: staging-dashboard
  level: smoke
  command: gh run watch 34606522036 --repo PLGEducation/dashboard-frontend --exit-status
  blocking_on: [release]
  environments: [staging]
```

## Test Plan

- [@test] ../../dashboard-frontend/src/src/pages/DiagnosticClass/DiagnosticClassAssignment.test.jsx
- [@test] ../../plg-platform-backend/src/tests/Feature/DiagnosticClassNoShowDiscountTest.php
