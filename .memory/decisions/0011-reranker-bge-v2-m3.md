# ADR 0011 — Reranker bge-reranker-v2-m3 (síntoma 11.4 — propuesto, activación pendiente)

- **Estado:** Proposed (activación pendiente — ver sec. "Bloqueador" más abajo)
- **Fecha:** 2026-05-09
- **Decisor:** Daniel Alonso Gómez
- **Tags:** retrieval,reranker,fase-2,sintoma-11.4,bge-reranker
- **Origen:** Fase 0 Q2/Q3 medidas a 0.5 (recuperables top-5, no top-1) → síntoma 11.4 verificado. Plan 0003 TODO #3 explícito.

---

## Contexto

Fase 0 cerró con `4.0/5.0` por dos preguntas (Q2 callsite de `audit_exam_associations`, Q3 inventario archivos plugin VP) atascadas en 0.5: el chunk canónico estaba indexado y aparecía en top-5 chunks devueltos por bge-m3, pero no en top-1. El reordenamiento de top-K → top-1 es exactamente lo que hace un cross-encoder reranker.

`wikiforge eval` ya implementa la infraestructura para medir el delta: con reranker activo, la métrica `recall@1` debería subir conservando `recall@K`. Si Q2/Q3 escalan a 1.0 y otras no se degradan, el ROI es claro.

## Decisión

Activar **bge-reranker-v2-m3** (BAAI, MIT, ~568 MB, multilingüe) como paso post-search en `runner.run_search`. Razones de la elección concreta vs alternativas:

| Modelo | Pros | Contras |
|---|---|---|
| **bge-reranker-v2-m3** ✅ | Mismo lab que bge-m3 (consistencia), MIT, ARM64 vía sentence-transformers, ~568 MB, multilingüe, cross-encoder estándar de facto | Tamaño moderado; descarga única desde HF |
| qwen3-reranker-4b | Más reciente, multilingüe excelente | 4 B params → más RAM, descarga ~8 GB, exceso para 10 preguntas |
| Sin reranker, top-k=20 vs 10 | Cero deps nuevas | No mejora ranking, solo recall — ya está a 0.7 |

### Implementación prevista

1. Nueva dep en `pyproject.toml [project.optional-dependencies] cognee`: `sentence-transformers>=3.0,<4`.
2. Helper `runner.rerank(query, items, top_n)` que carga `BAAI/bge-reranker-v2-m3` lazy, cachea el modelo en RAM, computa scores para `(query, _extract_text(item))` y reordena.
3. `runner.run_search(rerank=True)` opcional → reordena top-K antes de devolver.
4. `commands/eval.py` y `commands/ask.py` reciben flag `--rerank` (default off; activable per call).
5. `.kgconfig` añade `reranker = "bge-reranker-v2-m3"` opcional.
6. `wikiforge eval` con `--rerank` ejecuta y guarda como nuevo run; comparación con baseline mide delta.

### Privacidad / coste

- 100 % local — sentence-transformers ejecuta el modelo en CPU/GPU del Mac. Ningún dato sale.
- Latencia adicional por query: ~50-200 ms para 10 chunks en M5 Pro 64 GB. Aceptable.
- RAM extra: ~600 MB cuando el modelo está cargado. Aceptable.

## Bloqueador (2026-05-09)

**El reindex completo necesario para validar el reranker está bloqueado por síntoma 11.8 activo:** Ollama Cloud `kimi-k2.6:cloud` no responde (timeout 30 s en `/v1/chat/completions`). Sin LLM, `cognify` no puede extraer entities/edges → el grafo permanece parcial (4 docs viejos del 2026-05-04). Reranker sobre dataset parcial mide poco.

**Plan operativo:**

1. **Esta sesión**: ADR escrito, código del reranker preparado pero NO mergeado. Marcado como "Proposed".
2. **Próxima sesión que retome WikiForge**:
   - Verificar Ollama Cloud (`curl -m 10 http://localhost:11434/v1/chat/completions ...`).
   - Si vivo: `wikiforge index --rebuild` → completar.
   - Si sigue caído >24h: aplicar AGENTS.md sec. 11.8 reversión a `qwen3:30b` local (ya descargado, `ollama ls` lo confirma) — requiere ADR de re-pivote.
3. **Tras reindex completo**: instalar `sentence-transformers`, activar el helper `runner.rerank`, correr `wikiforge eval --rerank`, comparar con `baseline-fase-2.json`. Si delta `recall@1` ≥ +0.20, marcar este ADR como "Active". Si no, archivar como "Rejected — beneficio insuficiente".

## Alternativas consideradas

| Alternativa | Descartada porque |
|---|---|
| Activar reranker AHORA contra dataset parcial | Mide ruido, no señal. Síntoma 11.4 ya se verificó en Fase 0 con dataset completo del repo de prueba. |
| Saltar reranker, ir directo a qwen3-embedding-8b | Sec. 11.3 requiere síntoma de fallo multilingüe medido — no hay. Cambiar embedder sin medir es hipotetizar. |
| FlagEmbedding directo en lugar de sentence-transformers | sentence-transformers tiene API más limpia y es la dep que el ecosistema espera. FlagEmbedding es upstream pero peor mantenido. |

## Consecuencias

### Positivas (cuando se active)

- Q2/Q3 esperadas a 1.0 → total 5/5 en repo de prueba Fase 0.
- recall@1 sube sin tocar recall@K.
- Aplicable a cualquier repo gobernado por WikiForge — el reranker no es repo-específico.

### Negativas

- 568 MB descarga inicial (HF).
- 600 MB RAM cuando cargado.
- Nueva dep — superficie de mantenimiento.
- Si HF está caído, primer arranque del reranker falla. Mitigación: cache local del modelo tras primera descarga.

### Bloqueo actual

- Síntoma 11.8 activo (Ollama Cloud caído) impide validación end-to-end.
- ADR queda **Proposed** hasta que Ollama Cloud vuelva o se re-pivote a local.

## Verificación pendiente

1. `pip install sentence-transformers` resuelve sin conflictos en el venv WikiForge.
2. Primera carga del modelo descarga ~568 MB de HF.
3. `runner.rerank(query, [chunk1..chunk10], top_n=10)` devuelve los mismos 10 chunks reordenados.
4. `wikiforge eval --rerank` ejecuta sin nuevos errores.
5. Comparativa con `baseline-fase-2.json`: delta recall@1 medido y reportado.

## Referencias

- AGENTS.md sec. 11.4 (síntoma activo).
- AGENTS.md sec. 11.8 (síntoma actualmente activo bloqueando).
- ADR 0010 (suite eval — herramienta para validar este ADR).
- Plan 0003 sec. TODOs Fase 2 #3.
- Plan 0001-fase-0-bootstrap-results.md sec. Q2 / Q3 (medición original).
- Modelo: https://huggingface.co/BAAI/bge-reranker-v2-m3 (MIT).
