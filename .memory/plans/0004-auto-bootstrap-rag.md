# Plan 0004 — Auto-bootstrap RAG por sesión IA

- **Fecha de inicio:** 2026-05-09
- **Status:** In progress
- **ADR de referencia:** [0009](../decisions/0009-auto-bootstrap-rag-via-session-hook.md)
- **Fase del proyecto:** 2 (sub-objetivo `auto-bootstrap`)

## Objetivo

Cumplir la promesa A del proyecto en el primer mensaje de cada sesión IA: el agente sabe, sin coste cognitivo del usuario, si el repo activo tiene memoria/RAG al día, stale o ausente. Sin auto-ingesta. Sin esperar al LLM. Sin escribir fuera del git root del cwd.

## Resumen del ADR 0009

- Comando nuevo `wikiforge claude-session-start`: lee filesystem, reporta estado en una línea, no llama al LLM, p50 <500 ms.
- Comando nuevo `wikiforge claude-init`: cablea hook `SessionStart` en `<git_root>/.claude/settings.json`, idempotente.
- `wikiforge sync` con incremental real (mtime + `last_index.json`) y `asyncio.wait_for(timeout=120)` en `cognify`.
- Hook `Stop` opt-in (default `false`) en `~/.wikiforge/profile/preferences.json`.

## Tareas

### 1. ADR 0009 ✅
Escrito en `.memory/decisions/0009-auto-bootstrap-rag-via-session-hook.md`.

### 2. Comando `wikiforge claude-session-start`
**Archivo nuevo:** `src/wikiforge/commands/claude.py` (~120 líneas).
**Registro en CLI:** `src/wikiforge/cli.py` añade subparser `claude-session-start` con flags `--json`, `--scope` (default `auto`).
**Lógica:**

1. Resuelve cwd → git root vía `paths.find_git_root()`.
2. Si no hay repo: exit 0 silencioso (sin output) salvo `--json` que emite `{"status":"no_repo"}`.
3. Si hay repo pero no `.kg/`: emit `[WikiForge] repo no inicializado · ejecuta 'wikiforge init && wikiforge index'`.
4. Si hay `.kg/` pero no `.kg/last_index.json`: emit `[WikiForge] repo inicializado pero no indexado · ejecuta 'wikiforge index'`.
5. Si ambos existen: lee `last_index.json`, recorre globs canónicos (mismos que `index.py`), cuenta archivos con `mtime > last_index.timestamp`. Cuenta ADRs en `.memory/decisions/`. Emite `[WikiForge] memoria al día (N inputs · M ADRs)` o `[WikiForge] memoria stale (X archivos modificados · ejecuta 'wikiforge sync')`.

**Coste**: solo `Path.glob` + `os.stat`. No imports de cognee. **Target p50 <500 ms**.

### 3. Comando `wikiforge claude-init`
**Mismo archivo** `src/wikiforge/commands/claude.py`.
**CLI**: subparser `claude-init` con `--remove`.
**Lógica:**

1. Resuelve git root del cwd. Si no hay repo: exit 1 con mensaje "no estás dentro de un repo git".
2. Path target: `<git_root>/.claude/settings.json`.
3. Si no existe: crea con estructura mínima.
4. Si existe: parsea JSON, hace merge sin pisar otras claves. Añade entrada en `hooks.SessionStart` con `command: "wikiforge claude-session-start"`.
5. `--remove`: elimina solo la entrada que añadió (matchea por substring del comando), preserva el resto.

### 4. Sync incremental (`commands/index.py` + `commands/sync.py`)
**Cambios en `index.py`:**

- Añadir `_load_index_state(kg_dir: Path) -> dict | None` que lee `.kg/last_index.json` (None si no existe).
- Añadir `_filter_by_mtime(files: list[Path], last_ts: float) -> list[Path]` que filtra los modificados desde el último index.
- `run(rebuild=False, ...)`:
  - Si `rebuild=False` y hay `last_index.json`: filtrar inputs por mtime.
  - Si quedan 0: `print("[wikiforge sync] al día — sin cambios desde {iso_ts}"); return 0`.
  - Tras `run_cognify`: escribir `.kg/last_index.json` con `{"timestamp": now, "files": [paths_processed], "dataset": ds}`.
- Manejar excepción `asyncio.TimeoutError` en `run_cognify`: log warn y continuar (los datos ya están escritos antes del cleanup hang).

**Cambios en `runner.py`:**

- `cognify(dataset)` envuelta en `asyncio.wait_for(_cognify_inner(dataset), timeout=120)` con catch específico de `TimeoutError` que emite el log `[wikiforge runner] cognify timeout (cleanup hang upstream cognee 1.0.5) — datos íntegros`.

### 5. Dogfooding
- Ejecutar `wikiforge claude-init` en el repo WikiForge mismo → genera `.claude/settings.json` con el hook (NO se versiona — `.gitignore` actual ignora `.claude/`; cada checkout activa el hook con `wikiforge claude-init`).
- Symlink global: `ln -sf <repo>/.venv/bin/wikiforge ~/.local/bin/wikiforge` (necesario porque el hook se ejecuta sin venv activado y `~/.local/bin/` está en el PATH del usuario).
- Añadir `wikiforge_hooks.auto_sync_on_stop: false` a `~/.wikiforge/profile/preferences.json` (opt-in default off, sec. 9.7).

### 6. Verificación

| # | Escenario | Esperado |
|---|---|---|
| V1 | `time wikiforge claude-session-start` en repo WikiForge x5 | p50 < 500 ms |
| V2 | Mismo, con `--json` | JSON válido con `status:"ready"` o `"stale"` |
| V3 | `wikiforge claude-session-start` en `~/tmp` (sin repo) | exit 0 silencioso |
| V4 | `wikiforge claude-init` en repo nuevo (`/tmp/x` con `git init`) → cat `.claude/settings.json` | JSON válido con hook SessionStart |
| V5 | Mismo, ejecutar 2 veces | idempotente, no duplica |
| V6 | `wikiforge claude-init --remove` | quita solo el hook añadido |
| V7 | `wikiforge sync` recién después de `index` (sin tocar archivos) | exit 0 inmediato con mensaje "al día" |
| V8 | `touch src/wikiforge/cli.py && wikiforge claude-session-start` | mensaje `stale (1 archivo modificado)` |

### 7. Update memoria
- `MEMORY.md` del proyecto: añadir entrada ADR 0009 + Plan 0004.
- `plans/0003-fase-2-progresos.md`: añadir sección 2026-05-09 con el cierre del TODO #2 (mitigación cleanup hang).
- `auto-memory`: añadir feedback memory si surge algo no obvio durante la implementación.

### 8. Commit + tag
- Commit: `feat(adr-0009): auto-bootstrap RAG via SessionStart hook (opt-in privacy)`.
- Tag: `wf-fase-2-auto-bootstrap-rag`.

## Criterios de aceptación

1. ✅ ADR 0009 escrito.
2. ⏳ V1 cumple <500 ms p50.
3. ⏳ V3 (no-repo) y V5 (idempotencia) son verdes.
4. ⏳ V7 (sync at-rest) cumple <1 s.
5. ⏳ Hook real en `.claude/settings.json` del repo WikiForge — visible en próxima sesión.
6. ⏳ MEMORY.md y plan 0003 actualizados; commit + tag aplicados.

## Riesgos

- **Cognee `cognify` con timeout puede silenciar errores reales.** Mitigación: log explícito + revisar manualmente la primera vez. Cambiar a 30 s si genera ruido.
- **`.claude/settings.json` formato JSON puede cambiar entre versiones de Claude Code.** Mitigación: el helper `claude-init` escribe el formato actual documentado; si Anthropic lo cambia, ADR de actualización puntual.
- **Codex CLI / Cursor no consumen `SessionStart`.** Aceptado: este ADR es Claude Code-first; Codex/Cursor llamarán `wikiforge claude-session-start` desde sus propias instrucciones de inicio cuando el usuario lo configure.

## Fuera de alcance

- Resolución root-cause del cleanup async hang upstream (queda como TODO Fase 2 #2, ahora marcado **mitigado** en plan 0003).
- Reranker (TODO #3).
- Suite `wikiforge eval` (TODO #4).
- Auto-detección y soporte nativo en Codex/Cursor.
- Hooks `PreToolUse`/`PostToolUse` para tracking más fino — fuera de scope, otro ADR si surge.
