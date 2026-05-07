# Plan 0003 — Progresos hacia Fase 2

> Plan vivo. Anota cada cierre de TODO de la sec. 11 (síntomas) o de los ADRs en estado *Active* con tag `fase-2-todo`.

## 2026-05-04

### Resolución de ADR 0007 — Storage centralizado

**Promovido:** sesión 2026-05-03 (durante demo de criterio Fase 1).
**Resuelto:** sesión nueva 2026-05-04.

#### Implementación

1. `src/wikiforge/config.py::apply_stack_env()` exporta `SYSTEM_ROOT_DIRECTORY`, `DATA_ROOT_DIRECTORY`, `CACHE_ROOT_DIRECTORY` apuntando a `~/.wikiforge/cognee/`.
2. `~/.wikiforge/bin/cognee-mcp-stdio.sh` exporta las mismas tres env vars antes de lanzar el server, vía `mkdir -p` + `export`.
3. `src/wikiforge/runner.py::_patch_ladybug_version_mapping()` añade los códigos 40 y 41 al mapping (workaround de bug upstream cognee 1.0.5).

#### Validación

- ✅ Cognify mini de 4 archivos (AGENTS.md + Plan 0002 + ADR 0006 + MEMORY.md) escribe en `~/.wikiforge/cognee/.cognee_system/databases/`.
- ✅ `wikiforge ask "What ADR documents the cognee_system centralization?"` devuelve top-1 = `MEMORY.md` (que cita ADR 0007), top-2 = AGENTS.md, top-3 = ADR 0006.
- ⏳ MCP cognee server se reiniciará vía shim actualizado en próxima sesión de Claude Code.

#### Hallazgo bonus → ADR 0008

Durante la validación: el cognee-mcp venv tiene cognee 1.0.0 + kuzu legacy, mientras WF venv tiene cognee 1.0.5 + ladybug 0.16. Aunque el storage esté centralizado, los version_codes que cada venv escribe son incompatibles. **TODO Fase 2:** ADR 0008 promueve la decisión de alinear las versiones.

### Hallazgos secundarios documentados

- **Cognee 1.0.5 ladybug_version_mapping outdated** — `read_ladybug_storage_version` solo conoce hasta version_code 39 (Kuzu 0.11.3). Ladybug 0.16+ escribe 40+. Workaround: monkey-patch en `runner._patch_ladybug_version_mapping`. Reportable upstream (en tracker de cognee como issue).
- **Cognee 1.0.5 hangs en cleanup async tras `Pipeline run completed`** — confirmado de nuevo. Mitigación: SIGTERM tras detectar el log line "Pipeline run completed". Considerar wrapper con `asyncio.wait_for(timeout=...)` en `runner.py`.
- **Lance + lancedb + lance_namespace + pylance**: combinación que funciona — lancedb 0.29.2 + lance 0.36.0 + lance_namespace 0.6.1 + pylance dist-info 0.36.0 + ladybug 0.16.1. Cualquier upgrade a lancedb >= 0.30 rompe el chain.

## 2026-05-07

### Resolución de ADR 0008 — Versions alineadas + cross-venv recall

**Promovido:** sesión 2026-05-04.
**Resuelto:** sesión 2026-05-07.

#### Implementación

1. Edit `~/.wikiforge/cognee-mcp/cognee-mcp/pyproject.toml`: `cognee[postgres,docs,neo4j]==1.0.0` → `cognee>=1.0.5,<1.1` + `ladybug>=0.16,<0.17`. Drop extras (no usados, evitan psycopg2 build error).
2. `uv lock --upgrade-package cognee` + `uv sync` → cognee 1.0.8 + ladybug 0.16.1 estables.
3. Reinstalar deps que quitaron extras: `transformers`, `kuzu`, `lancedb`, `pylance`.
4. **Launcher Python wrapper** (`~/.wikiforge/bin/cognee_mcp_launcher.py`) que aplica `_patch_ladybug_version_mapping()` antes de `runpy.run_path(server.py)`. Espejo del patch del WF venv pero ejecutado desde el shim del MCP.
5. Update `~/.wikiforge/bin/cognee-mcp-stdio.sh` → `exec uv run python ~/.wikiforge/bin/cognee_mcp_launcher.py` (en vez de server.py directo).

#### Validación end-to-end

Cross-venv `cognee.search(CHUNKS, "ADR centralization", datasets=["WikiForge"])` desde el cognee-mcp venv devuelve 5 chunks reales: MEMORY.md, AGENTS.md, ADR 0006. **El MCP server (al reiniciarse en próxima sesión Claude Code) verá el dataset poblado por el CLI WF.**

### Versions finales

| Venv | cognee | ladybug | Path storage |
|---|---|---|---|
| WikiForge | 1.0.5 | 0.16.1 | `~/.wikiforge/cognee/` |
| cognee-mcp | 1.0.8 | 0.16.1 | `~/.wikiforge/cognee/` |

cognee no idéntico (1.0.5 vs 1.0.8) pero ladybug sí — la pieza crítica para compatibilidad de file format.

## TODOs abiertos para Fase 2 (orden por prioridad)

1. ~~**ADR 0008**~~ ✅ Resuelto 2026-05-07.
2. **Cognee cleanup async hang** — confirmado de nuevo en cognify mini de hoy. Investigar root cause o aplicar `asyncio.wait_for(timeout=...)` wrapper en `runner.py`. Próximo TODO de máxima prioridad.
3. **Reranker** — síntoma 11.4 medido en Fase 0 (Q2/Q3 a 0.5 por falta). Activar `bge-reranker-v2-m3` o `qwen3-reranker-4b`. Requiere ADR autorizando la nueva dep.
4. **Suite `wikiforge eval`** — entregable Fase 2 según plan original.
5. **PR upstream a cognee** — relajar el `cognee==1.0.0` strict pin del cognee-mcp para no requerir el hack del pyproject.
