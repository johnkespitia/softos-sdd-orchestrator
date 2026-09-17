---
schema_version: 3
id: softos-harness-core-and-profiles
name: "SoftOS Harness Core and Profiles"
description: "Separar las políticas reutilizables del harness de los perfiles específicos de cada proyecto y validar su contrato sin dependencias externas."
status: approved
owner: softos-harness
slice_mode: minimal-change
surface_policy: required
single_slice_reason: "El contrato ya está implementado; el cierre restante es validación y gobernanza del pack reutilizable."
depends_on:
  - ../../specs/000-foundation/spec-as-source-operating-model.spec.md
  - ../../specs/000-foundation/spec-driven-delivery-and-infrastructure.spec.md
required_runtimes:
  - python
required_services: []
required_capabilities: []
targets:
  - ../../policies/harness-core/**
  - ../../profiles/**
  - ../../scripts/harness/validate_profile.py
  - ../../scripts/harness/usage_report.py
  - ../../docs/harness-core-and-profiles.md
  - ../../docs/es/harness-core-and-profiles.es.md
  - ../../specs/features/softos-harness-core-and-profiles.spec.md
test_refs:
  - ../../scripts/harness/validate_profile.py
  - ../../scripts/harness/usage_report.py
---

# SoftOS Harness Core and Profiles

## Summary

Separate reusable Harness Core policies from project-specific profiles so the
pattern can be adopted across projects without hardcoding private conventions.

## Problem

Delivery harnesses often combine generic gates with local details such as label
names, deploy flows, E2E commands, ticket systems, and communication surfaces.
That makes reuse difficult and risks leaking private project context.

## Goals

- Define project-neutral core policies.
- Define a profile contract for project-specific conventions.
- Provide a generic open-source-safe example profile.
- Provide a stdlib-only validator for core/profile structure.
- Keep external writes dry-run-first unless a profile explicitly enables them.

## Non-Goals

- Do not include private repository names, ticket links, channel links,
  credentials, or organization-specific deploy commands in the core package.
- Do not require every project to use the same ticket system, PR labels, E2E
  runner, or communication tool.

## Slices

1. `harness-core-policy-pack`
2. `harness-profile-contract`
3. `example-api-ticket-profile`
4. `harness-profile-validator`
5. `opensource-adoption-docs`

## Slice Breakdown

```yaml
- name: harness-core-profile-governance-closeout
  repo: plg-platform-harness
  targets:
    - ../../policies/harness-core/**
    - ../../profiles/**
    - ../../scripts/harness/validate_profile.py
    - ../../scripts/harness/usage_report.py
    - ../../docs/harness-core-and-profiles.md
    - ../../docs/es/harness-core-and-profiles.es.md
    - ../../specs/features/softos-harness-core-and-profiles.spec.md
  hot_area: harness-core/profile-contract
  slice_mode: minimal-change
  surface_policy: required
  minimum_valid_completion: "Validator y compilacion pasan; perfil de ejemplo y politicas core cumplen el contrato; spec aprobada con evidencia."
  validated_noop_allowed: true
  acceptable_evidence:
    - "python3 scripts/harness/validate_profile.py --root . --json devuelve status ok"
    - "python3 -m py_compile scripts/harness/validate_profile.py scripts/harness/usage_report.py"
```

## Validation Plan

- Run `python3 scripts/harness/validate_profile.py --root . --json`.
- Confirm core policies have no obvious project-private terms.
- Confirm the example profile loads and declares required gates.
- Confirm profile automation is dry-run-first.

## Open Questions

None

## Scope

Includes the reusable policy pack, the profile contract, the example profile,
the stdlib-only validator, usage reporting, and the English/Spanish adoption
documentation. It does not include private project credentials, repository
automation, provider integrations, or external writes.

## Acceptance Criteria

- All required Harness Core policy documents exist and contain no forbidden
  project-private terms.
- The example profile extends `policies/harness-core` and declares gates R1-R5.
- Profile automation is dry-run-first and usage telemetry is fully declared.
- `python3 scripts/harness/validate_profile.py --root . --json` returns
  `status: ok`.
- `python3 -m py_compile scripts/harness/validate_profile.py scripts/harness/usage_report.py`
  passes.

## Closeout Contract

This is a governance and validation slice. No product route, UI, or external
service is required. Minimum valid completion is a passing validator, passing
Python compilation, complete targets, and an approved spec with CI evidence.
