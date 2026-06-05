# ADR 0006 — `.env` cognee-mcp real: dodge de bugs de LiteLLM y `OllamaEmbeddingEngine`

- **Estado:** Accepted
- **Fecha:** 2026-05-03
- **Decisor:** Daniel Alonso Gómez (autorización autónoma "sigue continuando si crees que queda mejor" tras PASS de Fase 0)
- **Redactor:** sesión Claude Code (Opus 4.7)
- **Complementa:** ADR 0005 (sustituye su sec. 2.2 con el `.env` que realmente funcionó)
- **No reemplaza:** stack vigente sigue siendo el de ADR 0005 (kimi-k2.6:cloud + bge-m3 local + Kuzu + LanceDB)

---

## 1. Contexto

El `.env` propuesto en ADR 0005 sec. 2.2 (y replicado en `AGENTS.md` sec. 13.2) describe el stack ideal pero **no funciona literalmente** por tres bugs/limitaciones en el ecosistema upstream descubiertos durante el bootstrap de Fase 0:

1. **LiteLLM parser de `:` en model name.** Con `LLM_PROVIDER=ollama` + `LLM_MODEL=ollama/kimi-k2.6:cloud`, LiteLLM corta el modelo en el primer `:` y queda `kimi-k2.6` (perdiendo el sufijo `:cloud`). Resultado: 404 model not found.
2. **`OllamaEmbeddingEngine` envía `dimensions` al endpoint nativo `/api/embed`.** El endpoint nativo de Ollama lo rechaza con `422 Unprocessable Entity`. Cognee 1.0 hardcodea el envío de `dimensions` en el payload aunque el `EMBEDDING_ENDPOINT` sea el path nativo.
3. **Pydantic validation requiere `HUGGINGFACE_TOKENIZER`.** Cuando `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL` y `EMBEDDING_DIMENSIONS` se setean manualmente, Cognee 1.0 obliga a setear también `HUGGINGFACE_TOKENIZER` o falla en boot del config.

A esto se suma un cuarto problema operativo:

4. **`429 too many concurrent requests` desde Ollama Cloud durante cognify.** Cognee dispara extracciones LLM en paralelo. Con kimi-k2.6:cloud la cuota de concurrencia se satura. Sin rate limit, todo el cognify falla.

## 2. Decisión

### 2.1. `.env` real (sustituye ADR 0005 sec. 2.2 y `AGENTS.md` sec. 13.2)

```env
# Stack ADR 0005 con dodges ADR 0006:

# --- LLM ---
# Dodge LiteLLM ':' parser: usar provider=openai con model=openai/<name> apuntando al
# endpoint OpenAI-compat de Ollama (puerto 11434/v1). Esto bypassea el codepath nativo
# de LiteLLM-ollama que parte el name en el primer ':'.
LLM_PROVIDER=openai
LLM_MODEL=openai/kimi-k2.6:cloud
LLM_ENDPOINT=http://localhost:11434/v1
LLM_API_KEY=ollama

# Rate limit estricto para evitar el 429 "too many concurrent requests" de Ollama Cloud
# durante cognify (que dispara extracciones LLM paralelas).
LLM_RATE_LIMIT_ENABLED=true
LLM_RATE_LIMIT_REQUESTS=2
LLM_RATE_LIMIT_INTERVAL=5

# --- Embeddings ---
# Dodge OllamaEmbeddingEngine /api/embed 422: usar el path OpenAI-compat
# /v1/embeddings (que sí acepta `dimensions` en payload, aunque lo ignore).
# Mantenemos provider=ollama para que el engine respete HUGGINGFACE_TOKENIZER en lugar
# de TikToken (LiteLLMEmbeddingEngine no conoce bge-m3 y crashea con KeyError).
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=bge-m3
EMBEDDING_ENDPOINT=http://localhost:11434/v1/embeddings
EMBEDDING_API_KEY=ollama
EMBEDDING_DIMENSIONS=1024

# Pydantic validation gate: requerido cuando se setean los EMBEDDING_* manualmente.
HUGGINGFACE_TOKENIZER=BAAI/bge-m3

# --- Backend graph + vector ---
GRAPH_DATABASE_PROVIDER=kuzu
VECTOR_DB_PROVIDER=lancedb

# --- Ergonomía Cognee 1.0 ---
ENABLE_BACKEND_ACCESS_CONTROL=false
COGNEE_SKIP_CONNECTION_TEST=true

# Autenticación con Ollama Cloud para modelos `:cloud` se hace una vez vía:
#   ollama login
# (no requiere variables de entorno)
```

### 2.2. Cambios al `AGENTS.md`

Reemplazar el bloque de `AGENTS.md` sec. 13.2 entero por el contenido de la sec. 2.1 de este ADR. La sec. 3 (stack canónico) no cambia.

### 2.3. Diagnóstico del doble `ollama serve` (ADR de soporte, no decisión arquitectónica)

El bug más insidioso de la sesión fue tener simultáneamente `/opt/homebrew/.../ollama serve` (homebrew) y `/Applications/Ollama.app/.../ollama serve` (app), ambos bindeando puerto 11434 (uno IPv4, otro IPv6). Provocaba `GGML_ASSERT([rsets->data count] == 0) failed` al cargar `qwen3:30b` localmente porque dos procesos compiten por la misma GPU/Metal context.

**Diagnóstico:** `lsof -nP -iTCP:11434 -sTCP:LISTEN` muestra ambos.

**Mitigación elegida en sesión:** bypassear local con `:cloud` (sin necesidad de matar daemons). Si se necesita ejecución local, dejar solo uno (apagar Ollama.app menubar O `brew services stop ollama`).

Esto se añade como nuevo síntoma 11.11 en `AGENTS.md` sec. 11 vía esta misma ADR.

### 2.4. Nuevo síntoma 11.11

| ID | Síntoma observable | Migración asociada | Comando indicativo |
|---|---|---|---|
| 11.11 | `GGML_ASSERT([rsets->data count] == 0) failed` o "model runner has unexpectedly stopped" al cargar modelo local en Ollama | Verificar que solo hay UN `ollama serve` en port 11434 | `lsof -nP -iTCP:11434 -sTCP:LISTEN`. Si hay dos: apagar Ollama.app O `brew services stop ollama`, dejar solo uno. |

## 3. Consecuencias

### 3.1. Positivas

- **El stack vigente se puede reproducir.** Copiando el `.env` de la sec. 2.1 + `ollama login` + scripts del bootstrap, la Fase 0 es repetible.
- **Síntoma 11.11 documentado.** Si en el futuro algún agente IA mete una recomendación tipo "tu Ollama está crasheando, reinstala" se le puede señalar el síntoma para diagnosticar antes de actuar.
- **Trazabilidad ADR-driven preservada.** AGENTS.md no se toca sin ADR (anti-patrón #5 respetado).

### 3.2. Negativas

- **Pareja de hacks frágil.** Tres workarounds simultáneos contra bugs upstream. Si Cognee/LiteLLM/Ollama refactorizan cualquiera de los tres codepaths, el `.env` puede romperse en silencio.
- **Mitigación:** suite `wikiforge eval` (Fase 2) detectará la regresión cuando se introduzca. Hasta entonces, las preguntas de validación de Fase 0 sirven como smoke test manual.

### 3.3. Cuándo este ADR queda obsoleto

- Cuando LiteLLM arregle el parser de `:` para Ollama (issue upstream pendiente de identificar).
- Cuando `OllamaEmbeddingEngine` deje de hardcodear `dimensions` o se añada flag `OLLAMA_EMBED_USE_NATIVE_API=false` con default OpenAI-compat.
- Cuando Cognee 1.x relaje la validación pydantic de tokenizer cuando provider=ollama.

Si cualquiera de los tres se resuelve upstream, abrir ADR 0007 simplificando el `.env`.

## 4. Trazabilidad

- **Bootstrap del 2026-05-03**: sesión Claude Code completó Fase 0 con score 4.0/5.0 usando exactamente este `.env`. Ver `.memory/plans/0001-fase-0-bootstrap-results.md` y commit `5d65d24`.
- **Tag de cierre:** `wf-fase-0-completed-2026-05-03`.
