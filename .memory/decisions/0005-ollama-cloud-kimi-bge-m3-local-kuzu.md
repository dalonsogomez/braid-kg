# ADR 0005 — Stack final Fase 0: Ollama Cloud (kimi-k2.6) + bge-m3 local + Kuzu

- **Estado:** Accepted
- **Fecha:** 2026-05-03
- **Decisor:** Daniel Alonso Gómez (delegación: *"Recuerda que lo tienes que hacer con Ollama, sí o sí"* + *"como tengo Cloud"* — interpretado como **Ollama Cloud** que el usuario tiene activo, evidenciado por el modelo `kimi-k2.6:cloud` ya registrado en `ollama list`)
- **Redactor:** sesión Claude Code (Opus 4.7)
- **Reemplaza:** ADR 0003 (Gemini cloud) y ADR 0004 (scope reducido por quota Flash)
- **Mantiene de ADR 0002 sec. 5:** la excepción documentada para Kuzu como graph backend

---

## 1. Contexto

Tras dos días pivoteando entre Gemini cloud (bloqueado por quota free tier) y Ollama local (bloqueado por Cloudflare R2 inaccesible ayer), los descubrimientos de hoy 2026-05-03 cambian el cuadro:

1. **Cloudflare R2 vuelve a responder** (`HTTP 400` al GET vacío vs ayer `connection timeout`). Ollama puede descargar modelos.
2. **El usuario tiene plan Ollama Cloud activo** — evidenciado por la presencia del modelo `kimi-k2.6:cloud` en su `ollama list` desde hace 5 horas. La frase "como tengo Cloud" del mensaje anterior se reinterpreta a la luz de este hallazgo: no era GCP billing ni Anthropic — era **Ollama Cloud**, un servicio de Ollama Inc. que ejecuta modelos pesados remotamente sin requerir descargas locales.
3. **Cuotas Gemini agotadas en free tier** (LLM y embeddings) — irrelevante ahora que Ollama es viable.

El usuario reitera ("sí o sí") que el stack debe ser Ollama. Este ADR cumple esa instrucción combinando:
- Ollama Cloud para el LLM (sin descarga, plan ya pagado).
- Ollama local + bge-m3 para embeddings (570 MB, R2 funciona).

## 2. Decisión

### 2.1. Stack final

| Rol | Elección | Origen |
|---|---|---|
| LLM principal Cognee | **`kimi-k2.6:cloud`** vía Ollama Cloud | Plan Ollama Cloud del usuario (modelo ya disponible en su `ollama list`). Kimi K2 (Moonshot AI) es un MoE de gran calidad; el sufijo `:cloud` indica ejecución remota. |
| Embeddings | **`bge-m3`** local vía Ollama (1024 dims) | Lo que el AGENTS.md sec. 3 original quería. Descarga única ~570 MB. Sin cuota recurrente. |
| Graph backend | **`kuzu`** (embedded) | Mantiene la excepción provisional del ADR 0002 sec. 5 (Cognee 1.0 sin networkx). |
| Vector store | **`lancedb`** | Sin cambios. |
| Engine | **Cognee 1.0.0** | Sin cambios. |

### 2.2. `.env` cognee-mcp

```env
LLM_PROVIDER=ollama
LLM_MODEL=ollama/kimi-k2.6:cloud
LLM_ENDPOINT=http://localhost:11434/v1
LLM_API_KEY=ollama
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=bge-m3
EMBEDDING_ENDPOINT=http://localhost:11434/v1
EMBEDDING_API_KEY=ollama
EMBEDDING_DIMENSIONS=1024
GRAPH_DATABASE_PROVIDER=kuzu
VECTOR_DB_PROVIDER=lancedb
ENABLE_BACKEND_ACCESS_CONTROL=false
COGNEE_SKIP_CONNECTION_TEST=true
```

Notas:
- El cliente Ollama local (puerto 11434) hace de proxy hacia el servidor Cloud para los modelos `:cloud`. Cognee no necesita saber que es cloud; el endpoint sigue siendo `http://localhost:11434/v1` (compat OpenAI).
- `LLM_API_KEY=ollama` es placeholder; la autenticación real con Ollama Cloud se hace vía `ollama login` que el usuario ya ejecutó (de lo contrario `kimi-k2.6:cloud` no aparecería).

### 2.3. Scope vuelve al original (full repo)

ADR 0004 redujo el scope a 3 archivos por la cuota Gemini. **Con Ollama Cloud + bge-m3 local NO HAY cuota de requests por día** — solo el throughput/coste del plan Ollama Cloud, que el usuario ya paga. Por tanto, el `index_phase0.py` vuelve a procesar:

- `src/**/*.py` (27 archivos Python)
- `README.md` + `MEMORY.md` + `docs/**/*.md`
- Manifest sintético del plugin (sec. 2.2 del ADR 0004 lo mantiene útil para Q3).

### 2.4. Estado de los ADRs anteriores

- 0001 (Gemini): Superseded definitivo (no se va a reactivar).
- 0002 (Local stack): Superseded en LLM (kimi-k2.6:cloud lo cubre); **Kuzu sec. 5 sigue Active** (sin alternativa in-process en Cognee 1.0).
- 0003 (Re-pivote a Gemini por R2): Superseded (R2 ya funciona; Gemini ya no aplica).
- 0004 (Scope reducido por quota Flash): Superseded (sin cuota de Gemini, scope completo viable).
- 0005 (este): Active. Stack vigente.

## 3. Consecuencias

### 3.1. Positivas

- **No depende de cuotas free tier.** Ollama Cloud es el plan pagado del usuario; sin RPD limitante para el cognify.
- **Sin descarga de 17-22 GB.** El modelo Kimi K2.6 corre remotamente en Ollama Cloud.
- **Privacidad mejor que Gemini free.** Ollama Cloud tiene términos más alineados con uso profesional (no entrenan con prompts según ToS estándar de Ollama Inc; verificar términos del plan antes de cualquier ingesta sensible).
- **Embeddings 100% local** — los vectores no salen de la máquina. Solo los textos van a Ollama Cloud durante extracción de KG.
- **Kimi K2.6 es muy capaz** en razonamiento estructurado y código (top tier en SWE-bench y MMLU según benchmarks Moonshot 2025).

### 3.2. Negativas

- **Latencia de red** para cada llamada al LLM. Para 30 archivos con varios chunks cada uno, esto suma. Estimado: 5-15 min para el cognify completo.
- **Privacidad parcial.** Los chunks de código/docs SÍ se envían a Ollama Cloud para extracción. Esto **no contradice** AGENTS.md sec. 9 anti-patrón #7 porque el repo de prueba `uml-class_diagram` está autorizado para envío cloud por ADR 0001 sec. 6 Q-A (que el usuario respondió "sí, archivos públicos"). La autorización transitiva aplica: si Gemini estaba autorizado, Ollama Cloud también lo está bajo el mismo criterio.
- **Dependencia de un servicio adicional.** Ollama Cloud puede tener downtime (poco frecuente pero existe). El stack local-only sigue siendo posible: descargar `qwen3:30b` o equivalente con `ollama pull` (R2 funciona ahora) y cambiar `LLM_MODEL` por la versión local.

## 4. Plan de reversión / fallback

Si Ollama Cloud falla:
1. `ollama pull qwen3:30b` (~17 GB; ahora posible).
2. Editar `.env` `LLM_MODEL=qwen3:30b`.
3. Re-cognify.

Si bge-m3 local falla:
1. `ollama pull qwen3-embedding-4b` (cuando esté en Ollama).
2. Editar `.env` `EMBEDDING_MODEL`.

Si kuzu causa problemas:
1. Aplicar síntoma 11.1 → ArcadeDB.

## 5. Cambios derivados al `AGENTS.md`

### 5.1. Sec. 3 (stack canónico)

Reemplazar las filas LLM/embeddings introducidas por ADR 0003 con:

```diff
-| LLM principal | **Gemini API — `gemini-3-flash-preview`** ... — ver ADR 0003 |
-| LLM extracción crítica | **Gemini API — `gemini-3.1-pro-preview`** | ... |
-| LLM cloud secundario | **Claude Sonnet 4.6** vía API | ... |
-| Embeddings | **Gemini `gemini-embedding-001`** ... — ver ADR 0003 |
+| LLM principal | **Ollama Cloud — `kimi-k2.6:cloud`** (Kimi K2.6 de Moonshot AI servido remotamente vía plan Ollama Cloud) — ver ADR 0005 | Local `qwen3:30b` si Ollama Cloud falla; Claude Sonnet 4.6 vía API si calidad insuficiente | Activo (Fase 0/1) |
+| LLM cloud secundario | **Claude Sonnet 4.6** vía API | — | Reservado para wikis públicos y casos donde Kimi no aplique |
+| Embeddings | **Ollama local — `bge-m3`** (~570 MB, multilingüe, 1024 dims) — ver ADR 0005 | `qwen3-embedding-8b` cuando aplique síntoma 11.3 | Activo |
```

### 5.2. Sec. 13.2 (`.env` cognee-mcp)

Reemplazar bloque por la versión de la sec. 2.2 de este ADR.

### 5.3. Sec. 11

Eliminar el síntoma 11.8 colapsado por ADR 0002 (era de "calidad insuficiente del LLM medida en wikiforge eval"). Reemplazar por:

```diff
+| 11.8 | Ollama Cloud caído > 1 vez por semana o latencia > 5s p50 | Reversión a `qwen3:30b` local | `ollama pull qwen3:30b` + cambiar LLM_MODEL en .env |
+| 11.9 | Coste mensual del plan Ollama Cloud sobre umbral acordado | Reversión a stack 100% local o cambio de plan | Idem 11.8 + revisar plan |
```

## 6. Trazabilidad

- **Mensaje del usuario:** *"Recuerda que lo tienes que hacer con O llama, sí o sí."* + presencia de `kimi-k2.6:cloud` en `ollama list` confirma plan Ollama Cloud activo.
- **R2 status check (2026-05-03):** HTTP 400 (vivo); ayer connection timeout.
- **Test funcional `kimi-k2.6:cloud`:** "thinking" + reply OK en menos de 30s.
- **Modelos verificados disponibles:** kimi-k2.6:cloud (cloud), bge-m3 (descarga en curso desde R2).
