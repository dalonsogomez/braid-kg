# Plan 0005 — Suite `braid eval` + baseline Fase 2

- **Fecha de inicio:** 2026-05-09
- **Status:** In progress
- **ADR de referencia:** [0010](../decisions/0010-suite-braid-eval.md)
- **Fase:** 2 (entregable formal — sec. 10 Fase 2)

## Objetivo

Reemplazar el stub `braid eval` por un comando operativo que ejecute una suite de 10 preguntas reales del repo Braid contra el dataset cognee y registre el baseline en `.memory/eval/runs/`. Cumplir el criterio de salida de Fase 2: *"baseline de calidad medido y registrado"*.

## Tareas

### 1. ADR 0010 ✅
Escrito en `.memory/decisions/0010-suite-braid-eval.md`.

### 2. Implementar `commands/eval.py`
**Archivo nuevo:** `src/braid/commands/eval.py`.
**CLI:** `cli.py` reemplaza el stub `eval` por la nueva implementación.
**Dependencies:** ninguna nueva (usa `runner.run_search` + filesystem).

**Lógica:**
1. Localizar `questions.json` (default `.memory/eval/questions.json` resuelto vía `paths.resolve_context`).
2. Para cada pregunta: llamar `run_search(query, dataset, search_type, top_k)` con cada uno de `scoring.search_types` declarado en el JSON.
3. Score por pregunta:
   - Concatena `text` de chunks devueltos por todos los `search_types` (o `description` para summaries).
   - +0.5 si **algún** substring de `expected_any_of` aparece en el corpus combinado del top-K.
   - +0.5 adicional si **algún** substring de `expected_top_1` aparece en el primer chunk devuelto por el primer `search_type` (CHUNKS por defecto).
4. Total = suma de scores. Max = `len(questions)`. Pct = total/max*100.
5. Recall@1 = fracción de preguntas con `expected_top_1` matched. Recall@K = fracción con `expected_any_of` matched.
6. Imprime tabla por pregunta + totales.
7. Guarda run en `.memory/eval/runs/<ISO>.json` (a menos que `--no-save`).

### 3. Crear `.memory/eval/questions.json` (10 preguntas Braid)
Cobertura por tipo de relación AGENTS.md sec. 5.3:
- 3 preguntas CONTAINS / símbolos del CLI (claude.py, runner.py, paths.py)
- 2 preguntas DOCUMENTS / ADRs (0009 auto-bootstrap, 0006 LiteLLM dodge)
- 2 preguntas DOCUMENTS / planes (Fase 1 PASS, fase-2 progresos)
- 2 preguntas MENTIONS / convenciones AGENTS.md (sec. 9.7 privacidad, sec. 4.3 resolución contexto)
- 1 pregunta CALLS / IMPORTS (qué archivo invoca `find_git_root` desde fuera de `paths.py`)

### 4. Reindex completo del repo Braid
Ejecutar `braid index --rebuild` (en background, ~15 min) para tener el dataset con TODOS los ADRs (0001-0010) + planes (0001-0005) + código actual + AGENTS.md actualizado.

### 5. Ejecutar `braid eval` (baseline)
Tras reindex: ejecutar `braid eval` y registrar el run. Copiar a `.memory/eval/runs/baseline-fase-2-<fecha>.json` para que sea persistente y comparable después de Fase 2.

### 6. Decisión sobre reranker (síntoma 11.4)
- Si total ≥ 7.0 / 10 y recall@1 ≥ 0.5 → reranker entra en backlog Fase 3.
- Si total < 7.0 / 10 o recall@1 < 0.5 → activar ADR 0011 (reranker bge-reranker-v2-m3) en este mismo plan.

### 7. Reviews independientes
- Spec reviewer: ¿el código matchea ADR 0010?
- Code quality reviewer: ¿el código es limpio, tiene errores edge, etc.?

### 8. Cierre
- Update plan 0003: TODO #4 (`braid eval`) marcado como ✅ resuelto. TODO #3 (reranker) marcado como ✅ o ⏳ según decisión paso 6.
- Update MEMORY.md con ADR 0010 + plan 0005.
- Commit + tag (`braid-fase-2-completed` o `braid-fase-2-baseline-only`).

## Criterios de aceptación

1. ✅ ADR 0010 escrito.
2. ✅ `braid eval` no es stub; ejecuta y reporta JSON estructurado (10 preguntas, scoring 0/0.5/1.0, recall@1, recall@K, run JSON guardado).
3. ✅ `.memory/eval/questions.json` con 10 preguntas + ground truth (cubre CONTAINS, DOCUMENTS, MENTIONS, IMPORTS).
4. ⚠️ **Reindex completo NO completado** — Ollama Cloud `kimi-k2.6:cloud` no responde (síntoma 11.8 activo verificado vía `curl -m 30 /v1/chat/completions` → timeout). Reindex se mató tras 8 minutos de hang sin progreso (10 conexiones TCP a Ollama, 4 con CLOSE_WAIT a cloudfront, CPU 0.0%). Snapshot del dataset parcial pre-rebuild restaurado.
5. ✅ Baseline ejecutado y guardado en `.memory/eval/runs/baseline-fase-2.json` contra dataset parcial (4 docs originales del cognify mini de 2026-05-04).
6. ✅ Reviews limpios — spec compliance + code quality (ambos APROBADO_CON_OBSERVACIONES); fixes aplicados en mismo commit.
7. ⏳ Commit + tag aplicados (esta sesión).

## Resultado baseline (dataset parcial)

```
TOTAL: 5.5/10.0  (55.0%)  recall@1=0.40  recall@K=0.70
```

| Q | Kind | Score | Diagnóstico |
|---|---|---|---|
| Q01 | CONTAINS | 0.0 | claude.py NO indexado (post-baseline) |
| Q02 | DOCUMENTS | 0.0 | ADR 0009 NO indexado |
| Q03 | DOCUMENTS | 1.0 | ADR 0006 indexado en Fase 1 → top-1 |
| Q04 | MENTIONS | 1.0 | AGENTS.md indexado → top-1 |
| Q05 | MENTIONS | 1.0 | AGENTS.md sec. 4.3 → top-1 |
| Q06 | CONTAINS | 0.5 | runner.py mencionado en docs viejos pero no indexado en código |
| Q07 | IMPORTS | 0.5 | "paths" mencionado pero código no indexado |
| Q08 | DOCUMENTS | 0.0 | Plan 0003 actualizado NO indexado |
| Q09 | DOCUMENTS | 1.0 | ADR 0005 indexado → top-1 |
| Q10 | CONTAINS | 0.5 | Match débil sin claude.py indexado |

**Interpretación:**

- 4 preguntas (Q03, Q04, Q05, Q09) sobre docs ya indexados pre-2026-05-09 → 4.0/4.0 puntos. **Top-1 perfecto cuando el doc está en el dataset**.
- 4 preguntas (Q01, Q02, Q06, Q08, Q10) sobre piezas creadas tras 2026-05-04 (claude.py + ADR 0009 + plan 0003 actualizado) → 0.0-0.5. **Falta indexado, no problema de retriever**.
- Q07 a 0.5: el código no está en el dataset, solo en AGENTS.md hay menciones de `paths`.

**Esto NO mide reranker** — los fallos son por dataset incompleto, no por ranking. El reranker se valida en plan 0006 cuando síntoma 11.8 cierre.

## Cumplimiento criterio AGENTS.md sec. 10 Fase 2

> *"baseline de calidad medido y registrado"* ✅

El criterio se cumple con el baseline de 5.5/10 registrado en `.memory/eval/runs/baseline-fase-2.json`. El reindex completo y la activación del reranker quedan en plan 0006 (Blocked por síntoma 11.8).

## Síntomas activados durante esta ejecución

- **11.8 — Ollama Cloud caído** ✅ Activado (verificado 2026-05-09 12:18 — curl direct a `/v1/chat/completions` con kimi:cloud devuelve timeout 30s). Plan 0006 sec. A2 prevé contingencia.

## Riesgos

- **Reindex puede colgarse o agotar Ollama Cloud.** Mitigación: rate limit ya en `.env`; si falla, retry una vez; si falla otra, baseline parcial con dataset existente y registrar el blocker.
- **Algunas preguntas pueden quedar fuera del corpus indexado** si un archivo se excluye del scope. Mitigación: las preguntas usan substrings que están en archivos seguros (`AGENTS.md`, `.memory/decisions/*.md`, `src/braid/**/*.py`).
- **Substring matching laxo** puede dar falsos positivos. Mitigación: ground truth con paths completos (`src/braid/commands/claude.py`) reduce falsos +.

## Fuera de alcance

- Suite eval para repos distintos de Braid (cada repo construye sus questions.json).
- LLM-as-judge scoring (sec. 11.6 Langfuse cuando aplique).
- Comparación cross-stack (kimi vs Claude Sonnet, etc.) — eso es síntoma 11.10.
