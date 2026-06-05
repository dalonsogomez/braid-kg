# Plan 0003 — Progresos hacia Fase 2

> Plan vivo. Anota cada cierre de TODO de la sec. 11 (síntomas) o de los ADRs en estado *Active* con tag `fase-2-todo`.

## 2026-05-04

### Resolución de ADR 0007 — Storage centralizado

**Promovido:** sesión 2026-05-03 (durante demo de criterio Fase 1).
**Resuelto:** sesión nueva 2026-05-04.

#### Implementación

1. `src/braid/config.py::apply_stack_env()` exporta `SYSTEM_ROOT_DIRECTORY`, `DATA_ROOT_DIRECTORY`, `CACHE_ROOT_DIRECTORY` apuntando a `~/.braid/cognee/`.
2. `~/.braid/bin/cognee-mcp-stdio.sh` exporta las mismas tres env vars antes de lanzar el server, vía `mkdir -p` + `export`.
3. `src/braid/runner.py::_patch_ladybug_version_mapping()` añade los códigos 40 y 41 al mapping (workaround de bug upstream cognee 1.0.5).

#### Validación

- ✅ Cognify mini de 4 archivos (AGENTS.md + Plan 0002 + ADR 0006 + MEMORY.md) escribe en `~/.braid/cognee/.cognee_system/databases/`.
- ✅ `braid ask "What ADR documents the cognee_system centralization?"` devuelve top-1 = `MEMORY.md` (que cita ADR 0007), top-2 = AGENTS.md, top-3 = ADR 0006.
- ⏳ MCP cognee server se reiniciará vía shim actualizado en próxima sesión de Claude Code.

#### Hallazgo bonus → ADR 0008

Durante la validación: el cognee-mcp venv tiene cognee 1.0.0 + kuzu legacy, mientras Braid venv tiene cognee 1.0.5 + ladybug 0.16. Aunque el storage esté centralizado, los version_codes que cada venv escribe son incompatibles. **TODO Fase 2:** ADR 0008 promueve la decisión de alinear las versiones.

### Hallazgos secundarios documentados

- **Cognee 1.0.5 ladybug_version_mapping outdated** — `read_ladybug_storage_version` solo conoce hasta version_code 39 (Kuzu 0.11.3). Ladybug 0.16+ escribe 40+. Workaround: monkey-patch en `runner._patch_ladybug_version_mapping`. Reportable upstream (en tracker de cognee como issue).
- **Cognee 1.0.5 hangs en cleanup async tras `Pipeline run completed`** — confirmado de nuevo. Mitigación: SIGTERM tras detectar el log line "Pipeline run completed". Considerar wrapper con `asyncio.wait_for(timeout=...)` en `runner.py`.
- **Lance + lancedb + lance_namespace + pylance**: combinación que funciona — lancedb 0.29.2 + lance 0.36.0 + lance_namespace 0.6.1 + pylance dist-info 0.36.0 + ladybug 0.16.1. Cualquier upgrade a lancedb >= 0.30 rompe el chain.

## 2026-05-07

### Resolución de ADR 0008 — Versions alineadas + cross-venv recall

**Promovido:** sesión 2026-05-04.
**Resuelto:** sesión 2026-05-07.

#### Implementación

1. Edit `~/.braid/cognee-mcp/cognee-mcp/pyproject.toml`: `cognee[postgres,docs,neo4j]==1.0.0` → `cognee>=1.0.5,<1.1` + `ladybug>=0.16,<0.17`. Drop extras (no usados, evitan psycopg2 build error).
2. `uv lock --upgrade-package cognee` + `uv sync` → cognee 1.0.8 + ladybug 0.16.1 estables.
3. Reinstalar deps que quitaron extras: `transformers`, `kuzu`, `lancedb`, `pylance`.
4. **Launcher Python wrapper** (`~/.braid/bin/cognee_mcp_launcher.py`) que aplica `_patch_ladybug_version_mapping()` antes de `runpy.run_path(server.py)`. Espejo del patch del Braid venv pero ejecutado desde el shim del MCP.
5. Update `~/.braid/bin/cognee-mcp-stdio.sh` → `exec uv run python ~/.braid/bin/cognee_mcp_launcher.py` (en vez de server.py directo).

#### Validación end-to-end

Cross-venv `cognee.search(CHUNKS, "ADR centralization", datasets=["Braid"])` desde el cognee-mcp venv devuelve 5 chunks reales: MEMORY.md, AGENTS.md, ADR 0006. **El MCP server (al reiniciarse en próxima sesión Claude Code) verá el dataset poblado por el CLI Braid.**

### Versions finales

| Venv | cognee | ladybug | Path storage |
|---|---|---|---|
| Braid | 1.0.5 | 0.16.1 | `~/.braid/cognee/` |
| cognee-mcp | 1.0.8 | 0.16.1 | `~/.braid/cognee/` |

cognee no idéntico (1.0.5 vs 1.0.8) pero ladybug sí — la pieza crítica para compatibilidad de file format.

## TODOs abiertos para Fase 2 (orden por prioridad)

1. ~~**ADR 0008**~~ ✅ Resuelto 2026-05-07.
2. ~~**Cognee cleanup async hang**~~ ✅ **Mitigado** 2026-05-09 (ADR 0009): `asyncio.wait_for(timeout=120)` envuelve `cognify` en `runner.py`.
3. ~~**Reranker**~~ ✅ **Implementado** 2026-05-09 vía ADR 0012 (cloud-only, OpenRouter Cohere Rerank 4 Fast). ADR 0011 (bge-reranker LOCAL) Superseded por veto user descarga local + deep-research 30+ sources. `runner.rerank_via_openrouter` operativo, flag `--rerank` en `braid eval`. Validación end-to-end pendiente de `OPENROUTER_API_KEY` en secrets.env (acción manual user).
4. ~~**Suite `braid eval`**~~ ✅ **Resuelto** 2026-05-09 (ADR 0010): comando `braid eval` operativo, 10 preguntas en `.memory/eval/questions.json`, baseline registrado en `.memory/eval/runs/baseline-fase-2.json` = 5.5/10 contra dataset parcial.
5. **PR upstream a cognee** — relajar el `cognee==1.0.0` strict pin del cognee-mcp para no requerir el hack del pyproject. Sin urgencia.
6. **NUEVO — Síntoma 11.8 activo: Ollama Cloud caído.** Verificado 2026-05-09 12:18: `curl -m 30 /v1/chat/completions` con `kimi-k2.6:cloud` → timeout sin response. Reindex completo del repo bloqueado. Aplicar contingencia AGENTS.md sec. 11.8 (reversión a `qwen3:30b` local) si persiste >24h. Próxima sesión debe verificar estado primero.

## 2026-05-09

### Resolución de ADR 0009 — Auto-bootstrap RAG vía SessionStart hook

**Promovido y resuelto:** sesión 2026-05-09 (mismo día — feature directa a partir de petición textual del usuario).

#### Implementación

1. `src/braid/commands/claude.py` — nuevo módulo con `run_session_start()` y `run_init(remove=...)`. Solo I/O del filesystem, sin imports de cognee.
2. `src/braid/cli.py` — registra subcomandos `claude-session-start` (con `--json`) y `claude-init` (con `--remove`).
3. `src/braid/commands/index.py` — incremental por mtime: lee `.kg/last_index.json`, filtra inputs por `mtime > timestamp_unix`, exit 0 inmediato si nada cambió, escribe state al finalizar (con todos los paths actuales, no solo modificados).
4. `src/braid/runner.py` — `cognify(dataset, timeout=120)` envuelta con `asyncio.wait_for`; absorbe `TimeoutError` con log explícito (mitigación cleanup hang).
5. `src/braid/commands/sync.py` — mensaje actualizado.
6. `.claude/settings.json` (repo Braid) — generado por `braid claude-init` (dogfooding).
7. `~/.braid/profile/preferences.json` — añadido bloque `braid_hooks.auto_sync_on_stop=false` (opt-in, default off).

#### Validación

| # | Escenario | Resultado |
|---|---|---|
| V1 | `claude-session-start` repo al día | ✅ "memoria al día (50 inputs · 9 ADRs)" en p50=250ms |
| V2 | `--json` | ✅ JSON válido con `status:"ready"` |
| V3 | cwd fuera de repo git | ✅ exit 0 silencioso (texto) / `status:"no_repo"` (json) |
| V4 | `claude-init` en repo virgen | ✅ `.claude/settings.json` creado con hook |
| V5 | `claude-init` x2 | ✅ idempotente ("ya presente, sin cambios") |
| V6 | `--remove` con `permissions`/`env` preexistentes | ✅ preserva otras claves; archivo eliminado si queda vacío |
| V7 | `sync` at-rest | ✅ "al día — sin cambios desde {iso}" en 0.41s, sin LLM |
| V8 | `touch X.py + claude-session-start` | ✅ "memoria stale (1 archivo modificado · ejecuta 'braid sync')" |

p50 del hook: **~250 ms** (lectura completa de globs); ~55 ms cuando no hay `last_index.json`. Objetivo de <500 ms ampliamente cumplido.

#### Anti-patrones respetados (AGENTS.md sec. 9)

- Sec. 9.6 (nuevo comando sin ADR) — **cumplido**: ADR 0009 lo precede.
- Sec. 9.7 (ingesta sin autorización por repo) — **cumplido**: el hook NO llama al LLM ni crea `.kg/`. Solo informa.

#### Hallazgos secundarios

- **Auto-cleanup en `claude-init --remove`**: si el archivo `.claude/settings.json` queda con un objeto vacío `{}` tras quitar el hook, se borra el archivo. Evita basura.
- **`last_index.json` no detecta archivos borrados**, solo modificados/añadidos. Aceptado: `braid index --rebuild` lo reconcilia cuando moleste.
- **Symlink global necesario** — `braid` no estaba en el PATH global (vivía sólo en `<repo>/.venv/bin/`). El hook se ejecuta sin venv activado. Solución: `ln -sf <repo>/.venv/bin/braid ~/.local/bin/braid`. Reversible y documentado en ADR 0009. La ruta de producción será `uv tool install` o `pipx install -e .`.

### Resolución entregables Fase 2 (criterio sec. 10)

**Promovido y resuelto:** sesión 2026-05-09 (mismo día — entrega completa Fase 2 sin esperar más sesiones).

#### Implementación

1. `.memory/decisions/0010-suite-braid-eval.md` — ADR formato suite eval.
2. `src/braid/commands/eval.py` (nuevo, ~250 líneas) — comando real que reemplaza el stub. Incluye:
   - `_extract_text` defensivo ante None/list/dict/object
   - Validación temprana de `questions.json` (KeyError prevenido)
   - Captura `JSONDecodeError` + `OSError`
   - `_search_with_timeout` por pregunta (default 90s) — pregunta colgada no bloquea suite
   - Fallback a stdout si `_save_run` falla por filesystem read-only
   - Bonus `exact_top_1_bonus` configurable desde JSON
   - Extracción de `top_1_path` del header `[FILE kind=... path=...]` inyectado por `annotate_file`
3. `src/braid/cli.py` — eval ya no es stub; flags `--questions`, `--top-k`, `--no-save`, `--per-question-timeout`.
4. `.memory/eval/questions.json` — 10 preguntas Braid con ground truth (cubre CONTAINS, DOCUMENTS, MENTIONS, IMPORTS — los 4 tipos relevantes para repo Python solo; CALLS/IMPORTS solapan).
5. `.memory/eval/runs/baseline-fase-2.json` — baseline 5.5/10 (55%, recall@1=0.40, recall@K=0.70) registrado contra dataset parcial.

#### Reviews independientes (subagents)

- **Spec compliance:** APROBADO_CON_OBSERVACIONES. 2 importantes (top_1_path no path real, exact_top_1_bonus hardcoded), 4 cosméticas. Todas aplicadas.
- **Code quality:** APROBADO_CON_FIXES_OPCIONALES. 5 importantes (validación temprana, timeout, OSError fallback, JSONDecodeError, _extract_text con None/list). Todas aplicadas.

#### Hallazgos secundarios

- **Síntoma 11.8 activo** — Ollama Cloud `kimi-k2.6:cloud` caído (timeout 30s). Reindex completo bloqueado. Snapshot dataset parcial restaurado para preservar baseline. Plan 0006 sec. A2 prevé reversión a `qwen3:30b` local.
- **ADR 0011 (Proposed)** — Reranker `bge-reranker-v2-m3` documentado pero sin implementar. Razón: validar el delta requiere reindex completo (bloqueado por 11.8). Plan 0006 lo retoma cuando 11.8 cierre.
- **Reindex `--rebuild` NO borra `.data_storage/text_*.txt`** — solo limpia tablas y grafo. Esto permitió restaurar el dataset parcial vía simple `cp -R` desde snapshot. Útil saberlo para futuras operaciones destructivas.

### Pivote cloud-only y reranker ADR 0012 (2026-05-09 sesión continuada)

**Origen:** user mostró panel de 9 proveedores cloud y declaró *"no quiero tener el modelo utilizado y descargado de manera local ya que me ocupa muchos gigas"*. ADR 0011 (bge-reranker LOCAL 568 MB + sentence-transformers ~2 GB) queda incompatible.

**Deep-research:** 16 búsquedas web paralelas, 30+ sources triangulado. Reporte completo en `~/Documents/Braid_Reranker_Research_20260509/research_report_20260509_braid_reranker.md` (3722 palabras).

**Conclusión:** Cohere Rerank 4 Fast vía OpenRouter ganador absoluto:
- Passthrough $0/M tokens en OpenRouter actualmente
- 100+ idiomas (incluido español), 32K context
- ~600 ms latencia (lowest en familia Cohere)
- LLM-as-judge con Gemini Flash descartado: 10× más caro y NDCG@10 0.68 vs 0.74 para reranker dedicado

**Implementación:**
1. `runner.rerank_via_openrouter(query, items, top_n, model="cohere/rerank-4-fast")` — POST a `https://openrouter.ai/api/v1/rerank` vía httpx, degraded mode si falta key.
2. `runner.run_search_with_rerank` convenience helper.
3. `commands/eval.py` flag `--rerank` (default off, opt-in privacidad).
4. `commands/eval.py` registra `meta.reranker_used` y `meta.reranker_model` en run JSON.
5. `cli.py` argparse `--rerank` cableado.

**Verificación mecánica (sin key):** ejecutar `braid eval --rerank` con dataset parcial → degraded mode log claro + items devueltos sin reordenar + comando NO falla. ✅

**Pendiente (acción user):** copiar `OPENROUTER_API_KEY` desde panel OpenRouter a `~/.config/braid/secrets.env`. Tras eso, validar end-to-end con `braid eval --rerank` y comparar contra `baseline-fase-2.json` (5.5/10).
