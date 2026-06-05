# ADR 0012 — Reranker cloud vía OpenRouter (Cohere Rerank 4 Fast)

- **Estado:** Active
- **Fecha:** 2026-05-09
- **Decisor:** Daniel Alonso Gómez
- **Tags:** retrieval,reranker,fase-2,cloud-only,openrouter,cohere,sintoma-11.4
- **Supersedes:** [ADR 0011](./0011-reranker-bge-v2-m3.md) (proponía bge-reranker-v2-m3 LOCAL — descartado por política cloud-only).
- **Origen:** decisión de usuario 2026-05-09 — *"no quiero tener el modelo utilizado y descargado de manera local ya que me ocupa muchos gigas y tengo bastantes plataformas para poder utilizar cualquiera de sus modelos"*. Validado por deep-research 2026-05-09 (`~/Documents/Braid_Reranker_Research_20260509/research_report_20260509_braid_reranker.md`, 30+ fuentes triangulado).

---

## Contexto

El síntoma 11.4 (medido en Fase 0: Q2/Q3 a 0.5 — chunks correctos en top-5 pero top-1 falla) sigue activo. El ADR 0011 proponía resolverlo descargando bge-reranker-v2-m3 (568 MB) + sentence-transformers (~2 GB con torch) localmente. El usuario rechazó esa ruta por consumo de disco y declaró su preferencia por sus 9 proveedores cloud configurados (Hugging Face, ZenMux, Anthropic, Ollama Cloud, OpenRouter, Inception, OpenAI, GitHub Copilot, OpenCode Zen).

Una primera intuición fue usar Gemini Flash como LLM-as-judge reranker (la única API key disponible localmente en `~/.config/braid/secrets.env`). El deep-research realizado el 2026-05-09 con 16 búsquedas web paralelas y 30+ sources demostró que esta opción es subóptima en todos los ejes:

- **Calidad**: Gemini Flash promedia NDCG@10 = 0.68 vs 0.74 para rerankers purpose-built (degradación ~9% por query).
- **Coste**: $25-30 / 1.000 queries vs $2 / 1.000 (Cohere Rerank) — exactamente 10× más caro.
- **Latencia**: 1-2 s vs ~600 ms del cross-encoder dedicado.

El research identificó **Cohere Rerank 4 Fast vía OpenRouter** como ganador absoluto para Braid.

## Decisión

Adoptar **Cohere Rerank 4 Fast** como reranker primario, accedido vía **OpenRouter** (`https://openrouter.ai/api/v1/rerank`), con modelo `cohere/rerank-4-fast`. Razones decisivas:

1. **Cero descarga local** — cumple la restricción dura del usuario.
2. **OpenRouter ya está en el stack** del user (panel de 9 proveedores). Reutiliza la pasarela cloud existente; un solo billing point.
3. **Pricing $0/M tokens** (passthrough OpenRouter actualmente) según página oficial. Cohere directo cuesta $2/1.000 queries — barato pero el passthrough es free, lo que cubre el uso Braid solo-developer holgado.
4. **32K context window** — cubre cualquier chunk cognee (típicamente <2K tokens).
5. **100+ idiomas multilingüe** incluido español — cubre tu mix docs-ES + código-EN.
6. **Lowest latency en familia Cohere** — ~600 ms p50 (ZeroEntropy benchmarks 2025).
7. **API es REST simple** — requiere ~50 líneas de código sobre `httpx` (ya en deps por `commands/review.py` + `zenmux.py` existentes).

### Implementación prevista

1. Nueva sección en `~/.config/braid/secrets.env`: `OPENROUTER_API_KEY=...` (el user copia desde su panel OpenRouter en https://openrouter.ai/keys).
2. Helper `runner.rerank_via_openrouter(query, items, top_n=5, model="cohere/rerank-4-fast")` en `src/braid/runner.py`:
   - Carga API key vía `paths.load_secrets_into_env()`.
   - POST a `https://openrouter.ai/api/v1/rerank` con `httpx`.
   - Body: `{"model": "cohere/rerank-4-fast", "query": query, "documents": [_extract_text(it) for it in items], "top_n": top_n}`.
   - Response: array de `{index, relevance_score}` ordenado por score desc.
   - Devuelve `[items[hit.index] for hit in response]`.
   - Cache LRU `(query_hash, items_hash) → ordered_items` en memoria del proceso.
3. `runner.run_search(rerank=False)` opcional → si `True` y `OPENROUTER_API_KEY` disponible, reordena top-K antes de devolver.
4. `commands/eval.py` y `commands/ask.py` reciben flag `--rerank` (default off; activable per call).
5. `.kgconfig` opcional `reranker = "cohere/rerank-4-fast"` para hacer el modelo configurable por repo.

### Privacidad

- Los chunks que se envían al reranker contienen contenido del repo (código + docs). Cohere/OpenRouter aplican sus políticas privacy estándar. Esto es **opt-in por flag `--rerank`**: el usuario decide cuándo enviar.
- El reranker NO se activa automáticamente — la sec. 9.7 anti-patrón privacidad sigue respetada.

### Coste estimado

- Eval típico Braid (10 preguntas × 5 chunks × ~200 tokens/chunk = ~10.000 tokens por run): a $0.02/1M tokens (precio Cohere directo, peor caso si OpenRouter retira el passthrough free), **$0.0002 por run**. 5.000 runs = $1.
- Mientras OpenRouter pasa el modelo a $0: gratis.

## Bloqueador resuelto vs ADR 0011

ADR 0011 quedaba **Blocked por síntoma 11.8** porque sin reindex completo no había contenido sobre el cual probar el reranker. Esto sigue siendo cierto técnicamente (el dataset cognee de Braid sigue parcial). PERO ADR 0012 puede:

1. **Implementarse y verificarse mecánicamente** contra el dataset parcial (los 4 docs viejos: ADR 0006, AGENTS.md viejo, Plan 0002, MEMORY.md viejo) → el reranker funciona técnicamente.
2. **Demostrar calidad parcial**: las 4 preguntas del eval suite que ya aciertan (Q03, Q04, Q05, Q09) deberían mantenerse en 1.0; las 3 que están a 0.5 (Q06, Q07, Q10) podrían escalar a 1.0 si el reranker mueve el chunk correcto al top-1.
3. **El gain real** (Q01, Q02, Q08 escalando de 0.0) sigue gated por reindex completo, que requiere síntoma 11.8 cerrado.

Por tanto: ADR 0012 se puede activar y validar en mecánica + calidad parcial inmediatamente. El cierre del ciclo full requiere síntoma 11.8.

## Alternativas consideradas (descartadas con motivo)

| Alternativa | Por qué descartada |
|---|---|
| **bge-reranker-v2-m3 LOCAL** (ADR 0011 original) | Veto user explícito: consumo disco. |
| **LLM-as-judge con Gemini Flash** | 10× más caro y calidad inferior (NDCG@10 0.68 vs 0.74). Confirmado en deep-research [5][6]. |
| **Voyage rerank-2.5-lite** | Plan B excelente (200M tokens free, beats bge-m3 +13.59%) pero requiere `VOYAGE_API_KEY` extra signup; OpenRouter es zero-friction. |
| **Jina Reranker v2/v3** | 10M free tokens (vs 200M Voyage); v3 es top en code-retrieval (CoIR 63.28) pero Braid tiene mix docs/código, no code-pure. |
| **Mixedbread mxbai-rerank-large-v2** | BEIR top (57.49) pero solo vía Together AI / Featherless — proveedores no en stack del user. |
| **Qwen3-Reranker-4B** | Best en code retrieval (MTEB-Code 81.20) pero solo vía SiliconFlow / HF Endpoints. Reservado para Fase 3 si Braid se enfoca en repos código-pure. |
| **HF Inference Providers + bge-reranker-v2-m3** | Cumpliría el "no descarga local" pero el modelo es inferior (BEIR 51.8) a Cohere/Voyage. Sin ventaja real. |

Detalles completos en `~/Documents/Braid_Reranker_Research_20260509/research_report_20260509_braid_reranker.md`.

## Consecuencias

### Positivas

- Resuelve síntoma 11.4 (reranker activo) sin descarga local.
- Pricing predecible ($0 actualmente, ≤$0.0002/eval-run en peor caso).
- API simple HTTP — un solo módulo `runner.rerank_via_openrouter` (~50 líneas).
- Reusa OpenRouter ya integrado por commands/review.py + zenmux.py — coherencia stack.
- Multilingüe sólido — Q en español + paths inglés cubiertos.
- Future-proofing: si OpenRouter añade Voyage/Jina/Mixedbread/Qwen3 al catálogo, switch trivial via `.kgconfig.reranker`.

### Negativas

- Requiere API key OpenRouter en `~/.config/braid/secrets.env` — paso manual del user (5 segundos copiando desde su panel).
- Privacy: los chunks van a OpenRouter→Cohere. Mitigación: opt-in por flag `--rerank`; nunca automático.
- Si OpenRouter retira el passthrough $0, fallback a $2/1.000 queries de Cohere directo. Aceptable para volumen Braid (~1.000 evals = $2).

### Neutras

- Nueva dep transitiva: ya tenemos `httpx>=0.28,<1` por commands/review.py. Sin instalación nueva.
- ADR 0011 queda **Superseded** por este ADR.

## Verificación

1. ✅ Deep-research 30+ sources confirma recomendación.
2. ⏳ User añade `OPENROUTER_API_KEY` al `secrets.env`.
3. ⏳ `runner.rerank_via_openrouter` implementado.
4. ⏳ `braid eval --rerank` ejecuta sin errores.
5. ⏳ Comparativa run: `baseline-fase-2.json` (5.5/10) vs `<ts>-rerank.json`. Esperado: total sube a 7+/10 (Q06/Q07/Q10 escalando a 1.0); Q01/Q02/Q08 siguen 0.0 hasta reindex.
6. ⏳ Tras síntoma 11.8 cerrado + reindex completo: re-run eval con reranker. Esperado: total 8-9/10.

## Plan operativo

Plan 0006 reescrito (cloud-only) — ver `.memory/plans/0006-reranker-activation.md`.

## Referencias

- [Deep research report](~/Documents/Braid_Reranker_Research_20260509/research_report_20260509_braid_reranker.md) (30+ sources, 2026-05-09).
- [OpenRouter Rerank docs](https://openrouter.ai/docs/sdks/typescript/api-reference/rerank).
- [Cohere Rerank 4 Fast on OpenRouter](https://openrouter.ai/cohere/rerank-4-fast).
- AGENTS.md sec. 11.4 (síntoma activo).
- AGENTS.md sec. 9.7 (privacidad — respetada por opt-in).
- ADR 0011 (Superseded).
- Plan 0006 (reescrito).
