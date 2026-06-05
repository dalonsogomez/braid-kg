# Plan 0006 — Activación reranker cloud vía OpenRouter (v2)

- **Fecha de inicio:** 2026-05-09 (v1 superseded mismo día por v2 cloud-only)
- **Status:** In progress
- **ADR de referencia:** [0012](../decisions/0012-reranker-cloud-cohere-openrouter.md) (Active). Supersede [ADR 0011](../decisions/0011-reranker-bge-v2-m3.md) (Superseded).
- **Bloqueador parcial:** Síntoma 11.8 sigue activo (Ollama Cloud caído) — bloquea el reindex completo y por tanto el gain MÁXIMO del reranker. Pero NO bloquea la activación mecánica del reranker contra dataset parcial (4 docs).

## Tareas

### A. Implementación reranker (sin bloqueador)

A1. ✅ ADR 0012 escrito.
A2. ⏳ User añade `OPENROUTER_API_KEY=...` a `~/.config/wikiforge/secrets.env`. Acción manual: copiar desde https://openrouter.ai/keys. Es un paso de 5 segundos.
A3. ⏳ Implementar `src/wikiforge/runner.py::rerank_via_openrouter(query, items, top_n=5, model="cohere/rerank-4-fast")`:
   - POST a `https://openrouter.ai/api/v1/rerank` vía `httpx` (ya en deps).
   - Lee API key de `os.environ["OPENROUTER_API_KEY"]` tras `paths.load_secrets_into_env()`.
   - Body JSON: `{"model": ..., "query": ..., "documents": [...], "top_n": ...}`.
   - Response: `{"results": [{"index": int, "relevance_score": float}, ...]}` ordenado.
   - Devuelve `[items[r["index"]] for r in response["results"][:top_n]]`.
   - Cache LRU `(hash(query), hash(tuple(_extract_text(it) for it in items))) → ordered_indices`.
   - Manejo errores: HTTPException, Timeout, MissingKey → log + devuelve `items[:top_n]` (degraded mode).
A4. ⏳ Modificar `runner.run_search(rerank=False, top_k=10)`:
   - Si `rerank=True` y `OPENROUTER_API_KEY` disponible: tras cognee.search, llamar `rerank_via_openrouter`.
   - Si `rerank=True` y key NO disponible: log warn + devuelve unsorted (no falla).
A5. ⏳ Modificar `commands/eval.py`:
   - Añadir flag `--rerank` (default off).
   - Pasarlo a `run_search(rerank=...)`.
   - Incluir flag en `run_doc.meta.reranker_used: bool` para que el JSON del run lo registre.
A6. ⏳ Modificar `commands/ask.py` (opcional, para `wikiforge ask "..." --rerank`):
   - Mismo flag.

### B. Validación (sobre dataset parcial — sin bloqueador)

B1. ⏳ Test mecánico: con dataset parcial (4 docs), ejecutar `wikiforge eval --rerank` y verificar:
   - El comando NO falla.
   - El JSON del run incluye `meta.reranker_used: true`.
   - Las preguntas que ya estaban en 1.0 (Q03, Q04, Q05, Q09) se mantienen.
   - Las preguntas que estaban a 0.5 (Q06, Q07, Q10) — observar si suben a 1.0.
   - Las preguntas a 0.0 (Q01, Q02, Q08) — siguen 0.0 (dataset no contiene los docs).
B2. ⏳ Comparativa: copiar el run a `.memory/eval/runs/with-rerank-fase-2.json`. Computar delta vs `baseline-fase-2.json` (5.5/10):
   - Esperado: total sube a 6.5-7.0/10 (Q06/Q07/Q10 → 1.0 si reranker funciona).
   - Si total NO sube: el reranker no diferencia chunks suficientemente — investigar (probablemente porque los chunks que están en top-5 son ya muy similares; necesitamos reindex completo para cubrir las preguntas a 0.0).

### C. Validación end-to-end (BLOQUEADA por síntoma 11.8)

C1. ⏳ Resolver síntoma 11.8 — ver Plan 0003 TODO #6. Tareas:
   - C1.a: Verificar Ollama Cloud `kimi-k2.6:cloud` cada sesión (`curl -m 8 ...`). Si vivo → reactivar.
   - C1.b: Si caído >7 días: aplicar AGENTS.md sec. 11.8 → switch LLM cognify a `qwen3:30b` LOCAL (ya descargado, 18 GB). PERO esto contradice la política cloud-only del user. Mejor opción: switch a `anthropic/claude-sonnet-4.6` o similar vía OpenRouter (mismo provider que ya usamos para reranker). Esto requiere ADR de re-pivote stack LLM.
C2. ⏳ Tras C1: `wikiforge index --rebuild` con LLM cloud alternativo. Esperar 15-30 min para re-cognify completo.
C3. ⏳ Re-run `wikiforge eval --rerank` contra dataset completo. Esperado: 8-9/10, recall@1 ≥ 0.7.

### D. Cierre

D1. ⏳ Actualizar plan 0003 — TODO #3 (reranker) ✅ resuelto vía ADR 0012.
D2. ⏳ Actualizar MEMORY.md con ADR 0012 + plan 0006 v2.
D3. ⏳ Commit + tag (`wf-fase-2-reranker-cloud-active` o similar).

## Criterios de aceptación

- ⏳ A2-A6 implementados.
- ⏳ B1-B2 ejecutados con resultado registrado.
- ⏳ Si B2 muestra mejora ≥ +1.0 en total: ADR 0012 confirmado **Active**.
- ⏳ Si B2 muestra mejora < +1.0: documentar en plan + abrir investigación (probablemente reindex es prerrequisito).
- ⏳ C1-C3 quedan en backlog hasta síntoma 11.8 cerrado.
- ⏳ D1-D3 cerrados al final de cada batch (B-batch o C-batch).

## Riesgos

- **OpenRouter retira el passthrough $0 entre el ADR y la implementación**. Mitigación: el código tolera $2/1.000 queries Cohere directo — sigue siendo barato para WikiForge. Documentado en ADR 0012.
- **API key OpenRouter no funciona** o tiene rate limits estrictos. Mitigación: `runner.rerank_via_openrouter` cae a degraded mode (devuelve unsorted top_n) y log warn. El comando NO falla; solo no aplica reranker.
- **B2 muestra que el reranker no mejora baseline**. Causa probable: el dataset parcial es DEMASIADO PARCIAL (solo 4 docs). Mitigación: documentar como findng en B2; reranker se valida finalmente en C-batch tras reindex.
- **Síntoma 11.8 cierra mientras esta sesión avanza** (Ollama Cloud vuelve). Mitigación: detección automática vía `curl` antes de cualquier reindex; si vivo, proceder con C-batch en misma sesión.

## Fuera de alcance

- bge-reranker-v2-m3 LOCAL — descartado por ADR 0012.
- LLM-as-judge con Gemini Flash — descartado por ADR 0012 (10× más caro, peor calidad).
- Voyage / Jina / Mixedbread / Qwen3-Reranker — alternatives identificadas en deep-research, reservadas para Fase 3 si Cohere via OpenRouter no satisface.
- Embedding upgrade (bge-m3 → qwen3-embedding-8b) — sigue Fuera de alcance hasta síntoma 11.3 medido.

## Referencias

- [ADR 0012](../decisions/0012-reranker-cloud-cohere-openrouter.md).
- [Deep-research report](~/Documents/WikiForge_Reranker_Research_20260509/research_report_20260509_wikiforge_reranker.md) (30+ sources, mayo 2026).
- [Plan 0003 sec. TODOs Fase 2](./0003-fase-2-progresos.md) — TODO #3 (reranker), TODO #6 (síntoma 11.8).
- [OpenRouter Rerank API](https://openrouter.ai/cohere/rerank-4-fast).
