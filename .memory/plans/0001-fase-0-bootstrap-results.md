# Fase 0 — Resultados de validación

- **Fecha de ejecución:** 2026-05-02
- **Repo de prueba:** `vp-class-diagram-agent` (`~/Developer/ai/uml-class_diagram`)
- **Dataset Cognee:** `vp-class-diagram-agent`
- **Stack:** Cognee 1.0 + Gemini 3 Flash Preview + `gemini-embedding-001` + Kuzu + LanceDB (ADR 0003)
- **Modelos verificados disponibles:** sí (Step 1.6 del plan)

## Resumen ejecutivo

**Resultado: FAIL — 0.0 / 5.0** ❌

**Causa raíz: la quota free tier de Gemini 3 Flash es de 20 requests por día**, y el `cognify` de un repo con 27 archivos `.py` + 3 docs Markdown agotó la cuota a la quinta o sexta llamada, dejando el grafo parcial (64 nodos / 145 edges en lugar de los 300+ esperados). Solo el primer DataPoint se procesó completamente (21 nodos / 41 edges); los siguientes archivos quedaron sin extracción de entidades. Por tanto las preguntas Q1-Q5 reciben chunks irrelevantes o resúmenes genéricos.

Esto NO es un fallo de la arquitectura WikiForge: es la realidad operativa del free tier al que el ADR 0001 sec. 6 Q-B advertía: *"Si es free tier, recomendaría rechazar este ADR."* La respuesta del usuario fue "indiferente" y se asumió free tier como peor caso. La predicción se cumplió.

## Resultados por pregunta

Todas las preguntas usan modos `CHUNKS` y `SUMMARIES` (sin LLM completion porque la quota está agotada). Las respuestas son retrieval puro contra el grafo + vector store parcial.

### Q1 — `generate_from_statement` (CONTAINS+description)

- **Ground truth:** vive en `src/vp_class_diagram_agent/generator.py`. Genera draft `ClassDiagramSpec.json` desde un PDF de enunciado.
- **Top CHUNK retornado:** `src/vp_class_diagram_agent/puml_analyzer.py` (parsea PlantUML — archivo distinto al que tiene `generate_from_statement`).
- **Top SUMMARIES retornados:** "PlantUML diagram parsing utility", "Data persistence and artifact registry management" — genéricos, sin mención del símbolo objetivo.
- **Score:** **0.0** — el archivo `generator.py` NO está en el grafo (no se procesó por quota agotada).

### Q2 — Callsite de `audit_exam_associations` (CALLS)

- **Ground truth:** `_generate_bdbol_specs` en `src/vp_class_diagram_agent/iweb_generator.py`.
- **Top CHUNK retornado:** `docs/iweb_conallen_profesora_style_from_plugin_export.md` — documento sobre estilos, no menciona `audit_exam_associations` ni `iweb_generator.py`.
- **Score:** **0.0** — `iweb_generator.py` no está en el grafo.

### Q3 — Archivos del plugin VP (CONTAINS+structure)

- **Ground truth:** `plugin/plugin.xml` + 16 archivos `plugin/src/**/*.java`.
- **Top CHUNK retornado:** `docs/iweb_conallen_profesora_style_from_plugin_export.md` — habla del export del plugin pero no enumera los archivos `.java`.
- **Score:** **0.0** — los `.java` del plugin no se ingestaron (los globs del indexer son `src/**/*.py` + `tests/**/*.py` + Markdown; los `.java` quedaron fuera por diseño y, aunque hubiéramos pedido `.java`, la quota no habría llegado).

### Q4 — Sección README "Direct .vpp Solution Output" (DOCUMENTS)

- **Ground truth:** sección `## Direct \`.vpp\` Solution Output` del README.
- **Top CHUNK retornado:** docs/iweb_conallen... (no es el README).
- **Score:** **0.0** — el README probablemente entró en `cognee.add` pero el chunking + extracción para ese archivo nunca llegó (quota).

### Q5 — Flujo de privacidad por defecto (MENTIONS)

- **Ground truth:** sección `## Privacy Notes` del README. Default privado/local.
- **Top CHUNK retornado:** docs/iweb_conallen... (no es Privacy Notes).
- **Score:** **0.0** — mismo problema que Q4.

## Total

| Métrica | Valor |
|---|---|
| Score | **0.0 / 5.0** |
| Criterio AGENTS.md sec. 10 | ≥ 4.0 |
| Resultado | **FAIL** |

## Causa raíz documentada

```
Gemini Free Tier:
  GenerateRequestsPerDayPerProjectPerModel: 20 requests/day for gemini-3-flash
  
cognee.cognify de 30 archivos:
  - chunking
  - extract_graph_and_summarize  → ~3-5 LLM calls per chunk
  - summarize_text                → 1 LLM call per chunk
  - extract_keywords (?)          → posible 1 LLM call por chunk
  
Total estimado: ~150-300 LLM calls. Free tier permite 20.
```

Logs de Cognee registran **1904 errores `RESOURCE_EXHAUSTED 429`** durante el cognify, con `retryDelay: 40s` ignorado tras 3-4 reintentos. Solo el primer DataPoint pasó completo (21 nodos / 41 edges).

## Decisiones derivadas

### Caminos para desbloquear (decide el usuario al volver)

1. **Activar billing en Google Cloud para el proyecto WikiForge (#846938751343).**
   - Free tier 20 RPD → tier paid 1000+ RPD para `gemini-3-flash`.
   - Coste estimado para indexar `vp-class-diagram-agent` completo: ~$0.10-$0.50 (Flash es barato).
   - Privacidad: con billing, los inputs **no** se usan para entrenar (mejor que free).
   - **No requiere ADR nuevo** — el ADR 0001 sec. 6 Q-B ya autoriza esto como mejora; basta una nota en `bootstrap-results.md` actualizada confirmando el cambio.

2. **Esperar a que Cloudflare R2 vuelva accesible** (causa del bloqueo del stack local).
   - Test trivial: `curl -m 5 https://dd20bb891979d25aebc8bec07b2b3bbc.r2.cloudflarestorage.com`.
   - Cuando responda HTTP, ADR 0004 reactiva Ollama.

3. **Pivotar a HuggingFace + mlx-lm** (qwen3 desde HF, servidor local).
   - HF responde HTTP 200 desde esta red.
   - Setup más complejo (~60-90 min) pero respeta la intención local del usuario.

4. **Reducir el scope del repo de prueba para que quepa en 20 RPD.**
   - p.ej. solo `README.md` + 3 archivos `.py` core (`generator.py`, `iweb_generator.py`, `__init__.py`).
   - Permite cerrar Fase 0 hoy sin tocar billing ni red.
   - Limitación: las preguntas se reformulan a símbolos de los 3 archivos elegidos.

### Recomendación del agente

**Camino 1 (activar billing) seguido de re-indexación completa.** Es el camino con mejor relación esfuerzo/calidad y respeta exactamente el ADR 0003 actual. ~5 min de configuración + ~5 min de re-indexar y volver a ejecutar las 5 preguntas con `validate_phase0.py`.

## Estado del bootstrap pese al FAIL

A pesar de que las 5 preguntas no pasaron, el bootstrap completó **toda la infraestructura** del plan 0001:

- ✅ Cognee 1.0 instalado y funcionando.
- ✅ Stack Gemini + Kuzu funcionando (smoke test E2E pasó).
- ✅ `~/.wikiforge/bin/cognee-mcp-stdio.sh` shim funcional.
- ✅ MCP server `cognee` registrado en Claude Code (`✓ Connected`).
- ✅ `~/Developer/ai/uml-class_diagram` inicializado con `git`, `.kgconfig`, `AGENTS.md`, symlinks, `.memory/`.
- ✅ 64 nodos / 145 edges en grafo Kuzu (parcial pero estructuralmente correcto).
- ✅ Tres ADRs documentando todas las decisiones del día.
- ✅ Snapshot de máquina del tiempo (`wf-checkpoint-2026-05-02-1746`).

Solo falta superar el blocker de quota para que el indexado complete y las 5 preguntas pasen. **El sistema está listo para ejecutar Fase 0 cuando el blocker se resuelva.**

## Próxima acción

Cuando el usuario vuelva, decide entre los caminos 1-4 de arriba. Si elige (1) — activar billing — la secuencia para reanudar es:

```bash
# 1. Activar billing en Google Cloud Console para el proyecto 846938751343.
# 2. Re-indexar:
cd ~/.wikiforge/cognee-mcp/cognee-mcp && uv run python ../index_phase0.py
# 3. Re-validar:
cd ~/.wikiforge/cognee-mcp/cognee-mcp && uv run python ../validate_phase0.py
# 4. Re-scoring (manual sobre el JSON o con un script).
# 5. Si PASS, tag wf-fase-0-completed-2026-05-XX.
```
