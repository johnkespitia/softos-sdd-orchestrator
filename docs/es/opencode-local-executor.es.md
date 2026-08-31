# Ejecutor local de OpenCode para SoftOS

> English source: [OpenCode Local Executor](../opencode-local-executor.md)

## 1. Propósito

Este documento registra la configuración local actual de OpenCode utilizada para preparar `opencode-local` como ejecutor de implementación de SoftOS. Explica los límites de responsabilidad, la disposición de conectividad entre Windows y WSL, el worker dedicado de OpenCode, la evidencia recopilada durante el diagnóstico, la integración actual con SoftOS y el trabajo pendiente.

El objetivo es proporcionar una ruta local y acotada de programación para asignaciones que normalmente tardan minutos, no una ruta de chat de un segundo. Los cambios redujeron el contexto innecesario de OpenCode y el comportamiento de agente genérico, a la vez que preservaron una regla arquitectónica estricta: SoftOS selecciona un ejecutor/harness, pero no selecciona ni codifica un proveedor o modelo de OpenCode.

Esta es documentación operativa y de configuración. Los archivos de OpenCode y del shell descritos a continuación se encuentran fuera del repositorio y deben administrarse por separado en cada estación de trabajo.

## 2. Arquitectura y límites de responsabilidad

```text
SoftOS
  ↓
opencode-local
  ↓
OpenCode
  ↓
softos-local-worker
  ↓
LM Studio
  ↓
local model
```

Las capas tienen responsabilidades deliberadamente separadas:

| Capa | Responsabilidad |
| --- | --- |
| SoftOS | Seleccionar el ejecutor, definir el repositorio/worktree/targets, entregar el contrato y los límites de la asignación, y verificar los resultados de forma determinista. |
| OpenCode | Operar el harness y administrar sus agentes/perfiles, incluido el worker acotado que se utiliza para las asignaciones de SoftOS. |
| Configuración de OpenCode/LM Studio | Seleccionar el proveedor, el modelo, el endpoint y los parámetros del modelo/runtime. |
| LM Studio | Servir el modelo local mediante su API compatible con OpenAI. |

SoftOS debe seguir siendo agnóstico respecto del proveedor y el modelo. El modelo Granite seleccionado actualmente es responsabilidad de OpenCode/LM Studio y no forma parte del contrato del registro de ejecutores de SoftOS.

## 3. Entorno

La topología validada es la siguiente:

- LM Studio se ejecuta en Windows y expone una API compatible con OpenAI en `http://127.0.0.1:1234/v1`.
- SoftOS y OpenCode se ejecutan en WSL.
- WSL utiliza redes en modo reflejado para que el servicio de Windows sea accesible desde WSL mediante la dirección estable de loopback.
- OpenCode lee su configuración global y las definiciones de agentes desde `~/.config/opencode/`.
- El entorno persistente del shell de WSL proporciona `LM_STUDIO_BASE_URL` mediante `~/.bashrc`.

Ninguna dirección dinámica de host `172.x.x.x` forma parte de la configuración. Esas direcciones dependen del entorno y no deben utilizarse como endpoint duradero.

## 4. Conectividad de WSL → LM Studio

El endpoint utilizado inicialmente desde WSL era `http://host.docker.internal:1234/v1`. Esa ruta produjo fallos de conectividad y contribuyó a que una ejecución anterior de `opencode-local` se detuviera sin generar salida.

Posteriormente, WSL se configuró en Windows mediante `%USERPROFILE%\.wslconfig`:

```ini
[wsl2]
networkingMode=mirrored
```

Después de reiniciar WSL, `127.0.0.1:1234` pasó a ser accesible directamente desde WSL. La variable persistente del shell en `~/.bashrc` ahora es:

```bash
export LM_STUDIO_BASE_URL="http://127.0.0.1:1234/v1"
```

La inspección actual confirmó tanto ese valor en `~/.bashrc` como una respuesta correcta de `GET http://127.0.0.1:1234/v1/models`. La respuesta anunció `granite-4.1-8b` y un modelo de embeddings.

Para reconstruir esta configuración en otra estación de trabajo, configure las redes en modo reflejado en el archivo `.wslconfig` del lado de Windows, reinicie WSL, exponga LM Studio en el puerto `1234` y establezca la variable de entorno de WSL. No copie una IP transitoria de puente de WSL o Windows.

## 5. Configuración global de OpenCode

La configuración global es `~/.config/opencode/opencode.json`. La inspección actual estableció los siguientes ajustes no secretos:

- ID del proveedor: `lmstudio`;
- implementación del proveedor: `@ai-sdk/openai-compatible`;
- URL base del proveedor: `{env:LM_STUDIO_BASE_URL}`;
- ID del modelo configurado: `lmstudio/granite-4.1-8b`;
- el agente genérico `build` tiene actualmente `steps: 8` y `temperature: 0.1`.

El endpoint se resuelve desde el entorno en lugar de duplicarse en el repositorio. El proveedor y el modelo pertenecen intencionalmente a OpenCode/LM Studio. Ninguno aparece en el esquema de ejecutores de SoftOS.

La ventana de contexto inicial de Granite era de 8,192 tokens. OpenCode falló con:

```text
request (...) exceeds available context size (8192 tokens)
```

Luego se aumentó el contexto de runtime de Granite en LM Studio a aproximadamente 16K, tras lo cual se completó una llamada local de OpenCode. Esta configuración de contexto pertenece a LM Studio y no está representada en el repositorio.

No publique la configuración completa de la estación de trabajo cuando contenga credenciales o proveedores no relacionados. Los valores anteriores son los datos mínimos relevantes y no secretos para reconstruirla.

## 6. `softos-local-worker` dedicado

El agente genérico `build` de OpenCode no era adecuado como worker canónico de SoftOS. Una respuesta mínima sin herramientas tardó aproximadamente 22.04 segundos en una ejecución dentro del repositorio; una ejecución anterior invocó WebFetch innecesariamente y una ejecución desde `/tmp/opencode-bench` tardó aproximadamente 98.40 segundos. También llevaba bastante más contexto en el prompt, que llegó a unos 10.5K tokens de solicitud en la medición anterior.

Por lo tanto, existe un agente primario dedicado llamado `softos-local-worker` en:

```text
~/.config/opencode/agents/softos-local-worker.md
```

Inicialmente era local al proyecto y se encontraba en `.opencode/agents/softos-local-worker.md`. Los Git worktrees de SoftOS no detectaban esa definición de forma confiable, por lo que se trasladó al directorio global de agentes de OpenCode. La salida actual de `opencode agent list` identifica `softos-local-worker (primary)` tanto desde el workspace principal como desde un checkout existente en `.worktrees/**`.

Las instrucciones del worker le exigen:

- seguir únicamente la asignación explícita del supervisor;
- modificar solo los archivos autorizados explícitamente y evitar ampliar el alcance;
- evitar la navegación web y la delegación a subagentes;
- evitar planes, commits, pushes, pull requests, merges y releases;
- preferir el cambio suficiente más pequeño y comprobaciones locales específicas;
- detenerse e informar los bloqueos causados por falta de contexto, entorno, permisos, problemas de plataforma o requisitos fuera del alcance;
- devolver un resumen conciso de los cambios y la verificación.

El front matter actual del agente declara `steps: 6`. Permite explícitamente `read`, `edit`, `glob`, `grep`, `list` y `bash`, y deniega explícitamente `task`, `webfetch`, `websearch`, `todowrite`, `skill` y `question`.

Hay un matiz importante del runtime: `opencode agent list` informa entradas de permisos combinadas, incluidas reglas heredadas en el nivel de OpenCode/proyecto, como un permiso comodín inicial, seguidas de las reglas explícitas de permiso/denegación del worker. La intención y las reglas explícitas del archivo del worker están verificadas, pero este documento no infiere semánticas de precedencia no documentadas a partir de esa lista combinada. Cuando el cumplimiento de permisos sea crítico para la seguridad, valide el comportamiento con la versión instalada de OpenCode en lugar de confiar únicamente en el front matter.

## 7. Validación y benchmarks

Durante la configuración y el diagnóstico se recopilaron las siguientes mediciones:

| Prueba | Resultado |
| --- | --- |
| `POST /v1/chat/completions` directo a LM Studio | `RAW_LM_OK`, ~1.02 s |
| Ejecución del `build` genérico de OpenCode | `OPENCODE_LOCAL_OK`, ~22.04 s |
| `build` de OpenCode desde `/tmp/opencode-bench` | ~98.40 s |
| Primera ejecución del worker local | ~39.84 s |
| Ejecución en caliente del worker local | ~12.55 s |
| Ejecución instrumentada del worker local | ~10.26 s |
| Tokens totales instrumentados | 5,143 |
| Tokens de entrada instrumentados | 5,138 |
| Tokens de salida instrumentados | 5 |
| Tokens de razonamiento instrumentados | 0 |
| Escritura/lectura de caché instrumentada | 0 / 0 |

El resultado instrumentado del worker es considerablemente menor que la solicitud de aproximadamente 10.5K tokens observada con la ruta anterior del agente genérico. Estos valores son evidencia de diagnóstico de ejecuciones concretas, no un SLA ni una garantía para tareas futuras. El costo de arranque, el contexto del repositorio, el tamaño del prompt, el uso de herramientas, el estado de la máquina y la versión de OpenCode pueden cambiar el resultado.

La finalización directa en ~1.02 segundos demuestra que LM Studio y Granite no eran la principal causa de la demora de extremo a extremo, mucho mayor, en esa comparación. El tiempo restante se consumió predominantemente en la ruta de OpenCode, incluido el arranque y el procesamiento del contexto/harness.

## 8. Integración del ejecutor de SoftOS

El registro actual de `workspace.config.json` contiene exactamente tres ejecutores:

| Ejecutor | Adaptador | Ejecutable | `argv` estático |
| --- | --- | --- | --- |
| `codex` | `codex` | `codex` | `[]` |
| `cursor` | `cursor` | `agent` | `[]` |
| `opencode-local` | `opencode` | `opencode` | `[]` |

El esquema del registro en `flowctl/agent_executors.py` acepta únicamente `adapter`, `executable` y `argv` para un ejecutor. No tiene ningún campo para el modelo, el proveedor o el perfil de OpenCode.

El `OpenCodeAdapter` actual en `flowctl/agent_executor_adapters.py` construye el equivalente de:

```text
opencode run --auto --dir <workdir> -- <delivered-prompt>
```

El registro de ejecutores no codifica por sí mismo un agente/perfil de OpenCode. Sin embargo, la selección de `softos-local-worker` se ha **validado mediante configuración por proceso** al pasar `OPENCODE_CONFIG_CONTENT='{"default_agent":"softos-local-worker"}'` al entorno heredado por `flow agent run`. Esto mantiene a SoftOS agnóstico respecto del proveedor/modelo y, a la vez, permite que OpenCode sea responsable de seleccionar el worker.

Añadir `--agent` mediante `executor.argv` no es una solución actual. Las opciones estáticas de OpenCode están restringidas deliberadamente y `_build_positional_prompt_argv` coloca los argumentos estáticos validados antes de la cola controlada por el adaptador. El adaptador no se ha modificado para seleccionar el worker.

Esto preserva el límite de abstracción correcto, pero deja sin resolver la selección final del perfil del harness.

## 9. Validación operativa

Ejecute estas comprobaciones desde WSL. Son comandos de diagnóstico; la ejecución de OpenCode invoca el modelo local, pero no debería editar archivos porque el prompt prohíbe explícitamente el uso de herramientas.

Compruebe el endpoint de LM Studio sin utilizar una IP dinámica:

```bash
curl http://127.0.0.1:1234/v1/models
```

Confirme que OpenCode detecta el worker global, tanto en el checkout principal como desde un Git worktree de SoftOS:

```bash
opencode agent list
```

Ejercite directamente el worker dedicado:

```bash
opencode run --agent softos-local-worker \
  "Do not use any tools. Reply only with: OPENCODE_LOCAL_OK"
```

Confirme que el registro de SoftOS sigue conteniendo únicamente ejecutores:

```bash
python3 ./flow agent list --json
```

La evidencia esperada es: la lista de modelos de LM Studio incluye Granite; la lista de agentes incluye `softos-local-worker (primary)`; la ejecución directa devuelve únicamente `OPENCODE_LOCAL_OK`; y la lista de SoftOS muestra `codex`, `cursor` y `opencode-local` sin datos del proveedor ni del modelo.

## 10. Solución de problemas

### Conexión rechazada o timeout con LM Studio

Confirme que LM Studio se está ejecutando en Windows, que su servidor local está iniciado en el puerto `1234` y que `curl http://127.0.0.1:1234/v1/models` funciona desde WSL. Inspeccione `LM_STUDIO_BASE_URL` en el shell activo y el export persistente en `~/.bashrc`. Un archivo del shell modificado no afecta a un shell que ya está en ejecución hasta que se recargue o reinicie.

### `host.docker.internal` frente a localhost

El endpoint `host.docker.internal` utilizado anteriormente no era confiable en esta ruta de WSL. Con las redes en modo reflejado de WSL configuradas y WSL reiniciado, utilice `http://127.0.0.1:1234/v1`. No lo sustituya por una dirección `172.x.x.x` detectada; eso volvería a introducir una dependencia transitoria.

### Desbordamiento del contexto de 8,192 tokens

Si OpenCode informa que la solicitud supera los 8,192 tokens, inspeccione el runtime de Granite cargado en LM Studio y asegúrese de que su contexto sea de aproximadamente 16K o lo bastante grande para la solicitud real. Cambiar el registro de SoftOS no es la solución: el tamaño del contexto es responsabilidad del runtime del modelo/LM Studio. Mantenga también acotada la asignación del worker para evitar entradas innecesarias.

### El worker no aparece desde un worktree

Ejecute `opencode agent list` desde el worktree. La definición canónica de la estación de trabajo debe existir en `~/.config/opencode/agents/softos-local-worker.md`, no solo en `.opencode/agents/` del checkout principal. Un archivo de agente local al proyecto no es suficiente para los Git worktrees hermanos.

### OpenCode utiliza `build` en lugar de `softos-local-worker`

Para una llamada directa de diagnóstico, pase `--agent softos-local-worker` o utilice el wrapper validado `opencode-softos`. La ruta real de SoftOS también se ha validado con `OPENCODE_CONFIG_CONTENT` heredado: `flow agent run → opencode-local → OpenCodeAdapter → softos-local-worker → LM Studio → local model`.

### Las ejecuciones de OpenCode son lentas

Compare ejecuciones en caliente y en frío equivalentes, registre el tiempo transcurrido y el número de tokens, y compruebe si se invocaron herramientas. La primera ejecución del worker fue más lenta que las posteriores. El arranque de OpenCode, la carga de la configuración, las instrucciones del repositorio, la construcción del prompt y el comportamiento del harness pueden dominar una finalización pequeña.

### Diferenciar el rendimiento de LM Studio de la sobrecarga de OpenCode

Primero envíe una solicitud mínima directa de `POST /v1/chat/completions` a LM Studio y luego ejecute un prompt equivalente sin herramientas mediante OpenCode. Una finalización directa rápida y una finalización lenta de OpenCode apuntan a una sobrecarga del harness/arranque/contexto, no solo a la inferencia del modelo. La comparación registrada fue de ~1.02 segundos de forma directa, frente a ~22.04 segundos mediante el `build` genérico y ~10.26 segundos para el worker dedicado instrumentado.

## 11. Limitaciones conocidas

- OpenCode aún tiene una sobrecarga medible de arranque y carga de contexto.
- El benchmark instrumentado informó una escritura de caché de `0` y una lectura de caché de `0`; en esa ejecución no se demostró ningún beneficio de caché.
- El registro de ejecutores no codifica permanentemente `softos-local-worker`; la selección del worker está validada actualmente mediante configuración por proceso o mediante el wrapper `opencode-softos` de la estación de trabajo.
- `flow agent run` no proporciona actualmente un mecanismo canónico de timeout/cancelación.
- La detección del agente demuestra su disponibilidad, no que el adaptador actual de SoftOS haya seleccionado ese agente.
- El agente global de OpenCode y la configuración del shell/proveedor son estado de la estación de trabajo fuera del repositorio y deben reconstruirse por separado.
- Estos cambios de ejecutor no constituyen el futuro mecanismo duradero de estado del orquestador. El cableado de selección/perfil del ejecutor y el estado duradero de orquestación son asuntos independientes.

## 12. Integración pendiente

La decisión de diseño pendiente es cómo hacer que el mecanismo de selección del worker ya validado sea permanente y canónico para los procesos de `opencode-local` lanzados por SoftOS, sin cambiar el comportamiento interactivo normal de OpenCode.

Una opción candidata es una sobrescritura de configuración por proceso:

```bash
OPENCODE_CONFIG_CONTENT='{"default_agent":"softos-local-worker"}'
```

**Esta sobrescritura por proceso está validada.** Se ha probado directamente con OpenCode y mediante la ruta real de `flow agent run`. Todavía no está codificada como configuración permanente de SoftOS en el nivel del repositorio.

El diseño final puede ser:

- una sobrescritura de configuración por proceso;
- un ejecutable wrapper dedicado a `opencode-local`;
- una capacidad explícita del adaptador que permanezca orientada a perfiles y sea agnóstica respecto del proveedor/modelo;
- otro mecanismo equivalente que preserve el límite de responsabilidad.

El mecanismo elegido debe probarse mediante la ruta real de `flow agent run`, desde un worktree de SoftOS, y debe demostrar que únicamente `opencode-local` selecciona el worker. No debe añadir campos de proveedor o modelo a SoftOS.

Posteriormente se intentó la repetición de Orchestrator V0 con Codex como supervisor, `opencode-local` como implementador, un revisor independiente y un presupuesto máximo de una reparación. La ejecución llegó al implementador mediante la ruta canónica de `flow agent run`, pero terminó con estado `BLOCKED` antes de la verificación determinista. Un diagnóstico posterior de solo lectura sobre el uso de herramientas se completó correctamente, lo que confirmó que OpenCode podía utilizar `glob` y `read`, recuperarse de una ruta inicialmente incorrecta y encontrar `command_repo_exec`. Ese diagnóstico tardó aproximadamente 75 segundos con unos 8.7K tokens de entrada, lo que indica que los periodos largos sin salida pueden deberse a la latencia del harness/modelo y no a un bloqueo definitivo de las llamadas a herramientas.

## 13. Lista de comprobación de aceptación

- [x] LM Studio es accesible desde WSL mediante localhost.
- [x] `LM_STUDIO_BASE_URL` persiste en `~/.bashrc` como `http://127.0.0.1:1234/v1`.
- [x] Granite responde directamente mediante la API de LM Studio compatible con OpenAI.
- [x] Granite dispone de contexto suficiente para la llamada local validada de OpenCode (aproximadamente 16K configurados en LM Studio).
- [x] OpenCode reconoce `softos-local-worker`.
- [x] `softos-local-worker` es visible desde un Git worktree.
- [x] Funciona una llamada directa con `--agent softos-local-worker`.
- [x] El registro de SoftOS sigue siendo agnóstico respecto del modelo/proveedor.
- [x] Se ha validado un mecanismo por proceso de selección de SoftOS → `softos-local-worker` mediante la ruta real de `flow agent run`.
- [x] El wrapper `opencode-softos` está validado como mecanismo de selección del worker en el nivel de la estación de trabajo.
- [ ] Está definido el cableado permanente en el nivel del repositorio para seleccionar el worker.
- [ ] La repetición de Orchestrator V0 alcanza la verificación determinista y la revisión independiente sin un bloqueo de plataforma.

Los elementos marcados combinan la inspección actual de archivos/comandos con la evidencia de validación registrada anteriormente. Los dos elementos no marcados están intencionalmente pendientes y no deben inferirse a partir del éxito directo de OpenCode.
