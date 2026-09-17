---
schema_version: 2
name: Dashboard Frontend SSH Deploy Migration
description: Migrar el deploy de dashboard-frontend desde FTP hacia SSH+rsync con el mismo patron de secretos que plg-platform-backend.
status: approved
owner: platform
depends_on:
  - specs/000-foundation/dashboard-frontend-foundation-alignment.spec.md
  - specs/000-foundation/dashboard-frontend-coding-style-and-quality-contract.spec.md
  - specs/000-foundation/spec-driven-delivery-and-infrastructure.spec.md
required_runtimes:
  - node-npm-react-cra
required_services: []
required_capabilities:
  - react-cra
targets:
  - ../../dashboard-frontend/.github/workflows/staging.yml
  - ../../dashboard-frontend/.github/workflows/production.yml
  - ../../dashboard-frontend/README.md
  - ../../dashboard-frontend/src/src/deploy.ssh-workflows.test.js
  - ../../specs/features/dashboard-frontend-ssh-deploy-migration.spec.md
slice_mode: minimal-change
surface_policy: required
minimum_valid_completion: staging.yml and production.yml deploy via SSH+rsync using STG_*/PROD_* secrets; FTP action and FTP secrets removed from those workflows; README no longer advertises FTP Deploy Action as the deploy path
validated_noop_allowed: false
acceptable_evidence:
  - workflow YAML no longer references SamKirkland/FTP-Deploy-Action or DEV_/PROD_FTP_*
  - workflow YAML validates secrets STG_/PROD_ SSH_USER + SSH_KEY and vars for HOST/PORT/APP_PATH
  - CI=true npm --prefix src test -- --watchAll=false --testPathPattern=deploy.ssh-workflows
  - python3 ./flow ci spec specs/features/dashboard-frontend-ssh-deploy-migration.spec.md
---

# Dashboard Frontend SSH Deploy Migration

## Governing decision

| Decision | Choice | Prohibited alternatives |
| --- | --- | --- |
| Transport | SSH + `rsync` over OpenSSH key auth | FTP, FTPS, SFTP-via-FTP-Deploy-Action, password-based SSH |
| Secret naming | Same prefixes as `plg-platform-backend` (`STG_*` / `PROD_*`), with sensitivity split: user+key as secrets; host/port/path as variables | Keep `DEV_FTP_*` / `PROD_FTP_*`; invent `DEV_SSH_*`; store host/port/path as secrets |
| Payload | Built CRA output under `src/build/` including `.htaccess` | Sync source tree, `node_modules`, or entire repo |
| Trigger parity | Preserve current branch push triggers (`staging` / `main`) | Convert to SoftOS promotion-PR / `workflow_dispatch` in this slice |
| Remote post-steps | Upload only; no remote artisan/composer/reload | Copy backend remote deploy script |
| SoftOS control-plane | Child-repo workflow ownership; no new root provider wiring | Reintroduce `ftp-bridge` for this app |

Source of truth for the secret contract: `plg-platform-backend/.github/workflows/staging.yml` and `production.yml` prepare-key + rsync steps.

Parity vs correction:

| Behavior | Policy |
| --- | --- |
| Build env (`REACT_APP_*`), Sentry/PostHog secrets | Preserve |
| `.htaccess` materialization from `htaccess.txt` | Preserve |
| Deploy transport FTP | Correct → SSH+rsync |
| Staging secret prefix `DEV_FTP_*` | Correct → secrets `STG_SSH_USER`/`STG_SSH_KEY` + vars `STG_SSH_HOST`/`STG_SSH_PORT`/`STG_APP_PATH` |
| Production secret prefix `PROD_FTP_*` | Correct → secrets `PROD_SSH_USER`/`PROD_SSH_KEY` + vars `PROD_SSH_HOST`/`PROD_SSH_PORT`/`PROD_APP_PATH` |
| Production semantic-release job | Preserve unchanged |

## Context / problem

`dashboard-frontend` still deploys with `SamKirkland/FTP-Deploy-Action` and FTP secrets. `plg-platform-backend` already deploys with SSH key + `rsync`. Operators want one secret pattern and one transport for both repos.

Foundation specs for the dashboard explicitly exclude FTP redesign; this feature spec owns that change.

## Scope

### Includes

- Rewrite deploy steps in `staging.yml` and `production.yml` to SSH+rsync.
- Require and document the backend-aligned secret set.
- Remove FTP action usage and FTP secret validation from those workflows.
- Update `README.md` so it no longer presents FTP Deploy Action as the deploy mechanism.

### Excludes

- Creating or rotating real GitHub secrets/keys (operator action outside git).
- Changing SoftOS root CI / release providers.
- Migrating to promotion-PR deploy templates.
- Changing CRA build, routes, UI, or Node version.
- Remote reload/healthcheck/artisan steps from the backend workflow.
- Deleting unused `DEV_FTP_*` / `PROD_FTP_*` secrets from GitHub UI (optional cleanup after cutover).

## Executable surface inventory

| Surface | Role | Disposition |
| --- | --- | --- |
| `dashboard-frontend/.github/workflows/staging.yml` | Staging deploy write path | Mandatory change |
| `dashboard-frontend/.github/workflows/production.yml` | Production deploy write path | Mandatory change |
| `dashboard-frontend/README.md` | Operator-facing deploy signal | Mandatory change (remove FTP badge/claim) |
| `dashboard-frontend/.github/workflows/repo-ci.yml` | Verify-only CI | Out of scope / do not change |
| `plg-platform-backend/.github/workflows/{staging,production}.yml` | Reference algorithm only | Read-only reference |
| GitHub Actions secrets store | Runtime credentials | Operator provisioning; not in git |

### Technical observed inventory (current → target)

| Item | Current | Target |
| --- | --- | --- |
| Staging trigger | `push` → `staging` | unchanged |
| Production trigger | `push` → `main` | unchanged |
| Staging deploy action | FTP-Deploy-Action + `DEV_FTP_*` | SSH key + `rsync` + `STG_*` |
| Production deploy action | FTP-Deploy-Action + `PROD_FTP_*` | SSH key + `rsync` + `PROD_*` |
| Local artifact | `./src/build/` | unchanged |
| Remote destination | FTP `server-dir` | `STG_APP_PATH` / `PROD_APP_PATH` |

## Secret / variable contract (mandatory)

### Staging secrets

| Name | Store | Purpose |
| --- | --- | --- |
| `STG_SSH_USER` | secret | SSH user |
| `STG_SSH_KEY` | secret | Private key PEM/OpenSSH |

### Staging variables

| Name | Store | Purpose |
| --- | --- | --- |
| `STG_SSH_HOST` | variable | SSH host |
| `STG_SSH_PORT` | variable | SSH port |
| `STG_APP_PATH` | variable | Absolute remote directory for dashboard build files |

### Production secrets

| Name | Store | Purpose |
| --- | --- | --- |
| `PROD_SSH_USER` | secret | SSH user |
| `PROD_SSH_KEY` | secret | Private key PEM/OpenSSH |

### Production variables

| Name | Store | Purpose |
| --- | --- | --- |
| `PROD_SSH_HOST` | variable | SSH host |
| `PROD_SSH_PORT` | variable | SSH port |
| `PROD_APP_PATH` | variable | Absolute remote directory for dashboard build files |

### Preserved non-SSH secrets

- Staging: `DEV_SENTRY_URL`, `DEV_POSTHOG_KEY`, optional `REACT_APP_MAINTENANCE_MODE`
- Production: `PROD_SENTRY_URL`, `PROD_POSTHOG_KEY`, optional maintenance/diagnostic vars

### Forbidden in these workflows after migration

- `DEV_FTP_*`, `PROD_FTP_*`
- `SamKirkland/FTP-Deploy-Action`
- password-based SSH (`sshpass` / interactive password)
- reading host/port/app path from `secrets.*` (must be `vars.*`)
- reading user/key from `vars.*` (must be `secrets.*`)

## Algorithm

### Per-environment deploy algorithm

1. Checkout the push ref (existing).
2. Setup Node LTS/`20` and `npm ci` in `src/` (existing).
3. Validate non-SSH app secrets still required for build (Sentry/PostHog).
4. Validate SSH credentials and connection variables for the environment; fail fast if any empty.
5. Build CRA with existing `REACT_APP_*` env matrix.
6. Materialize `.htaccess` via `mv htaccess.txt ./build/.htaccess`.
7. Write `${{ secrets.*_SSH_KEY }}` to `/tmp/deploy.key` with mode `600`.
8. Build `ssh_opts` identical in spirit to backend:
   `-4 -o ConnectTimeout=20 -o ServerAliveInterval=15 -o ServerAliveCountMax=3 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -i /tmp/deploy.key -p ${SSH_PORT}`
9. Retry up to 3 times: `ssh ... "mkdir -p '${APP_PATH}'"` using `vars.*_SSH_HOST` / `*_SSH_PORT` / `*_APP_PATH` and `secrets.*_SSH_USER`.
10. `rsync -az --delete -e "ssh ${ssh_opts}" ./src/build/ "${SSH_USER}@${SSH_HOST}:${APP_PATH}/"`
11. Do not run remote PHP/Node install steps.
12. Production `release` job (semantic-release) remains independent and unchanged.

### Sequencing constraints

- Build and `.htaccess` must complete before rsync.
- Key materialization must complete before any SSH/rsync step.
- Staging and production workflows are independent; no cross-env ordering.
- Do not edit backend workflows as part of this slice.

## Exception / disposition matrix

| Condition | Disposition | Blocks closure? |
| --- | --- | --- |
| Missing `STG_*` / `PROD_*` SSH secret or variable in GitHub | Workflow fails at validation; operator must provision | Yes for live deploy; no for git merge of workflow if contract is documented |
| SSH connectivity failure | Retry mkdir 3x then fail job | Runtime only |
| Wrong `*_APP_PATH` | Fail or overwrite wrong path; operator must set absolute dashboard webroot | Yes until corrected |
| Leftover FTP secrets in GitHub | Allowed residual debt; remove after cutover | No |
| Desire to adopt promotion-PR SoftOS flow | Deferred to a separate spec | N/A |
| Agent proposes keeping FTP as fallback | Reject | Yes |

## Stop conditions

Stop and escalate if:

- hosting cannot accept SSH key auth;
- remote path isolation for dashboard vs API is unclear (`APP_PATH` would collide with backend tree);
- change requires editing SoftOS root release providers or backend workflows;
- change requires migrating framework/bundler or altering product `REACT_APP_*` URLs.

## Evidence package

| Evidence | Location / form |
| --- | --- |
| Workflows use SSH+rsync with secrets for user/key and vars for host/port/path | Diff of `staging.yml` / `production.yml` |
| No FTP action references remain in deploy workflows | `rg` over those two files returns no FTP Deploy Action / `FTP_*` |
| README no longer advertises FTP deploy badge as mechanism | Diff of `README.md` |
| Spec governance | `python3 ./flow ci spec specs/features/dashboard-frontend-ssh-deploy-migration.spec.md` |
| Optional live proof | Successful staging Actions run after secrets are provisioned (operator) |

### Evidence delivery contract

- Persistent evidence for SoftOS closure: workflow/README diffs + passing `flow ci spec` for this feature.
- Live deploy success is operator evidence after secret provisioning; absence of a live run does not block merging the workflow change when validation steps and secret contract are present.
- No new E2E suite is required; user journeys are unchanged. Relationship to existing CRA tests: deferred/out of scope for this transport-only change.

## Definition of closure / residual debt

Closure is valid when mandatory surfaces match the secret contract and algorithm above.

Allowed residual debt:

- unused FTP secrets still present in GitHub until operator deletes them;
- README may remain otherwise sparse;
- SoftOS promotion-PR adoption remains deferred.

## Acceptance criteria

- Staging and production dashboard deploys authenticate with SSH keys and upload with `rsync --delete`.
- Secret/variable names use `STG_*` / `PROD_*`; only user+key are secrets.
- FTP Deploy Action and FTP secret checks are gone from both workflows.
- Build/`REACT_APP_*` behavior and production semantic-release job are preserved.
- Spec review/CI for this feature pass.

## Test plan

- [@test] ../../dashboard-frontend/src/src/deploy.ssh-workflows.test.js

## Verification Matrix

```yaml
- name: ssh-deploy-workflow-contract
  level: integration
  command: CI=true npm --prefix src test -- --watchAll=false --testPathPattern=deploy.ssh-workflows
  blocking_on: [ci]
  environments: [local, ci]
- name: softos-spec-governance
  level: smoke
  command: python3 ./flow ci spec specs/features/dashboard-frontend-ssh-deploy-migration.spec.md
  blocking_on: [ci]
  environments: [local, ci]
```

## Rollback

Revert the two workflow files (and README) to the previous FTP Deploy Action revision and keep FTP secrets until SSH path is restored.
