# Ejecutores de agentes

English source: [docs/agent-executors.md](../agent-executors.md)

Source: `docs/agent-executors.md`

SoftOS registra harnesses de agentes nativos del host en la sección de nivel superior `agents` de `workspace.config.json`. V1 declara `codex`, `cursor` y `opencode-local`.

## Requisitos previos del host

Instala, autentica y configura cada CLI en el host WSL antes de usar `flow agent run`:

- **Codex CLI** (`codex`): el operador instala y autentica Codex en WSL.
- **Cursor Agent CLI** (`agent`): el operador instala Cursor CLI e inicia sesión en WSL.
- **OpenCode CLI** (`opencode`): el operador instala OpenCode y configura la selección de provider/model en OpenCode mismo.

SoftOS no instala CLIs, no monta credenciales, no valida autenticación ni selecciona models/providers. `flow agent doctor` comprueba únicamente que el ejecutable configurado se resuelve en el host (búsqueda en `PATH` o un archivo ejecutable con ruta absoluta). Un estado `ready` no significa que las credenciales sean válidas.

## Host WSL vs control plane Docker

Las CLIs de harness de agentes siempre se ejecutan en el host WSL, nunca dentro del contenedor del workspace.

| Familia de comandos | Dónde se ejecuta |
| --- | --- |
| `python3 ./flow agent ...` | Host WSL |
| `scripts/workspace_exec.sh python3 ./flow <command>` | Contenedor del workspace (control plane) |
| `python3 ./flow repo exec <repo> --workdir <worktree> -- <command>` | Runtime del repositorio en el contenedor |
| `python3 ./flow stack <command>` | Ciclo de vida Docker desde el host |

Las instrucciones del runtime del repositorio están embebidas en el contrato de ejecución de SoftOS entregado a cada harness. SoftOS no ejecuta comandos de build/test del repositorio en el host en nombre de un agente.

## Comandos

Ejecuta estos en el host WSL (no se proxyan al contenedor del workspace):

```bash
python3 ./flow agent list
python3 ./flow agent doctor
python3 ./flow agent doctor codex
python3 ./flow agent run <executor> --repo <repo> --workdir <path> --prompt "<text>" --target <path>
```

### Ejemplos

```bash
# Listar ejecutores configurados
python3 ./flow agent list

# Comprobar si los ejecutables del host se resuelven
python3 ./flow agent doctor

# Ejecutar Codex contra un worktree con un archivo target
python3 ./flow agent run codex \
  --repo softos-agentic \
  --workdir /path/to/worktree \
  --prompt "Implement the requested change" \
  --target src/example.py

# Ejecutar Cursor Agent CLI en la raíz del repo
python3 ./flow agent run cursor \
  --repo workspace-root \
  --workdir /path/to/repo \
  --prompt "Review the diff" \
  --target .

# Ejecutar OpenCode localmente (provider/model provienen de la config de OpenCode)
python3 ./flow agent run opencode-local \
  --repo softos-agentic \
  --workdir /path/to/worktree \
  --prompt "Add tests for the adapter" \
  --target flowctl/agent_executor_adapters.py
```

- `agent list` valida el registro e imprime el id, adapter y ejecutable configurado de cada executor en orden lexicográfico.
- `agent doctor` resuelve ejecutables mediante el `PATH` del host (o comprueba rutas absolutas) e informa `ready` o `missing`. No inspecciona credenciales, no llama APIs del vendor ni demuestra que la autenticación funciona.
- `agent run` valida los límites de repo/worktree/target, prefija el prompt del operador con el contrato de ejecución de SoftOS, invoca el ejecutable configurado con una secuencia argv (`shell=False`), captura stdout/stderr y devuelve el exit code exacto del proceso hijo. No persiste prompts, salida capturada, valores de entorno ni argv renderizado.

El resto de comandos `flow` normales siguen siendo solo del workspace.

## Formas de comando del adapter

SoftOS construye argv de forma determinista a partir de la entrada del registro. Los valores estáticos de `executor.argv` se validan con una política conservadora de allow-by-known-safe-options antes del lanzamiento; los arrays `argv` vacíos son canónicos en V1. Los tokens estructurales inseguros (subcomandos, `--help`, `--version`, `--`, flags propiedad del adapter, flags de enrutamiento model/provider y texto posicional) se rechazan de forma determinista y nunca se repiten en los diagnósticos.

El contrato de ejecución completo de SoftOS más el prompt del usuario sin cambios es siempre un elemento argv final discreto (`<PROMPT>` abajo). Las CLIs con prompt posicional usan el delimitador de fin de opciones `--` soportado por el parser para que los marcadores del contrato que empiezan por `---` no se interpreten como flags.

| Adapter | Ejecutable del registro | forma argv |
| --- | --- | --- |
| `codex` | `codex` | `codex [<validated static argv>] exec --approve-for-me -- <PROMPT>` |
| `cursor` | `agent` | `agent [<validated static argv>] --trust -p -- <PROMPT>` |
| `opencode` | `opencode` | `opencode [<validated static argv>] run --auto -- <PROMPT>` |

SoftOS nunca añade `--model`, `--provider`, `--full-auto` ni flags similares de enrutamiento del vendor. No se admite argv estático arbitrario; solo opciones globales revisadas explícitamente que no alteren la semántica de ejecución propiedad del adapter pueden estar en la allowlist por adapter. El `cwd` del subproceso es el workdir validado; los adapters no crean worktrees ni ejecutan Docker.

### Política de argv estático (V1)

- Las entradas canónicas del registro usan `"argv": []`.
- SoftOS valida argv estático antes de construir la invocación final y rechaza tokens inseguros en lugar de descartarlos o reordenarlos en silencio.
- Las categorías rechazadas incluyen subcomandos (`exec`, `run`), flags de help/version, `--`, flags de aprobación/trust/prompt/auto propiedad del adapter, flags de selección model/provider y argumentos posicionales.
- Los diagnósticos nombran solo el adapter y la clase de fallo; nunca se repiten valores argv que contengan secretos.

## Forma del registro

```json
{
  "agents": {
    "schema_version": 1,
    "executors": {
      "codex": {"adapter": "codex", "executable": "codex", "argv": []},
      "cursor": {"adapter": "cursor", "executable": "agent", "argv": []},
      "opencode-local": {"adapter": "opencode", "executable": "opencode", "argv": []}
    }
  }
}
```

Los campos inválidos del registro terminan con exit distinto de cero y un diagnóstico específico del campo.

## Solución de problemas

| Síntoma | Causa probable | Qué comprobar |
| --- | --- | --- |
| `doctor` informa `missing` | El ejecutable no está en el `PATH` del host o la ruta absoluta no es ejecutable | Instala la CLI en WSL; confirma `which codex` / `which agent` / `which opencode` |
| `doctor` está `ready` pero la ejecución falla dentro de la CLI del vendor | Autenticación o configuración del vendor | Vuelve a autenticarte fuera de SoftOS; SoftOS no valida credenciales |
| `Executor desconocido` | Error tipográfico en el ID del registro | `flow agent list` |
| Errores de workdir/target | Ruta fuera del repo/worktree asignado | Usa la raíz de un repo registrado o un Git worktree; mantén los targets dentro del workdir |
| Exit distinto de cero con stdout/stderr | El harness hijo falló | Inspecciona los streams reenviados; SoftOS devuelve el exit code exacto del proceso hijo |
| Comando del control plane bloqueado en el host | Los comandos `flow` que no son de agent son solo del workspace | Usa `scripts/workspace_exec.sh python3 ./flow <command>` |

## Verificación

```bash
scripts/workspace_exec.sh python3 ./flow ci integration --profile agent-executors --json
```
