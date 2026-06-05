# ADR 0009 — Auto-bootstrap RAG vía SessionStart hook (opt-in privacidad)

- **Estado:** Active
- **Fecha:** 2026-05-09
- **Decisor:** Daniel Alonso Gómez
- **Tags:** infra,claude-code,hooks,fase-2,ux,privacy
- **Origen:** sesión 2026-05-09. Petición textual: *"que cada vez que utilice cualquier herramienta de inteligencia artificial, … cree los archivos de la base de datos del directorio actual … fluido y no tarde un tiempo excesivo"*.

---

## Contexto

Tras Fase 1 PASS (CLI `wikiforge` operativo, dos repos con `.kg/.rag/.memory/`), el flujo real para activar memoria/RAG en un repo nuevo o reanudar uno existente requiere comandos manuales (`wikiforge init && wikiforge index`). Esto fricciona la promesa A del proyecto (*"que un agente trabajando dentro de un proyecto responda preguntas concretas sin alucinar y sin que el usuario tenga que abrir archivos a mano"*) porque:

1. Un agente nuevo en una sesión Claude Code no sabe si el repo está indexado.
2. Si está indexado pero hay archivos modificados desde el último index, no hay señal automática de staleness.
3. El usuario tiene que recordar ejecutar `wikiforge sync` tras cambios — lo que rompe la fluidez.

A la vez, dos restricciones del contrato canónico (`AGENTS.md`) bloquean cualquier solución agresiva:

- **Sec. 9.7 (privacidad):** *"Subir documentos privados a APIs cloud sin que el usuario lo haya autorizado explícitamente para esa ingesta concreta"* — cualquier auto-`index` sin consentimiento por repo viola este anti-patrón. Cognee llama al LLM cloud (Ollama Cloud `kimi-k2.6:cloud`) durante `cognify`.
- **Sec. 9.6:** Crear nuevos comandos `wikiforge` requiere ADR. Este es el ADR.

Adicionalmente, el cuello de botella de "fluidez" no es la activación: es el `cleanup async hang` de cognee 1.0.5 documentado como TODO Fase 2 #2 (plan 0003 sec. 2026-05-04). Sin mitigación, cualquier llamada a `cognify` cuelga al final indefinidamente y obliga a `SIGTERM`.

## Decisión

Se introducen tres piezas, gobernadas por el principio **"el cwd manda; nunca crear estructura fuera del git root del cwd; ingesta solo con consentimiento explícito por repo"**:

### 1. Comando `wikiforge claude-session-start` (nuevo)

Subcomando interno usado por hooks de Claude Code (y portable a Codex/Cursor en el futuro). Propiedades duras:

- **Nunca llama al LLM** ni a cognee. Solo I/O del filesystem.
- **Nunca crea `.kg/`, `.rag/` ni `.memory/`** si no existen — solo informa de su ausencia.
- **Resuelve cwd → git root** (sin ascender más arriba). Si el cwd no está dentro de un repo git: silent exit con código 0 y mensaje vacío.
- **Si `.kg/` no existe**: imprime una sola línea `[WikiForge] repo no inicializado · ejecuta 'wikiforge init && wikiforge index'`. Exit 0.
- **Si `.kg/` existe pero `.kg/last_index.json` no**: imprime `[WikiForge] repo inicializado pero no indexado · ejecuta 'wikiforge index'`. Exit 0.
- **Si `.kg/` y `.kg/last_index.json` existen**: cuenta archivos del scope (sec. 5.1 de este ADR) cuyo `mtime` > `last_index.timestamp`. Imprime `[WikiForge] memoria al día (N inputs · M ADRs)` o `[WikiForge] memoria stale (X archivos modificados · ejecuta 'wikiforge sync')`. Exit 0.
- **Coste objetivo p50 < 500 ms** medido sobre el repo WikiForge (~50 archivos del scope).
- **Soporta `--json`** para consumo programático: emite `{"status":"ready|stale|uninitialized|no_repo","root":"…","dataset_id":"…","ndocs":N,"nadrs":M,"stale_count":X}`.

### 2. Comando `wikiforge claude-init` (nuevo)

Helper que crea/actualiza `.claude/settings.json` (relativo al git root del cwd) con un hook `SessionStart` que invoca `wikiforge claude-session-start`. Propiedades:

- **Idempotente**: si el archivo existe, hace merge sin pisar otras claves (ej. `permissions`, `env`, otros hooks).
- **Solo escribe en el git root del cwd**, nunca en `~/.claude/`.
- **Soporta `--remove`** para deshacer (quita solo el hook que añadió, no el archivo).

### 3. `wikiforge sync` incremental real

`index.run(rebuild=False)` actualizado para:

- Leer `.kg/last_index.json` antes de empezar.
- Filtrar inputs cuyo `mtime` ≤ `last_index.timestamp`. Si quedan 0 inputs y los ADRs/MEMORY tampoco cambiaron: imprimir `[wikiforge sync] al día — sin cambios desde {timestamp}` y exit 0 inmediato (< 100 ms).
- Si quedan >0: ejecutar `cognee.add` + `cognify` solo sobre el delta.
- Envolver `cognify(dataset)` con `asyncio.wait_for(timeout=120)` para neutralizar el cleanup async hang documentado en plan 0003. Si timeout se dispara tras "Pipeline run completed" se considera éxito (el hang es upstream y no afecta a los datos ya escritos).
- Al finalizar (con o sin timeout), escribir `.kg/last_index.json` con el `timestamp` actual y la lista de paths procesados.

Esto cierra el TODO Fase 2 #2 (plan 0003) como **mitigación** — el root-cause sigue abierto upstream y se reportará en otro ADR si es necesario.

## Alternativas consideradas

| Alternativa | Por qué descartada |
|---|---|
| Auto-init + auto-index al primer `SessionStart` | Viola sec. 9.7 (ingesta sin consentimiento por repo). Además bloquea la sesión 5-25 min con `cognify` la primera vez. |
| Hook `SessionStart` que llama a cognee MCP en vez de al CLI | Acoplaría el hook al estado del cognee-mcp server (puede no estar arrancado). El CLI es self-contained. |
| Usar un daemon `wikiforge watch` con `fswatch` | Mucho más complejo, otro proceso vivo, no justificado todavía. Si el flujo opt-in resulta insuficiente medido en Fase 2 `eval`, se reconsiderará en otro ADR. |
| Hook `Stop` con auto-`sync` activado por defecto | Mismo problema de privacidad y de coste de tokens. **Se incluye como flag opt-in** (`auto_sync_on_stop` en `~/.wikiforge/profile/preferences.json`, default `false`). |
| Detectar el IDE (Cursor/Codex) y emitir hooks específicos por cada uno | Sobre-ingeniería. El comando `claude-session-start` es genérico. Codex/Cursor pueden invocarlo cuando soporten el equivalente a hooks. Si no, queda inerte sin coste. |

## Consecuencias

### Positivas

- Cualquier sesión Claude Code dentro de un repo gobernado por WikiForge ve, en el primer mensaje, si la memoria está al día, stale o ausente — sin ejecutar nada manual.
- El usuario sigue controlando cuándo se gasta LLM (sec. 9.7 respetada). El hook **nunca** llama al LLM.
- `wikiforge sync` deja de tardar minutos cuando no hay cambios → la fluidez pedida se cumple por skip, no por concurrency.
- El timeout de 120 s neutraliza el cleanup hang sin esperar al fix upstream.

### Negativas

- Añade dos comandos al CLI (`claude-session-start`, `claude-init`) — eleva la superficie de mantenimiento. Mitigación: ambos son <100 líneas, sin deps nuevas.
- El timeout de 120 s puede silenciar regresiones reales del cleanup. Mitigación: log explícito `[wikiforge sync] timeout esperado tras 'Pipeline run completed' (cleanup hang upstream)` para que se note.
- `last_index.json` no detecta archivos *borrados* — solo modificados. Mitigación aceptada: las búsquedas en cognee sobre archivos borrados son detectables por el lector (ruta no existe en disco) y se reconcilian con `wikiforge index --rebuild` cuando moleste.

### Neutras

- Necesita seed por repo: el primer `wikiforge claude-init` por repo. Es un comando, no fricción.
- Codex CLI y Cursor no soportan el mismo formato de hook que Claude Code; quedan fuera de la fluidez automática hasta que añadan equivalente — pueden invocar `wikiforge claude-session-start` manualmente desde sus propias instrucciones de inicio si el usuario lo configura.

## Alcance: solo cwd dentro del git root

Es **no negociable** que ninguna pieza de este ADR escriba fuera del git root del cwd. Concretamente:

- `claude-session-start` lee solo desde `git_root` resuelto desde el cwd. Si cwd está fuera de un repo, exit 0 silencioso.
- `claude-init` escribe solo en `<git_root>/.claude/settings.json`.
- `sync` escribe solo en `<git_root>/.kg/last_index.json`.
- Si el usuario está en un sub-directorio del repo, el git root sigue siendo el ámbito (consistente con `paths.find_git_root`). Esto es lo que la petición original llamaba *"solo coger o solo crear del directorio justo actual o sin crearlo de toda una ruta"*.

## Verificación

1. **Tiempo p50 < 500 ms** en `wikiforge claude-session-start` ejecutado 5 veces consecutivas en `~/Developer/claude/code-projects/WikiForge` (warm cache).
2. **3 escenarios de output** verificados:
   - cwd en repo virgen sin `.kg/` → `[WikiForge] repo no inicializado · ...`
   - cwd en repo indexado al día → `[WikiForge] memoria al día (N · M)`
   - cwd en repo con archivo tocado → `[WikiForge] memoria stale (1 archivo modificado · ...)`
3. **`wikiforge sync` con todo cached** → exit 0 en <1 s, sin invocar al LLM.
4. **`.claude/settings.json` generado por `claude-init`** valida JSON y carga correctamente en próxima sesión Claude Code (dogfooding en el repo WikiForge mismo).
5. **No-creación fuera del scope**: ejecutar `claude-session-start` desde `~/tmp` (no-repo) → exit 0 silencioso, no se crea nada.

## Disponibilidad global del binario

El hook usa `wikiforge claude-session-start` resuelto por `$PATH`. El binario instalado por `uv pip install -e .` vive en `<repo>/.venv/bin/wikiforge` y NO está en el PATH global por defecto. Para que el hook funcione en cualquier sesión:

```bash
ln -sf <repo>/.venv/bin/wikiforge ~/.local/bin/wikiforge
```

`~/.local/bin/` ya está en el PATH del usuario (al inicio). El symlink es reversible y usa el shebang absoluto del binario, así que sigue resolviendo el python correcto del venv aunque se invoque desde otro cwd.

**Alternativa producción**: `uv tool install /path/to/WikiForge` o `pipx install -e .` instalan el CLI en su propio venv aislado y dejan el comando global automáticamente. Cuando el proyecto se distribuya, será el camino oficial.

## Migración / rollback

- Si el hook causa fricción: `wikiforge claude-init --remove` lo desinstala dejando el resto de `settings.json` intacto.
- Si el timeout de 120 s en `sync` cuelga regresiones reales: cambiar a 30 s en `runner.py`. ADR de actualización si pasa.
- Si el comando se demuestra innecesario: deprecación en próximo ADR. Los archivos `.kg/last_index.json` son inertes sin el comando.

## Referencias

- AGENTS.md sec. 4.3 (resolución de contexto), sec. 7 (CLI canónico — esta entrada lo amplía con dos subcomandos), sec. 9.6 (anti-patrón nuevos comandos sin ADR — cumplido por este ADR), sec. 9.7 (anti-patrón ingesta sin autorización — respetado).
- ADR 0007 — storage centralizado (relación: `last_index.json` vive en el `.kg/` local del repo, no en el storage centralizado, porque es metadata local de fluidez, no datos del grafo).
- Plan 0003 sec. 2026-05-04 TODO #2 (cleanup async hang) — mitigado parcialmente.
