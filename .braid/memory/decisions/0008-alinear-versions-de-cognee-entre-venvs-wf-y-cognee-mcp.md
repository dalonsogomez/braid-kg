# ADR 0008 — Alinear versions de cognee entre venvs (WF y cognee-mcp)

- **Estado:** Resolved
- **Fecha:** 2026-05-04 (promovido) → 2026-05-07 (resuelto)
- **Decisor:** Daniel Alonso Gómez
- **Tags:** infra,cognee,fase-2-todo,version-skew
- **Origen:** promoción manual sesión → proyecto vía `wikiforge promote-decision`

---

## Decisión

Los venvs de WikiForge (cognee 1.0.5 + ladybug 0.16) y cognee-mcp (cognee 1.0.0 + kuzu legacy) escriben formatos de Kuzu file con version_codes incompatibles. Tras centralizar el storage (ADR 0007), si el MCP lee chunks escritos por el CLI, falla con "Could not map version_code". TODO Fase 2: alinear versions actualizando cognee-mcp venv a cognee 1.0.5 (o lo que sea last stable que tenga ladybug_version_mapping actualizado upstream). Verificar que cognee-mcp/server.py sigue siendo compatible con la API de la versión target.

## Resolución (2026-05-07)

### Implementación

1. **Modificar `~/.wikiforge/cognee-mcp/cognee-mcp/pyproject.toml`** — relajar el constraint `cognee==1.0.0` a `cognee>=1.0.5,<1.1` y añadir `ladybug>=0.16,<0.17` como dependency directa. El extras `[postgres,docs,neo4j]` se eliminó (no usados, evita el psycopg2 build error).

2. **`uv lock --upgrade-package cognee` + `uv sync`** — actualizó el lockfile a `cognee==1.0.8` (último compatible) y aplicó la nueva resolución al venv.

3. **Reinstalar deps que `uv sync` eliminó por dropear extras**: `transformers`, `kuzu`, `lancedb`, `pylance` mediante `VIRTUAL_ENV=$(pwd)/.venv uv pip install`.

4. **`~/.wikiforge/bin/cognee_mcp_launcher.py`** — wrapper Python que aplica `_patch_ladybug_version_mapping()` (mismo patch que `wikiforge.runner` aplica al CLI) y luego `runpy.run_path(server.py, run_name="__main__")`. Espejo del patch del WF venv pero ejecutado desde el shim del MCP.

5. **`~/.wikiforge/bin/cognee-mcp-stdio.sh`** — actualizado para `exec uv run python ~/.wikiforge/bin/cognee_mcp_launcher.py` en lugar del server.py directo.

### Estado final de versions

| Venv | cognee | ladybug | Path storage |
|---|---|---|---|
| WikiForge (`/Users/dalonsogomez/Developer/claude/code-projects/WikiForge/.venv/`) | 1.0.5 | 0.16.1 | `~/.wikiforge/cognee/` (compartido vía env vars) |
| cognee-mcp (`~/.wikiforge/cognee-mcp/cognee-mcp/.venv/`) | 1.0.8 | 0.16.1 | `~/.wikiforge/cognee/` (compartido vía env vars) |

`cognee` no está perfectamente alineado (1.0.5 vs 1.0.8) pero la pieza crítica para compatibilidad de file format — `ladybug` — está idéntica a 0.16.1 en ambos venvs. El bug del `ladybug_version_mapping` upstream sigue ahí en cognee 1.0.5/1.0.8 (mapping solo hasta v_code 39); ambos venvs aplican el mismo patch en runtime.

### Validación end-to-end

Desde el cognee-mcp venv (con env vars del shim + patch del launcher), una `cognee.search(query_type=CHUNKS, query_text="ADR centralization", datasets=["WikiForge"])` devuelve **5 chunks**:

```
[1] [FILE kind=doc path=.memory/MEMORY.md] # MEMORY.md — Índice de gobernanza de WikiForge ...
[2] [FILE kind=doc path=AGENTS.md] # WikiForge — Project Instructions ...
[3] [FILE kind=doc path=.memory/decisions/0006-env-litellm-colon-dodge.md] # ADR 0006 — `.env` cognee-mcp real ...
```

Por tanto: el MCP server (al reiniciarse con el shim actualizado en próxima sesión Claude Code) verá el dataset WikiForge populado por el CLI WF.

### Limitaciones residuales

- **cognee 1.0.5 ≠ 1.0.8 entre venvs.** Si en el futuro un upgrade de uno (ej. cambio de schema) rompe la compatibilidad, hay que igualarlos. Mitigación: tests de smoke con `wikiforge eval` (Fase 2) detectarían la regresión.
- **El upgrade del cognee-mcp venv tocó `pyproject.toml` upstream.** Backup en `pyproject.toml.bak`. Si se hace `git pull` del cognee-mcp upstream, hay que re-aplicar el cambio. **TODO**: PR upstream para relajar el `cognee==1.0.0` strict pin.
- **Aún hay version skew menor entre ladybug y kuzu legacy.** En teoría compatible para reads, pero no testado exhaustivamente.

## Notas

Junto con ADR 0007, este es el segundo ciclo completo de promote→resolve via `wikiforge promote-decision`. El sistema demuestra capacidad real de gestionar TODOs cross-session: ADR 0007 fue promovido en N, resuelto en N+1; ADR 0008 fue promovido en N+1, resuelto en N+2 (esta sesión).
