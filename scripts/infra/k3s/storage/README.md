# PLG local storage

Esta carpeta contiene la política declarativa para datos persistentes locales
del clúster K3s de PLG.

## StorageClass

`storage-class.yaml` define `plg-local-retain` con:

- `kubernetes.io/no-provisioner`: los PersistentVolumes se declaran
  explícitamente y no se crean dinámicamente por accidente.
- `Retain`: borrar un claim no solicita el borrado automático del volumen.
- `WaitForFirstConsumer`: el binding respeta la ubicación del nodo.
- no es la StorageClass default.

## Rutas previstas

Las rutas físicas se crearán en una slice posterior, cuando conozcamos los
requerimientos reales de cada aplicación:

```text
/srv/plg-data/
├── production/
├── staging/
├── wordpress/
├── backups/
└── ai-models/
```

Cada PV futuro deberá usar un volumen local, declarar `nodeAffinity` para el
nodo K3s y tener un backup asociado. Esta StorageClass por sí sola no crea
directorios, PVs ni PVCs.
