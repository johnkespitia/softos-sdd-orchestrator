---
schema_version: 3
name: "Diagnostic class reminder scheduler"
description: "Canonicalize the already-implemented Laravel scheduler path that sends diagnostic-class candidate webhooks and professor reminder emails with idempotent per-channel buckets, legacy HTTP parity, and no SMTP/cron infrastructure changes."
status: approved
owner: platform
single_slice_reason: ""
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
  - ../../specs/features/plg/2026-09-10-diagnostic-class-reminder-scheduler.spec.md
  - ../../plg-platform-backend/src/app/Console/Kernel.php
  - ../../plg-platform-backend/src/app/Console/Commands/SendDiagnosticClassReminders.php
  - ../../plg-platform-backend/src/app/Services/DiagnosticClassReminderService.php
  - ../../plg-platform-backend/src/app/Http/Controllers/DiagnosticClassController.php
  - ../../plg-platform-backend/src/routes/api.php
  - ../../plg-platform-backend/src/app/Services/MailService.php
  - ../../plg-platform-backend/src/app/Services/WebhookStudentNotificationService.php
  - ../../plg-platform-backend/src/app/Support/TransactionalEmailComposer.php
  - ../../plg-platform-backend/src/resources/views/email/diagnostic-class-reminder-professor.blade.php
  - ../../plg-platform-backend/src/tests/Feature/DiagnosticClassReminderCommandTest.php
  - ../../plg-platform-backend/src/tests/Feature/HubNotificationSchedulerTest.php
---

# Diagnostic class reminder scheduler

## Objective

Make the already-implemented diagnostic-class reminder path a SoftOS-governed contract so production `php artisan schedule:run` reliably sends candidate webhook reminders and professor reminder emails ~60 minutes before start, without duplicate sends in the same reminder bucket, while preserving legacy `GET /api/send-entry-notification` auth/status/`body` parity.

This spec documents and locks existing backend behavior. It does not invent new product UI, migrations, SMTP providers, or host cron wiring.

## Context

Production operators already run Laravel's scheduler on a minute tick (example production pattern: `php artisan schedule:run` appended to `storage/logs/scheduler.log`). Regular class reminders and queue batch processors were already registered in `App\Console\Kernel`. Diagnostic-class reminders historically lived only behind the legacy HTTP endpoint `/api/send-entry-notification`, so `schedule:run` did not generate diagnostic reminder work unless that HTTP path was called separately.

Current backend reality (implementation already present):

| Surface | Role |
| --- | --- |
| `notifications:send-diagnostic-class-reminders` | Artisan command entrypoint |
| `DiagnosticClassReminderService::send` | Eligibility, idempotency, candidate webhook, professor email |
| `Kernel::schedule` | Registers the command every five minutes with `--minutes=60` |
| `DiagnosticClassController::sendUpcomingClassNotifications` | Legacy HTTP trigger that reuses the same service |
| `MailService::send` | Queues professor mail on the `emails` queue |
| `queue:process-cron-batch --queue=default,emails` | Existing scheduler path that drains queued mail |

## Foundations Aplicables

- `specs/000-foundation/spec-as-source-operating-model.spec.md`: this file is the canonical behavior contract; `.flow/**` is evidence only.
- `specs/000-foundation/spec-driven-delivery-and-infrastructure.spec.md`: verification uses `flow ci` / repo runtime PHPUnit evidence.
- `specs/000-foundation/repo-routing-and-worktree-orchestration.spec.md`: changes stay inside `plg-platform-backend` targets routed from this root spec.
- `specs/000-foundation/plg-platform-backend-foundation-alignment.spec.md`: Laravel 8 app root remains `src/`.
- `specs/000-foundation/plg-platform-backend-coding-style-and-quality-contract.spec.md`: PHPUnit feature tests under `src/tests/Feature` are the local proof surface.

Runtime / capability / skill governance for `php-laravel8-apache` + Laravel 8 is **not** declared as a SoftOS `depends_on` here. Those constraints are already enforced by committed workspace routing (`workspace.config.json` → repo runtime / capability refs), `required_runtimes` / `required_capabilities` on this spec, and `plg-platform-backend/AGENTS.md` plus the Laravel 8 skill pack. A draft foundation spec for runtime-capability-skill governance is intentionally omitted so this feature can release from committed HEAD without waiting on an uncommitted foundation draft.

## Domains Aplicables

No dedicated `specs/domains/**` vocabulary exists for diagnostic-class reminders. Product terms used here (`DiagnosticClass`, candidate webhook, professor transactional email, reminder bucket) are defined by this feature spec and by the existing Laravel models/services. Domain omission is intentional, not accidental. Broader platform temporal/DTO domain vocabulary (when introduced elsewhere) does not gate this reminder scheduler contract.

## Related Feature Dependency

No SoftOS `depends_on` edge to a sibling temporal-projection feature. Broader backend-owned timezone DTO / `viewer_*` projection work is explicitly **out of scope** for this reminder scheduler and is not required for release of this contract.

This spec still owns a **reminder-local** timezone projection rule: candidate webhook and professor email must each project the class instant with independent `copy()->setTimezone(...)` (no mutable Carbon collapse shared across channels). That local invariant is complete for diagnostic reminders and must not wait on a wider temporal-projection program.

## Problem To Solve

Without a scheduler-registered diagnostic reminder command:

1. Operators who only run `schedule:run` never enqueue diagnostic candidate/professor reminders.
2. Relying solely on `/api/send-entry-notification` couples reminder delivery to an external HTTP cron caller and API key.
3. Repeated ticks in a five-minute schedule must not duplicate candidate webhooks or professor emails for the same class/minutes/channel bucket.
4. A failed candidate webhook must not block the professor email (and vice versa) for the same class or later eligible classes.
5. The legacy HTTP endpoint must remain usable for operators who still call it, with compatible response shape.

## Scope

Exact inclusions:

1. Laravel schedule registration for `notifications:send-diagnostic-class-reminders --minutes=60`.
2. Artisan command contract, exit codes, and structured logging.
3. `DiagnosticClassReminderService` eligibility window, channel isolation, cache idempotency, and retry-after-failure semantics.
4. Candidate webhook side effect via `WebhookStudentNotificationService`.
5. Professor email side effect via `MailService` → `SendEmailJob` on queue `emails`.
6. Legacy `GET /api/send-entry-notification` auth, rate/concurrency locks, status codes, `body` list parity, and additive `summary` metadata.
7. Focused PHPUnit coverage that locks the contracts above.
8. Documentation of timezone projection rules used by this reminder path only.

## Out Of Scope

Exact exclusions:

- New database migrations, schema changes, or candidate migration activation.
- Frontend/UI/Hub dashboard changes of any kind.
- SMTP provider, mail transport, or host crontab/infrastructure changes.
- Changes to regular-class reminder commands (`notifications:send-class-reminders`) beyond requiring they remain registered.
- Hub notification scheduler/push runner redesign (`hub:notifications:*`).
- Changing `queue:process-cron-batch` cadence or queue names.
- Broader temporal DTO/`viewer_*` rollout owned by the sibling temporal-projection spec.
- OpenAPI expansion unless a future approved slice explicitly adds it.
- Commit, push, merge, release, or publish actions.

## Affected Repos / Surfaces

| Repo | Surfaces |
| --- | --- |
| `plg-platform-harness` | This spec only |
| `plg-platform-backend` | Console Kernel/command, reminder service, legacy controller method/route, mail/webhook collaborators, feature tests |

No `dashboard-frontend` or `hub-frontend` targets.

## Governing Decision

Diagnostic-class reminders are backend-owned and scheduler-first.

| Decision | Contract |
| --- | --- |
| Primary trigger | Laravel scheduler every five minutes runs `notifications:send-diagnostic-class-reminders --minutes=60`. |
| Shared implementation | Command and legacy HTTP endpoint both call `DiagnosticClassReminderService::send`. |
| Default lead time | 60 minutes before class start (UTC instant derived from stored `starting_date` + `starting_time`). |
| Schedule overlap guard | Scheduler entry uses `withoutOverlapping()` and `runInBackground()`. |
| Idempotency unit | Per diagnostic class id + minutes bucket + channel (`candidate` or `professor`). |
| Professor delivery | Asynchronous job on queue `emails` (not synchronous SMTP inside the reminder process). |
| Candidate delivery | Synchronous HTTP POST to configured student notification webhook URL. |
| Partial failure policy | Channel/class failures are recorded; remaining work continues; command exits success unless a top-level uncaught failure occurs. |
| Legacy HTTP | Retained with auth/status/`body` parity and additive `summary`. |

Prohibited alternatives:

- Do not remove the scheduler entry and rely only on HTTP.
- Do not send professor mail synchronously outside the existing `emails` queue path.
- Do not use a single global lock that skips all remaining eligible classes after one channel failure.
- Do not change host cron to call only the HTTP endpoint as the primary path.
- Do not invent migrations/UI to “complete” this feature.

## Exact Behavior And Invariants

### Eligibility query

`DiagnosticClassReminderService::send($minutes)` must:

1. Clamp `$minutes = max(1, $minutes)`.
2. Compute UTC `now`.
3. Compute `windowFloor = max(0, $minutes - SCHEDULE_WINDOW_MINUTES)` where `SCHEDULE_WINDOW_MINUTES = 5`.
4. Load diagnostic classes where:
   - `class_closed = false`
   - `candidate_attended = false`
   - `starting_date` is between `now+windowFloor` and `now+$minutes` (date strings `Y-m-d`)
   - eager-load `professor.user`
5. For each row, parse `starting_date` + first five chars of `starting_time` as `Y-m-d H:i` in timezone `UTC`.
6. Keep a class only when `windowFloor < minutesUntilClass <= $minutes` (using signed `diffInMinutes` against the UTC class instant).
7. Count `classes_found` as the number of classes that pass the minute-bucket filter (not merely the SQL date window).

### Return shape

```php
[
  'classes_found' => int,
  'notifications_sent' => int,      // successful candidate webhook sends in this run
  'professor_emails_sent' => int,   // successful professor queue dispatches in this run
  'errors' => [
    [
      'diagnostic_class_id' => int|null,
      'channel' => 'datetime'|'candidate'|'professor',
      'error' => string,
    ],
    // ...
  ],
  'classes' => Collection<DiagnosticClass>, // eligible classes only
]
```

### Channel invariants

| Invariant | Required behavior |
| --- | --- |
| Candidate without duplicate | Cache key `diagnostic-class-reminder:{id}:{minutes}:candidate` must be acquired with `Cache::add` before webhook send. |
| Professor without duplicate | Cache key `diagnostic-class-reminder:{id}:{minutes}:professor` must be acquired with `Cache::add` before mail dispatch. |
| TTL | `max($minutes, 5) * 60` seconds. |
| Retry after failure | On channel exception (or professor send returning false after lock), forget the channel cache key so a later tick can retry. |
| Missing professor | Skip professor channel quietly (`false`); do not invent a professor. |
| Independent channels | Candidate failure must not prevent professor attempt for the same class; professor failure must not prevent later classes. |
| Datetime parse failure | Record `channel=datetime` error and continue the batch. |
| Empty date/time | Skip class without counting it eligible and without error entry. |

### Candidate webhook payload (observable)

Webhook payload must include at least:

- `title`: `Tu clase de diagnóstico en PLG comenzará pronto`
- `message`: approx-1-hour Spanish copy pointing candidates to Hub
- `email`: `candidate_email`
- `additional_data.class_*` projected into candidate timezone
- `additional_data.class_timezone`
- `additional_data.candidate_name` / `candidate_email`
- `additional_data.professor_name` or `No asignado`
- `additional_data.class_id`
- `additional_data.hub_url` / `target_url` = Hub product login URL from `V2ProductFrontendResolver`

Non-success webhook HTTP responses must throw and be recorded as `channel=candidate` errors after releasing the cache lock.

### Professor email side effect (observable)

Professor reminder must:

1. Resolve professor timezone via `TimezoneHelper::getUserTimezone($user, 'America/Bogota')`, validating with `TimezoneHelper::isValidTimezone` and falling back to `America/Bogota`.
2. Project class instant with `$classDateTime->copy()->setTimezone($professorTimezone)` (no mutable collapse shared with candidate).
3. Clone the model only for template display fields `starting_date` / `starting_time`.
4. Compose localized content via `TransactionalEmailComposer::diagnosticReminderProfessorMail`.
5. Call `MailService::send` with template `email.diagnostic-class-reminder-professor`.
6. Resulting job must be pushed to queue name `emails` (`SendEmailJob`).

`MailService` development allow-list behavior remains unchanged: blocked recipients may return `true` without dispatch; reminder service treats that as a successful professor channel completion for that run.

## Command Contract

| Field | Contract |
| --- | --- |
| Signature | `notifications:send-diagnostic-class-reminders {--minutes=60}` |
| Minutes clamp | `max(1, (int) option)` |
| Success exit | `Command::SUCCESS` (0) when service returns, including partial `errors` |
| Failure exit | `Command::FAILURE` only for top-level throwable outside service-handled channel errors |
| stdout | Includes `classes_found`, `notifications_sent`, `professor_emails_sent`, `errors=<count>`; warns with JSON errors when count > 0 |
| Logging | Datadog info on success path; error log on top-level failure |

## Scheduler Contract

`App\Console\Kernel::schedule` must register:

```text
notifications:send-diagnostic-class-reminders --minutes=60
  ->everyFiveMinutes()
  ->withoutOverlapping()
  ->runInBackground()
```

Required coexistence (must remain registered; not redesigned by this spec):

- `notifications:send-class-reminders` (default and `--minutes=30`)
- `notifications:send-plan-expiration-reminders`
- `queue:process-cron-batch --queue=default,emails ...` (drains professor reminder jobs)

The diagnostic reminder schedule entry must not set a custom timezone; eligibility uses UTC `Carbon::now('UTC')` and UTC-stored class instants. This must not alter `config('app.timezone')` / process default timezone.

## Queue / Email Side-Effects Matrix

| Effect | When | Required | Forbidden |
| --- | --- | --- | --- |
| Candidate webhook HTTP POST | Eligible class + candidate cache miss + successful send | Required | Duplicate POST for same class/minutes bucket while TTL holds |
| `SendEmailJob` on `emails` | Eligible class with professor.user + professor cache miss + mail dispatch path | Required | Synchronous SMTP send inside reminder command/service |
| Cache key write | Before channel send | Required | Leaving key set after failed send that should retry |
| Datadog/info logs | Command/service completion and channel failures | Required for observability | Silent swallow of channel exceptions |
| DB schema change | Never in this spec | Forbidden | Any migration |
| UI notification screen | Never in this spec | Forbidden | Frontend edits |

## Idempotency And Retry Semantics

| Scenario | Expected result |
| --- | --- |
| First successful run in bucket | Candidate webhook once; professor email job once; counters increment. |
| Immediate second run same bucket | Eligible class may still be counted in `classes_found`, but `notifications_sent` and `professor_emails_sent` remain 0 for already-locked channels; no duplicate webhook/job. |
| Candidate webhook fails | Candidate cache key forgotten; professor channel still attempted; error recorded; later tick may retry candidate. |
| Professor dispatch throws / returns false after lock | Professor cache key forgotten; candidate success remains; later tick may retry professor. |
| Overlapping scheduler ticks | Laravel `withoutOverlapping()` prevents concurrent command execution for the scheduled entry. |
| Legacy HTTP concurrent callers | `notifications_running` cache lock (300s) returns HTTP 429 `Process already running`. |

## Timezone Rules

| Actor | Source timezone | Projection rule |
| --- | --- | --- |
| Stored class instant | UTC columns `starting_date` + `starting_time` | Parsed as UTC; this is the eligibility clock. |
| Candidate | `candidate_timezone` if valid, else `America/Bogota` | `copy()->setTimezone(candidate)` for webhook `class_*` fields. |
| Professor | user timezone helper with default `America/Bogota` | `copy()->setTimezone(professor)` for email display fields. |
| Scheduler cadence | App/process timezone unchanged | Do not pin diagnostic reminder schedule entry to `America/Bogota`. |

Parity vs intentional change:

| Topic | Decision |
| --- | --- |
| Mutable Carbon reuse across candidate then professor | Bug relative to temporal-projection contract; current reminder service must keep independent `copy()` projections. |
| Fallback `America/Bogota` when timezone invalid/missing | Preserve existing reminder behavior. |
| Expanding to full `viewer_*` DTO fields in reminder payloads | Deferred to temporal-projection sibling; not required here. |

## Legacy Endpoint Parity

Route: `GET /api/send-entry-notification` → `DiagnosticClassController::sendUpcomingClassNotifications` (throttle middleware group `throttle:10,1`).

| Concern | Contract |
| --- | --- |
| Auth | Header `X-API-KEY` must equal `config('app.cron_api_key')`; otherwise `401` `{"error":"Unauthorized"}`. |
| Rate limit | Max 2 attempts per IP key `send-notifications:{ip}`; excess returns `429` with `retry_after`; hits expire after 300 seconds. |
| Concurrency lock | `Cache::add('notifications_running', true, 300)`; if locked, `429` `Process already running`. |
| Happy path | Calls `$this->diagnosticClassReminderService->send(60)`. |
| Response 200 | `message` = `Notifications sent successfully`; `body` = eligible diagnostic class list (collection/array of classes); `summary` = `{classes_found, notifications_sent, professor_emails_sent, errors}`. |
| `body` compatibility | Remains a list of eligible diagnostic classes (legacy consumers reading `body` as the class list must keep working). `summary` is additive metadata. |
| Server error | On exception: forget lock, log error, `500` `{"error":"Server error"}`. |
| Lock cleanup | Forget `notifications_running` on success and on exception paths that acquired the lock. |

## Error Handling

| Layer | Behavior |
| --- | --- |
| Per-class datetime | Catch, append `errors[]` with `channel=datetime`, continue. |
| Candidate channel | Catch, append `errors[]` with `channel=candidate`, continue to professor. |
| Professor channel | Catch, append `errors[]` with `channel=professor`, continue to next class. |
| Command | Partial errors → exit 0 + warn output; only uncaught top-level throwable → exit non-zero. |
| Legacy HTTP | Uncaught exception after lock → 500; auth/rate/lock failures → 401/429 without invoking send when blocked. |

## Actors / Triggers

| Actor | Trigger | Authority |
| --- | --- | --- |
| Laravel scheduler / host cron calling `schedule:run` | Primary production path | No API key; process-local artisan |
| Operator/automation with `CRON_API_KEY` | Legacy HTTP GET | Must present matching `X-API-KEY` |
| End users / frontends | None | Forbidden as reminder triggers |

## Acceptance Criteria

1. `schedule:list` / scheduled events include `notifications:send-diagnostic-class-reminders --minutes=60` every five minutes with overlapping protection.
2. Artisan command delegates to `DiagnosticClassReminderService::send` and exits 0 on partial channel errors.
3. A due diagnostic class in the 55–60 minute UTC bucket receives exactly one candidate webhook and one professor `emails` job on first successful run.
4. A second run in the same bucket does not duplicate candidate or professor side effects.
5. Candidate webhook failure still allows professor email dispatch and records an isolated candidate error.
6. Malformed datetime on one class does not abort reminders for other eligible classes.
7. `classes_found` counts only minute-bucket eligible classes.
8. Legacy endpoint rejects missing API key with 401, succeeds with key, returns class list in `body`, and includes `summary`.
9. No migration, UI, SMTP, or host-cron redesign is introduced under this spec.
10. Focused PHPUnit evidence listed in Test Plan passes.
11. `flow ci spec` for this spec passes after governance review/approval gates are run by the orchestrator.

## Slice Breakdown

Because the feature is already implemented in backend code, slices lock and verify the contract rather than inventing new product surface.

```yaml
- name: reminder-scheduler-contract-spec
  repo: plg-platform-harness
  targets:
    - ../../specs/features/plg/2026-09-10-diagnostic-class-reminder-scheduler.spec.md
  hot_area: canonical SoftOS contract for diagnostic reminder scheduler
  depends_on: []
  slice_mode: governance
  surface_policy: forbidden
  minimum_valid_completion: this spec exists with schema_version 3, grounded targets, command/scheduler/idempotency/legacy contracts, slices, Verification Matrix, stop conditions, and evidence requirements
  validated_noop_allowed: false
  acceptable_evidence:
    - spec file present at the canonical path
    - frontmatter validates under SoftOS schema_version 3 expectations
    - no code/state/manifest edits in this slice

- name: scheduler-and-command-verification
  repo: plg-platform-backend
  targets:
    - ../../plg-platform-backend/src/app/Console/Kernel.php
    - ../../plg-platform-backend/src/app/Console/Commands/SendDiagnosticClassReminders.php
    - ../../plg-platform-backend/src/app/Services/DiagnosticClassReminderService.php
    - ../../plg-platform-backend/src/tests/Feature/DiagnosticClassReminderCommandTest.php
    - ../../plg-platform-backend/src/tests/Feature/HubNotificationSchedulerTest.php
  hot_area: schedule registration, command exit semantics, eligibility, idempotency, channel isolation
  depends_on:
    - reminder-scheduler-contract-spec
  slice_mode: verification-only
  surface_policy: forbidden
  minimum_valid_completion: focused PHPUnit proves scheduler registration and service/command contracts without expanding UI or migrations
  validated_noop_allowed: true
  acceptable_evidence:
    - DiagnosticClassReminderCommandTest passes
    - HubNotificationSchedulerTest::test_legacy_notification_schedules_remain_registered passes
    - code changes only if a verified contract defect blocks acceptance; otherwise validated no-op closeout

- name: legacy-endpoint-parity-verification
  repo: plg-platform-backend
  targets:
    - ../../plg-platform-backend/src/app/Http/Controllers/DiagnosticClassController.php
    - ../../plg-platform-backend/src/routes/api.php
    - ../../plg-platform-backend/src/tests/Feature/DiagnosticClassReminderCommandTest.php
  hot_area: /api/send-entry-notification auth status body summary parity
  depends_on:
    - scheduler-and-command-verification
  slice_mode: verification-only
  surface_policy: forbidden
  minimum_valid_completion: legacy endpoint parity assertions pass while keeping body as eligible class list and summary additive
  validated_noop_allowed: true
  acceptable_evidence:
    - test_legacy_endpoint_preserves_auth_status_and_body_with_summary passes
    - no route/controller redesign beyond defect repair required by this contract
```

## Stop Conditions

Stop and escalate to the orchestrator if any of the following occurs:

- Closing a defect appears to require a database migration or schema change.
- Fixing timezone display appears to require frontend or broad `viewer_*` DTO rollout beyond reminder payloads.
- Professor delivery cannot use queue `emails` without changing SMTP/infrastructure.
- Legacy consumers require removing `summary` or changing `body` away from a class list.
- Scheduler registration conflicts with an approved sibling Hub/notifications spec in an unresolved way.
- Required proof needs production-only credentials or live webhook/SMTP side effects.
- A change would edit files outside declared `targets`.

## Evidence Requirements

Minimum evidence package for closeout:

1. Spec governance: `flow spec review` / `flow ci spec` for this path (orchestrator-owned gate after this worker deliverable).
2. Command/service proof:

```bash
python3 ./flow repo exec plg-platform-backend -- php -d memory_limit=512M src/vendor/bin/phpunit -c src/phpunit.xml src/tests/Feature/DiagnosticClassReminderCommandTest.php
```

3. Scheduler coexistence proof:

```bash
python3 ./flow repo exec plg-platform-backend -- php -d memory_limit=512M src/vendor/bin/phpunit -c src/phpunit.xml src/tests/Feature/HubNotificationSchedulerTest.php --filter test_legacy_notification_schedules_remain_registered
```

4. Optional operator inspection (non-blocking alone):

```bash
python3 ./flow repo exec plg-platform-backend -- php src/artisan list notifications
python3 ./flow repo exec plg-platform-backend -- php src/artisan schedule:list
```

5. Diff hygiene for any repair slice: `git -C plg-platform-backend diff --check`.

## Test Plan

- [@test] ../../plg-platform-backend/src/tests/Feature/DiagnosticClassReminderCommandTest.php
- [@test] ../../plg-platform-backend/src/tests/Feature/HubNotificationSchedulerTest.php

Focused behaviors already encoded in tests and required by this contract:

- command delegates to service and prints counters
- service sends candidate webhook and queues professor email for due class
- no duplicate candidate/professor sends in same bucket
- candidate channel errors isolate and continue professor path
- `classes_found` uses minute bucket, not only SQL date window
- malformed datetime isolates as `datetime` error
- command exits 0 with partial errors
- legacy endpoint auth/status/`body`/`summary` parity
- scheduler retains diagnostic reminder registration alongside legacy notification schedules

## Verification Matrix

```yaml
- name: spec-review
  level: custom
  command: python3 ./flow workspace exec -- python3 ./flow spec review specs/features/plg/2026-09-10-diagnostic-class-reminder-scheduler.spec.md --json
  blocking_on: [approval]
  environments: [local]
  notes: validates schema_version 3 shape, targets, depends_on, and governance readiness

- name: spec-ci
  level: custom
  command: python3 ./flow workspace exec -- python3 ./flow ci spec specs/features/plg/2026-09-10-diagnostic-class-reminder-scheduler.spec.md --json
  blocking_on: [ci]
  environments: [local]
  notes: SoftOS spec CI gate for this feature contract

- name: backend-reminder-focused
  level: integration
  command: python3 ./flow repo exec plg-platform-backend -- php -d memory_limit=512M src/vendor/bin/phpunit -c src/phpunit.xml src/tests/Feature/DiagnosticClassReminderCommandTest.php
  blocking_on: [ci]
  environments: [local]
  notes: proves command/service idempotency, channel isolation, queue emails, legacy endpoint parity

- name: backend-scheduler-coexistence
  level: integration
  command: python3 ./flow repo exec plg-platform-backend -- php -d memory_limit=512M src/vendor/bin/phpunit -c src/phpunit.xml src/tests/Feature/HubNotificationSchedulerTest.php --filter test_legacy_notification_schedules_remain_registered
  blocking_on: [ci]
  environments: [local]
  notes: proves diagnostic reminder schedule remains registered with legacy notification schedules

- name: backend-repo-ci
  level: integration
  command: python3 ./flow repo exec plg-platform-backend -- php -d memory_limit=512M src/vendor/bin/phpunit -c src/phpunit.xml --filter "DiagnosticClassReminder|legacy_notification_schedules"
  blocking_on: [ci]
  environments: [local]
  notes: aggregated focused filter before broader repo CI if a repair slice touched code
```

## Rollout / Rollback

| Mode | Expectation |
| --- | --- |
| Rollout | Already implemented in backend; enablement is existing host `schedule:run` plus queue drain for `emails`. |
| Rollback | Remove or disable only the diagnostic schedule entry if emergency stop is required; prefer keeping shared service for legacy HTTP. Do not drop queue infrastructure. |
| Data | No migration; cache keys expire by TTL. |

## Explicit Non-Goals Recap

Do not invent migration scope. Do not invent UI scope. Do not redesign SMTP/cron hosts. Do not expand this into the temporal-projection DTO program.
