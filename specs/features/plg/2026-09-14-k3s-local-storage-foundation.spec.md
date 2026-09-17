---
schema_version: 2
name: "PLG K3s local storage foundation"
description: "Define una StorageClass local retenida para datos persistentes de PLG sin introducir object storage externo."
status: draft
owner: platform
depends_on:
  - ../../specs/000-foundation/spec-as-source-operating-model.spec.md
  - ../../specs/000-foundation/spec-driven-delivery-and-infrastructure.spec.md
required_runtimes: []
required_services: []
required_capabilities: []
targets:
  - ../../specs/features/plg/2026-09-14-k3s-local-storage-foundation.spec.md
  - ../../scripts/infra/k3s/storage/README.md
  - ../../scripts/infra/k3s/storage/storage-class.yaml
infra_targets:
  - ../../scripts/infra/k3s/storage/**
test_refs: []
---

# PLG K3s local storage foundation

## Objetivo

Preparar una capa declarativa de almacenamiento local para el clúster K3s de
PLG, adecuada para el VPS actual y compatible con la restricción de no
contratar object storage externo.

## Contexto actual

- VPS Hostinger `srv1954283`, un solo nodo, 8 vCPU, 31 GiB de RAM y 387 GiB de
  almacenamiento principal.
- K3s `v1.36.4+k3s1` está instalado como control plane y worker.
- El provisionador incluido `local-path` usa
  `/var/lib/rancher/k3s/storage` y tiene `reclaimPolicy: Delete`.
- No existen todavía aplicaciones, bases de datos, PVCs ni datos migrados en
  el clúster.
- WordPress, PLG y los futuros servicios de IA deben conservar sus datos en
  volúmenes persistentes locales durante esta fase.

## Alcance

### Incluye

- Una StorageClass llamada `plg-local-retain`.
- Política `Retain` para que la eliminación de un PVC no borre
  automáticamente los datos del volumen.
- Provisionador `kubernetes.io/no-provisioner` para que los PV locales sean
  declarados explícitamente y queden bajo control de IaC.
- Modo `WaitForFirstConsumer` para que el binding respete la afinidad del nodo.
- Documentación del uso previsto y de las rutas futuras bajo `/srv/plg-data`.

### No incluye

- Crear o modificar la StorageClass predeterminada `local-path`.
- Crear PersistentVolumes o PersistentVolumeClaims de aplicaciones.
- Crear directorios en el VPS.
- Instalar MySQL, Redis, WordPress o aplicaciones PLG.
- Migrar datos o backups.
- Introducir S3, R2, Backblaze u otro object storage.
- Configurar alta disponibilidad o almacenamiento compartido entre nodos.

## Invariantes

1. Ninguna aplicación stateful de producción usará la StorageClass
   `local-path` con `Delete` sin una decisión explícita posterior.
2. La nueva StorageClass no será default, para evitar que una aplicación la
   use accidentalmente.
3. Los PV de aplicaciones futuras deberán declarar `local` y `nodeAffinity`
   hacia el nodo donde reside el dato.
4. Los datos persistentes de PLG se organizarán bajo `/srv/plg-data`, pero las
   rutas físicas se crearán en una slice posterior y versionada.
5. Esta configuración no abrirá puertos ni modificará Cloudflare, UFW o el
   firewall administrado de Hostinger.

## Contrato observable

La aplicación de `../../infra/k3s/storage/storage-class.yaml` debe producir:

```text
NAME              PROVISIONER                    RECLAIMPOLICY
plg-local-retain  kubernetes.io/no-provisioner    Retain
```

La StorageClass existente `local-path` debe conservarse como default sin
modificaciones en esta slice.

## Criterios de aceptación

- El manifiesto pasa una validación server-side con el API de Kubernetes.
- `plg-local-retain` existe con `reclaimPolicy: Retain`.
- `plg-local-retain` no tiene la anotación de StorageClass default.
- No se crean PVs, PVCs, deployments ni servicios en esta slice.
- El manifiesto y la spec pasan `git diff --check` y la revisión de spec del
  workspace.

## Stop conditions

- Detenerse si la StorageClass default actual cambia durante la validación.
- No aplicar ningún PVC de aplicación hasta definir su PV, ruta física,
  capacidad, afinidad de nodo y backup asociado.
- No editar directamente el ConfigMap administrado por el addon
  `local-path`.

## Slice breakdown

```yaml
- name: local-retain-storage-class
  repo: plg-platform-harness
  targets:
    - ../../scripts/infra/k3s/storage/storage-class.yaml
    - ../../scripts/infra/k3s/storage/README.md
  hot_area: k3s persistent storage policy
  depends_on: []
  slice_mode: implementation-heavy
  surface_policy: required
  minimum_valid_completion: declarative StorageClass Retain validada sin modificar la default ni crear workloads
  validated_noop_allowed: false
  acceptable_evidence:
    - server-side dry-run exitoso
    - StorageClass observada con provisioner y reclaimPolicy esperados
    - diff check y spec review exitosos
```

## Verification Matrix

```yaml
- name: manifest-server-dry-run
  level: custom
  command: sudo k3s kubectl apply --dry-run=server -f scripts/infra/k3s/storage/storage-class.yaml
  blocking_on: [ci]
  environments: [staging]

- name: storage-class-observation
  level: custom
  command: sudo k3s kubectl get storageclass plg-local-retain -o yaml
  blocking_on: [review]
  environments: [staging]

- name: workspace-spec-review
  level: custom
  command: python3 ./flow workspace exec -- python3 ./flow spec review specs/features/plg/2026-09-14-k3s-local-storage-foundation.spec.md --json
  blocking_on: [approval]
  environments: [local]

- name: workspace-diff-check
  level: custom
  command: git diff --check
  blocking_on: [ci]
  environments: [local]
```

## Rollout

1. Revisar y aprobar esta spec.
2. Validar el manifiesto contra el API server de staging.
3. Aplicar la StorageClass en el nodo K3s actual.
4. Observar que la StorageClass default original no cambió.
5. Definir en slices posteriores los PV/PVC de WordPress, PLG y backups.

## Rollback

Mientras no existan PVCs que la utilicen, retirar el manifiesto y eliminar
`plg-local-retain`. Una vez que existan claims, el rollback requerirá una
decisión explícita para no poner datos persistentes en riesgo.
