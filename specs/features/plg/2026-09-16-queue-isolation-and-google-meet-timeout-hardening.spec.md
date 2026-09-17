---
schema_version: 3
name: "Queue isolation and Google Meet timeout hardening"
description: "Preserve existing google-meet / default / emails queue isolation; harden concurrency caps, Google Retry-After release/delay, reconcile and transcript stop conditions without new DB columns; add focused tests and evidence."
status: released
owner: platform
single_slice_reason: "Queue isolation already exists in Kernel and CronjobController; this feature hardens concurrency, Retry-After handling, stop conditions, and verification without schema expansion."
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
  - ../../specs/features/plg/2026-09-16-queue-isolation-and-google-meet-timeout-hardening.spec.md
  - ../../plg-platform-backend/src/app/Console/Kernel.php
  - ../../plg-platform-backend/src/app/Console/Commands/ProcessQueueCronBatchCommand.php
  - ../../plg-platform-backend/src/app/Http/Controllers/CronjobController.php
  - ../../plg-platform-backend/src/app/Http/Controllers/QueueController.php
  - ../../plg-platform-backend/src/config/queue.php
  - ../../plg-platform-backend/src/config/google.php
  - ../../plg-platform-backend/src/app/Jobs/ReconcileMeetConferenceSessionsJob.php
  - ../../plg-platform-backend/src/app/Jobs/IngestGoogleMeetTranscriptJob.php
  - ../../plg-platform-backend/src/app/Services/GoogleWorkspace/GoogleMeetTranscriptProvider.php
  - ../../plg-platform-backend/src/app/Services/GoogleWorkspace/GoogleMeetTranscriptIngestionService.php
  - ../../plg-platform-backend/src/app/Services/GoogleWorkspace/GoogleMeetConferenceSessionBindingService.php
  - ../../plg-platform-backend/src/app/Services/GoogleWorkspace/GoogleMeetRetryAfterException.php
  - ../../plg-platform-backend/src/app/Services/GoogleWorkspace/GoogleMeetTranscriptMaxPagesPerAttemptException.php
  - ../../plg-platform-backend/src/tests/Feature/GoogleMeetReconciliationQueueTest.php
  - ../../plg-platform-backend/src/tests/Feature/ProcessQueueCronBatchCommandTest.php
test_refs:
  - "../../plg-platform-backend/src/tests/Feature/GoogleMeetReconciliationQueueTest.php"
  - "../../plg-platform-backend/src/tests/Feature/ProcessQueueCronBatchCommandTest.php"

---

# Queue isolation and Google Meet timeout hardening

## Objective

Preserve the already-implemented isolation of Laravel queue workers across `google-meet`, `default`, and `emails`. Harden concurrency caps, Google HTTP `Retry-After` handling via job `release`/`delay`, reconcile and transcript pagination stop conditions, and focused verification — without new database columns (Schema B).

## Context

Production processes Meet reconciliation, transcript ingestion, mail, and default jobs through minute-tick cron (`schedule:run` or `/cronjob/process-queue`), not a long-running `queue:work` daemon. Isolation already exists:

- `Kernel` schedules `queue:process-cron-batch --queue=google-meet` separately from `--queue=default,emails`.
- `CronjobController::processQueueBatch` invokes the same two batch calls.
- `ReconcileMeetConferenceSessionsJob` and `IngestGoogleMeetTranscriptJob` call `onQueue('google-meet')` with `$tries = 3` on reconcile and binding checkpoints at `[1, 3, 5, 10, 15, 30, 60, 120, 360]` minutes.
- `GoogleMeetTranscriptProvider::entries` already paginates with `pageSize <= 100` and returns `nextPageToken`, but `getJson` uses fixed `usleep` backoff and does **not** parse HTTP `Retry-After`.

The remaining gap is concurrency/timeout alignment and provider backpressure, not inventing a second isolation layer.

## Technical observed inventory

| Observed path | Role today | Policy |
| --- | --- | --- |
| `app/Console/Kernel.php` | Schedules `queue:process-cron-batch --queue=google-meet --max-jobs=200 --max-time=55` and `--queue=default,emails --max-jobs=100 --max-time=55` every minute with `withoutOverlapping` | **Preserve** isolation invariant; only adjust caps if config-driven values replace hard-coded CLI flags consistently. |
| `ProcessQueueCronBatchCommand` | Cache lock keyed by queue-list md5; runs `queue:work --tries=3 --timeout=120 --max-jobs/--max-time --stop-when-empty`; skips when `QUEUE_CONNECTION=sync` | **Harden** concurrency caps, lock semantics, and align worker timeout with connection `retry_after`. |
| `CronjobController::processQueueBatch` | Calls batch for `google-meet` then `default,emails` | **Preserve** queue awareness; do not claim it lacks isolation. |
| `QueueController::processQueue` | Operational endpoint that runs `queue:work --queue=emails` under rate limit + cache lock | **Preserve** emails-only behavior; no Meet routing or invented dispatch API. |
| `config/queue.php` | Connection `retry_after` defaults to `90` for database/redis | **Harden** so visibility timeout stays strictly greater than worker `--timeout` (or reduce timeout). |
| `ReconcileMeetConferenceSessionsJob` | `onQueue('google-meet')`; `public int $tries = 3`; unique keys; binds `observed_unbound` sessions; marks `not_generated` after reconcile hours when no artifacts | **Preserve** `$tries` and checkpoints; add Retry-After-aware `release`/`delay` without DB columns. |
| `IngestGoogleMeetTranscriptJob` | `onQueue('google-meet')`; unique until processing | **Harden** release/delay on provider 429 when ingestion path surfaces it. |
| `GoogleMeetConferenceSessionBindingService::markEnded` | Dispatches delayed reconcile jobs at fixed checkpoint minutes | **Preserve** checkpoint schedule; do not replace with new retry columns. |
| `GoogleMeetTranscriptProvider::getJson` | Retries 429/5xx up to 3 attempts with `usleep(50_000 * $attempts)`; no header parse | **Required change**: parse `Retry-After` and expose delay seconds to callers/jobs. |
| `GoogleMeetTranscriptProvider::entries` | `pageSize` clamped `1..100`; returns `nextPageToken` | **Preserve** pagination contract; stop conditions live at job/cache/ingestion level, not new columns. |
| `GoogleMeetTranscriptIngestionService::fetchAllPages` | Loops `entries` until `nextPageToken` is null | **Harden** bounded page/time stop conditions without persisting page tokens on sessions. |
| Association statuses | `observed_unbound`, `not_generated` (among others) | **Status vocabulary for this spec**: use `observed_unbound` / `not_generated` only; do not invent uppercase aliases. |

## Foundations and domains

Applicable foundation contracts are listed in `depends_on`. No new domain vocabulary is introduced. Queue names remain the literal Laravel queue strings already used in production code: `google-meet`, `default`, `emails`.

## Problem to solve

1. Meet reconciliation and mail/default work can still contend for host CPU/time within a cron minute if concurrency caps and locks are weak or misaligned.
2. Google Meet HTTP 429/5xx responses do not honor provider `Retry-After`, so jobs burn `$tries` with fixed micro-sleeps instead of releasing with an informed delay.
3. Connection `retry_after` (90s) vs worker `--timeout` (120s) can leave reserved jobs invisible longer than intended or cause duplicate visibility races.
4. Transcript pagination can run unbounded page loops inside a single job attempt when transcripts are large or the provider stalls.
5. Prior draft language invented queue aliases, DB columns, feature flags, and false claims (unbounded retries; CronjobController without queue awareness). Those must not reappear.

## Scope

1. Keep queue vocabulary exactly: `google-meet`, `default`, `emails`.
2. Preserve Kernel + CronjobController isolation as an invariant.
3. Make concurrency caps explicit and testable for `ProcessQueueCronBatchCommand` (and config if needed).
4. Parse Google/HTTP `Retry-After` on Meet provider failures and apply Laravel job `release($seconds)` or delayed re-dispatch — Schema B (no new DB columns).
5. Align stop conditions with existing `$tries = 3` and binding checkpoints; mark `not_generated` only via existing reconcile-hours path when artifacts are absent.
6. Bound transcript page fetching with in-memory / job-level stop conditions (max pages per attempt, rethrow/release on 429).
7. Align `config/queue.php` connection `retry_after` with worker timeout semantics.
8. Extend focused PHPUnit coverage and persist evidence.

## Out of scope

- New migrations or columns for Meet attempt counters, stored provider delay seconds, lock TTL milliseconds, or persisted transcript page tokens.
- Invented queue aliases or constant renames for queue names.
- Feature flag to toggle Meet queue isolation.
- Changing Classroom/Calendar product behavior or mock data.
- Replacing checkpoint delays in `GoogleMeetConferenceSessionBindingService` with a new persistence model.
- Expanding `QueueController` into a Meet dispatcher.
- Frontend, Hub, DNS, Google Workspace admin console, or infra daemon redesign beyond cron-batch workers.

## Governing decisions

| Decision | Contract |
| --- | --- |
| Queue vocabulary | Only `google-meet`, `default`, `emails`. No aliases. |
| Isolation status | **Already implemented** in `Kernel` and `CronjobController`. Preserve as invariant; do not re-implement via flags or controllers. |
| Schema | **B**: no new DB columns. Use job `release`/`delay`, Cache locks, existing `$tries`, and binding checkpoints. |
| Provider backoff | Prefer parsed HTTP `Retry-After` seconds; else bounded default backoff; never invent DB-stored retry counters. |
| Status values | Persist/assert `observed_unbound` and `not_generated` (snake_case strings already on the model). |
| focused-tests | `surface_policy: required` — focused tests must exist and pass before closeout. |
| Frontmatter | Keep `status: draft` until SoftOS review/approve outside this Patch Unit. |
| Prohibited inventions | No invented dispatch or job-manifest routers, no fake isolation flag, no unbounded-retry claims. |

## Affected surfaces

| Surface | Required change |
| --- | --- |
| `ProcessQueueCronBatchCommand` | Explicit per-queue-list concurrency/lock behavior; configurable or documented caps; timeout/`retry_after` alignment inputs. |
| `config/queue.php` | Connection `retry_after` must exceed worker job timeout used by cron batch (or timeout reduced to stay below it). |
| `config/google.php` | Optional documented knobs for Meet provider default backoff / max transcript pages per attempt — values only, no schema. |
| `GoogleMeetTranscriptProvider` | Parse `Retry-After` (or equivalent 429 guidance); surface delay to callers; keep `pageSize <= 100`. |
| `ReconcileMeetConferenceSessionsJob` / ingest path | On Retry-After-aware transient failure: `release`/`delay` within `$tries`; do not add columns. |
| `GoogleMeetTranscriptIngestionService::fetchAllPages` | Stop after configured max pages per attempt; leave remaining work to a subsequent job attempt without DB page-token columns. |
| `Kernel` / `CronjobController` | Preserve dual-batch isolation; update CLI flags only if caps move to config and must stay in sync. |
| `QueueController` | No behavioral expansion for Meet; regression-safe emails worker only. |
| Focused tests | Extend `ProcessQueueCronBatchCommandTest` and `GoogleMeetReconciliationQueueTest` (and/or sibling focused tests under declared targets). |

## retry_after disambiguation table

| Term | Where it lives | Meaning | This spec uses it for |
| --- | --- | --- | --- |
| Connection `retry_after` | `config/queue.php` → `connections.*.retry_after` | Laravel visibility timeout: seconds before a reserved job may be picked again if the worker dies | Must be **strictly greater** than cron-batch `--timeout` |
| HTTP `Retry-After` | Google Meet API response header on 429 (or documented equivalent) | Provider-requested wait before next request | Parsed and converted to integer seconds for job `release`/`delay` |
| Job release delay | `$job->release($seconds)` / `->delay(...)` | Puts the job back on the queue after N seconds without a DB column | Schema B backoff mechanism |
| Cache lock TTL | `ProcessQueueCronBatchCommand` `Cache::put($lockKey, true, $maxTime + 30)` | Prevents overlapping ticks for the same queue list | Concurrency control for cron batches |
| Binding checkpoint delay | `markEnded` delayed dispatches at fixed minute marks | Product reconcile cadence for missing transcripts | Preserved; not a substitute for HTTP Retry-After |

Never store HTTP Retry-After on conference session rows. Never conflate connection `retry_after` with HTTP `Retry-After`.

## Required implementation algorithms

### A. Preserve queue isolation (invariant)

1. Confirm `Kernel` still schedules two distinct `queue:process-cron-batch` entries: one for `google-meet`, one for `default,emails`.
2. Confirm `CronjobController::processQueueBatch` still invokes both with the same queue lists.
3. Confirm Meet jobs continue to `onQueue('google-meet')` and mail continues to use `emails`.
4. Fail verification if any change merges Meet work into `default`/`emails` workers or invents alternate queue names.

### B. Concurrency caps and cron-batch locks

1. Keep a lock key derived from the exact `--queue` list (existing md5 pattern is acceptable).
2. Do not block `google-meet` batches on `default,emails` locks or vice versa (except intentional global host safeguards documented in code comments/tests).
3. Enforce caps via `--max-jobs` / `--max-time` and optional config mirrors; defaults must remain at least as protective as today (`google-meet`: max-jobs 200 / max-time 55; `default,emails`: max-jobs 100 / max-time 55) unless an explicit config change is evidenced.
4. When `QUEUE_CONNECTION=sync`, continue skipping the batch worker.

### C. Align worker timeout with connection `retry_after`

1. Read the active connection's `retry_after`.
2. Ensure cron-batch `queue:work --timeout` is **less than** that value (Laravel requirement).
3. Preferred fix: raise database/redis `retry_after` above 120 if timeout remains 120; alternative: lower `--timeout` below current `retry_after` and document the chosen pair in evidence.
4. Do not introduce a second competing timeout source without documenting precedence in this table.

### D. Parse Retry-After and release jobs (Schema B)

1. In `GoogleMeetTranscriptProvider::getJson`, on HTTP 429 (and optionally 503 when `Retry-After` is present), read the `Retry-After` header.
2. If the header is an integer delay-seconds, use `max(1, min(parsed, configured_ceiling))`.
3. If the header is an HTTP-date, convert to delay seconds with the same ceiling.
4. If absent, use existing bounded default backoff (may keep short in-request retries, but exhausted attempts must propagate a typed/transient signal including suggested delay seconds).
5. Callers that run inside queued jobs (`ReconcileMeetConferenceSessionsJob`, `IngestGoogleMeetTranscriptJob`, ingestion service) must `release($seconds)` or equivalent delay when a Retry-After-aware transient is raised and attempts remain under `$tries`.
6. After `$tries` is exhausted, allow Laravel failed-job handling; do **not** invent infinite retries.

### E. Reconcile stop conditions

1. Keep `public int $tries = 3` on `ReconcileMeetConferenceSessionsJob`.
2. Keep querying `association_status = observed_unbound` with `imparted_class_id IS NULL` for unbound reconcile.
3. Keep marking `association_status = not_generated` only when provider artifacts are empty and `provider_ended_at` is older than `config('google.meet_transcript_reconcile_hours')` (existing path).
4. Preserve checkpoint delayed jobs from `markEnded`; do not replace them with DB retry counters.
5. Stop and fail the attempt (release or throw) when provider Retry-After requires waiting; do not busy-loop.

### F. Transcript pagination stop conditions (no new columns)

1. Keep `entries` page size clamped to `<= 100`.
2. In `fetchAllPages`, iterate tokens in memory only.
3. Stop the current attempt when: `nextPageToken` is null/empty; **or** page count reaches a configured max-pages-per-attempt; **or** a Retry-After-aware transient is raised.
4. On max-pages stop with remaining token work: release/delay the ingest job so a later attempt continues from durable transcript progress already persisted by ingestion — **not** from a new session column.
5. Never write `transcript_page_token` (or similar) onto `google_meet_conference_sessions`.

## Disposition and threshold matrix

| Condition | Disposition | Threshold / stop |
| --- | --- | --- |
| Overlapping cron tick for same queue list | Skip tick (success) | Cache lock present |
| `QUEUE_CONNECTION=sync` | Skip batch | Always |
| HTTP 429 with Retry-After | Release/delay job | Delay = parsed seconds capped by config ceiling; counts toward `$tries` when Laravel releases consume tries |
| HTTP 429 without Retry-After | Release/delay with default backoff | Default backoff ≤ configured ceiling; ≤ 3 in-request usleep attempts then propagate |
| HTTP 5xx | Existing retry then propagate | ≤ 3 in-request attempts |
| Worker timeout vs connection retry_after | Block closeout until aligned | `timeout < retry_after` |
| Unbound session still unbound after binding attempt | Remain `observed_unbound` | No status invention |
| Ended session, no artifacts, past reconcile hours | Set `not_generated` | Existing hours config |
| Transcript pages exceed max per attempt | Stop attempt; release ingest job | Config max pages ≥ 1 |
| Job exceeded `$tries` | Failed job / Laravel failure path | `$tries = 3` for reconcile |
| Proposed new DB column for retries/tokens | Reject | Schema B absolute |

## Stop conditions

Stop implementation and report a blocker if:

- preserving isolation would require merging `google-meet` into `default`/`emails` workers;
- Retry-After handling cannot be applied without a new migration/column;
- connection `retry_after` cannot be aligned with worker timeout without changing unrelated queue drivers in unsafe ways;
- existing Google Meet reconciliation/ingestion tests fail for reasons outside this hardening scope;
- an implementer believes a feature flag or alternate queue vocabulary is required — that belief contradicts governing decisions and must be escalated, not coded.

## Observable contract

- Scheduler and cron HTTP entrypoints continue to process `google-meet` separately from `default,emails`.
- Meet reconcile/ingest jobs remain on queue `google-meet`.
- On provider 429 with `Retry-After: N`, the next job attempt is not started earlier than ~N seconds (subject to queue tick granularity).
- `observed_unbound` and `not_generated` remain the status strings used by reconcile paths covered here.
- No new columns appear on Meet session/transcript tables for this feature.

## Acceptance criteria

1. Isolation invariant documented and covered by focused tests (scheduler commands and/or cron batch queue lists).
2. Cron-batch concurrency locks do not incorrectly serialize unrelated queue lists.
3. Provider parses `Retry-After` and jobs release/delay accordingly without DB writes for backoff.
4. `timeout < retry_after` holds for the active queue connection used in non-sync environments.
5. Transcript pagination has an explicit max-pages-per-attempt stop without new columns.
6. Focused PHPUnit tests required by slices are green; evidence package delivered under the path below.
7. Spec body contains none of the prohibited invention strings listed in Residual debt / anti-hallucination.

## Residual debt

- Account-level Google Workspace quota increases remain operational.
- Long-running `queue:work` daemons (if introduced later by infra) are out of scope; this spec assumes cron-batch ticks.
- Classroom job backoff arrays are reference patterns only; Meet may use release-on-Retry-After rather than copying Classroom's `[60, 180, 600]` unless tests prove equivalence is desirable.
- `QueueController`'s emails-only worker is legacy operational surface; unifying it with `ProcessQueueCronBatchCommand` is deferred debt, not this feature.

## Slice Breakdown

```yaml
- name: queue-isolation-invariant-and-caps
  repo: plg-platform-backend
  targets:
    - ../../plg-platform-backend/src/app/Console/Kernel.php
    - ../../plg-platform-backend/src/app/Console/Commands/ProcessQueueCronBatchCommand.php
    - ../../plg-platform-backend/src/app/Http/Controllers/CronjobController.php
    - ../../plg-platform-backend/src/app/Http/Controllers/QueueController.php
    - ../../plg-platform-backend/src/config/queue.php
  hot_area: preserve google-meet vs default,emails isolation; concurrency caps; timeout vs connection retry_after
  depends_on: []
  slice_mode: minimal-change
  surface_policy: required
  minimum_valid_completion: dual-batch isolation preserved; locks/caps explicit; timeout < connection retry_after
  validated_noop_allowed: false
  acceptable_evidence:
    - focused ProcessQueueCronBatchCommand / schedule isolation tests pass
    - config or command evidence showing timeout/retry_after alignment

- name: meet-retry-after-and-stop-conditions
  repo: plg-platform-backend
  targets:
    - ../../plg-platform-backend/src/app/Services/GoogleWorkspace/GoogleMeetTranscriptProvider.php
    - ../../plg-platform-backend/src/app/Services/GoogleWorkspace/GoogleMeetTranscriptIngestionService.php
    - ../../plg-platform-backend/src/app/Jobs/ReconcileMeetConferenceSessionsJob.php
    - ../../plg-platform-backend/src/app/Jobs/IngestGoogleMeetTranscriptJob.php
    - ../../plg-platform-backend/src/app/Services/GoogleWorkspace/GoogleMeetConferenceSessionBindingService.php
    - ../../plg-platform-backend/src/app/Services/GoogleWorkspace/GoogleMeetRetryAfterException.php
    - ../../plg-platform-backend/src/app/Services/GoogleWorkspace/GoogleMeetTranscriptMaxPagesPerAttemptException.php
    - ../../plg-platform-backend/src/config/google.php
  hot_area: Schema B Retry-After release/delay; pagination and reconcile stop conditions
  depends_on: [queue-isolation-invariant-and-caps]
  slice_mode: minimal-change
  surface_policy: required
  minimum_valid_completion: Retry-After parsed and applied via release/delay; no new DB columns; observed_unbound/not_generated paths preserved
  validated_noop_allowed: false
  acceptable_evidence:
    - provider unit/feature test with Retry-After header
    - pagination max-pages stop test
    - reconcile tries/checkpoint regression assertions

- name: focused-tests-and-evidence
  repo: plg-platform-backend
  targets:
    - ../../plg-platform-backend/src/tests/Feature/GoogleMeetReconciliationQueueTest.php
    - ../../plg-platform-backend/src/tests/Feature/ProcessQueueCronBatchCommandTest.php
  hot_area: required focused verification and evidence packaging
  depends_on: [queue-isolation-invariant-and-caps, meet-retry-after-and-stop-conditions]
  slice_mode: minimal-change
  surface_policy: required
  minimum_valid_completion: focused PHPUnit suite for this feature green; evidence directory populated
  validated_noop_allowed: false
  acceptable_evidence:
    - PHPUnit focused output
    - flow ci spec JSON for this spec
```

## Test Plan

Existing regression surfaces (must remain green):

- [@test] ../../plg-platform-backend/src/tests/Feature/GoogleMeetReconciliationQueueTest.php
- [@test] ../../plg-platform-backend/src/tests/Feature/ProcessQueueCronBatchCommandTest.php
- [@test] ../../plg-platform-backend/src/tests/Feature/GoogleMeetClassSessionBoundaryTest.php
- [@test] ../../plg-platform-backend/src/tests/Feature/GoogleMeetClassTranscriptIngestionTest.php
- [@test] ../../plg-platform-backend/src/tests/Feature/GoogleMeetTranscriptPresentationContractTest.php

Required new/extended assertions:

1. Scheduler or cron-batch inventory: `google-meet` batch exists separately from `default,emails`.
2. Lock behavior: overlapping same queue-list skipped; other queue-list not blocked by dead global lock mistakes.
3. Provider: 429 with `Retry-After` yields the parsed delay to the job layer.
4. Job: release/delay invoked (faked queue) without writing retry columns.
5. Pagination: stops at max pages without requiring a session page-token column.
6. Status: unbound path keeps `observed_unbound`; empty-artifact late path still sets `not_generated`.

## Verification Matrix

```yaml
- name: spec-review
  level: custom
  command: python3 ./flow workspace exec -- python3 ./flow spec review specs/features/plg/2026-09-16-queue-isolation-and-google-meet-timeout-hardening.spec.md --json
  blocking_on: [approval]
  environments: [local]

- name: spec-ci
  level: custom
  command: python3 ./flow workspace exec -- python3 ./flow ci spec specs/features/plg/2026-09-16-queue-isolation-and-google-meet-timeout-hardening.spec.md --json
  blocking_on: [ci]
  environments: [local]

- name: backend-queue-meet-focused
  level: integration
  command: python3 ./flow repo exec plg-platform-backend -- php -d memory_limit=512M src/vendor/bin/phpunit -c src/phpunit.xml --filter "ProcessQueueCronBatch|GoogleMeetReconciliation|GoogleMeetClassTranscriptIngestion|GoogleMeetTranscriptPresentation"
  blocking_on: [ci]
  environments: [local]

- name: backend-repo-ci
  level: integration
  command: python3 ./flow repo exec plg-platform-backend -- php -d memory_limit=512M src/vendor/bin/phpunit -c src/phpunit.xml
  blocking_on: [ci]
  environments: [local]
  notes: full suite before release; focused filter is the minimum merge gate for implementation slices

- name: cross-repo-contract
  level: integration
  command: python3 ./flow ci integration --profile smoke:ci-clean --auto-up --json
  blocking_on: [ci]
  environments: [local]
  notes: only when stack/orchestration wiring changes; not required for pure Meet provider unit edits
```

## Evidence package

The implementation handoff must include:

- modified file list bounded to this spec's `targets`;
- focused PHPUnit output for cron-batch isolation, Retry-After release/delay, and pagination stops;
- proof of `timeout < retry_after` for the active non-sync connection;
- confirmation no migration added Meet retry/token columns;
- `flow spec review` and `flow ci spec` JSON for this spec.

## Evidence delivery contract

- Persist evidence under `.flow/evidence/plg/2026-09-16-queue-isolation-and-google-meet-timeout-hardening/`.
- Reference that directory from the slice handoff and closeout report.
- Redact secrets, tokens, and PII from provider payloads.
- Functional/E2E relationship: existing Meet reconciliation and transcript ingestion feature tests are the primary functional evidence; no new Hub/UI E2E is required unless a slice expands presentation surfaces (forbidden by this spec).

## Rollback

Revert application/config changes only. No migrations to roll back under Schema B. Failed jobs already on `google-meet` remain processable by the preserved isolation path.

## Anti-hallucination checklist (implementers)

Do **not** introduce or restate as required:

- alternate queue names or constant renames for queues;
- DB columns for Meet retries, Retry-After storage, lock TTL, or transcript page tokens;
- isolation feature flags;
- claims that reconcile retries without bound;
- claims that `CronjobController` lacks queue awareness;
- invented Meet dispatch APIs on `QueueController`.
