# Plan 0006 — Activación del reranker (síntoma 11.4)

- **Fecha de inicio:** 2026-05-09
- **Status:** Blocked (esperando síntoma 11.8 cierre)
- **ADR de referencia:** [0011](../decisions/0011-reranker-bge-v2-m3.md) (Proposed)
- **Bloqueador:** Ollama Cloud `kimi-k2.6:cloud` caído (síntoma 11.8 activo) — sin LLM no puedo cognify ni validar el reranker contra dataset completo.

## Tareas (ordenadas por bloqueo)

### A. Pre-requisitos para activación

A1. **Verificar Ollama Cloud** — `curl -m 10 http://localhost:11434/v1/chat/completions -H 'Content-Type: application/json' -d '{"model":"openai/kimi-k2.6:cloud","messages":[{"role":"user","content":"ok"}],"max_tokens":3}'`. Esperar respuesta <30 s.
A2. Si A1 falla durante >24h consecutivas: aplicar contingencia AGENTS.md sec. 11.8 (reversión a `qwen3:30b` local) → ADR de re-pivote stack.
A3. **Reindex completo del repo WikiForge** — `wikiforge index --rebuild`. Esperar conteo final >40 inputs en `~/.wikiforge/cognee/.data_storage/`.

### B. Activación del reranker

B1. Añadir `sentence-transformers>=3.0,<4` a `[project.optional-dependencies] cognee` en `pyproject.toml`.
B2. `uv sync` o `uv pip install sentence-transformers` en el venv WikiForge.
B3. Implementar helper `runner.rerank(query, items, top_n=10)`:
   - Cachea el modelo `BAAI/bge-reranker-v2-m3` en variable global (lazy load).
   - Recibe lista de items (output de `cognee.search`), extrae `_extract_text(item)`, computa `model.predict([(query, text)])` para cada chunk.
   - Devuelve la lista reordenada por score descendente.
B4. Modificar `runner.run_search(rerank=False)`: si `True`, llamar `rerank` antes de devolver.
B5. `commands/eval.py` y `commands/ask.py` añaden flag `--rerank` (default off).
B6. `.kgconfig` opcional `reranker = "bge-reranker-v2-m3"`.

### C. Validación

C1. `wikiforge eval --rerank` ejecuta sin errores nuevos.
C2. Run JSON guardado.
C3. Comparativa con `.memory/eval/runs/baseline-fase-2.json`: delta `recall@1` y `total`.
C4. Si `delta_recall@1 ≥ +0.20` → ADR 0011 → Status: **Active**. Mergear cambios.
C5. Si delta < +0.20 → ADR 0011 → Status: **Rejected**. Revertir cambios. Documentar ROI insuficiente.

### D. Cierre

D1. Update plan 0003 — TODO #3 ✅ resuelto (con resultado A/R).
D2. Update MEMORY.md.
D3. Commit + tag.

## Criterios de aceptación

- ⏳ A1 → A3 hechos (síntoma 11.8 cerrado, dataset reindexado).
- ⏳ B1 → B6 implementados.
- ⏳ C1 → C5 ejecutados con conclusión clara.
- ⏳ D1 → D3 cerrados.

## Riesgos

- **Síntoma 11.8 puede tardar días en cerrarse.** Plan: si pasa >7 días, aplicar A2 (reversión local).
- **sentence-transformers puede traer torch como dep transitiva** (~2 GB descarga). Aceptable; el M5 Pro tiene espacio. Verificar con `uv tree` antes.
- **bge-reranker-v2-m3 puede no escalar Q3** (manifiesto sintético, problema de chunk size, no de ranking). Mitigación: ya documentado en plan 0001 post-mortem. ADR 0011 reconoce que Q3 puede seguir 0.5 incluso con reranker — sería caso para boost por kind.

## Fuera de alcance

- qwen3-reranker-4b — alternativa más reciente; descartada por tamaño en ADR 0011.
- Activación automática del reranker en cada `wikiforge ask` — primero hay que medir delta. Si Active, se considera flip del default en otro ADR.
