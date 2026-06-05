# ADR 0003 — Re-pivote a Gemini API + Kuzu por bloqueo de red Cloudflare R2

- **Estado:** Accepted
- **Fecha:** 2026-05-02
- **Decisor:** Daniel Alonso Gómez (delegación explícita + necesidad técnica forzosa)
- **Redactor:** sesión Claude Code (Opus 4.7)
- **Reemplaza parcialmente:** ADR 0002 (en lo que respecta a Ollama y embeddings locales). El uso de Kuzu como graph backend SE MANTIENE.
- **Reactiva parcialmente:** ADR 0001 (en lo que respecta a Gemini API). ADR 0001 vuelve a `Active` solo en lo concerniente a LLM y embeddings.
- **Modifica:** `AGENTS.md` sec. 3 (filas LLM y embeddings) y sec. 13.2 (`.env` cognee-mcp)

---

## 1. Contexto

Tras aceptar el ADR 0002 (pivote a stack local), el bootstrap se inició con `brew install ollama` exitoso, pero los `ollama pull bge-m3` y `ollama pull qwen3:30b` fallaron con `i/o timeout` contra `dd20bb891979d25aebc8bec07b2b3bbc.r2.cloudflarestorage.com` (Cloudflare R2, donde Ollama aloja todos los blobs de modelos).

Diagnóstico de red (desde esta máquina, esta sesión, hora 2026-05-02 ~20:20 CEST):

| Endpoint | Resultado |
|---|---|
| `https://registry.ollama.ai/v2/library/bge-m3/manifests/latest` | `HTTP 200` ✓ |
| `https://huggingface.co` | `HTTP 200` ✓ |
| `https://generativelanguage.googleapis.com` | `HTTP 404` ✓ (host responde) |
| `https://dd20bb891979d25aebc8bec07b2b3bbc.r2.cloudflarestorage.com` | `Connection timed out (28)` ✗ |
| `ping 172.64.66.1` | 100% packet loss ✗ |

**Cloudflare R2 selectivamente inaccesible** desde esta red (causa probable: routing / firewall / VPN / DNS / problema de Cloudflare en esta zona). HuggingFace y Google sí responden.

Eso bloquea Ollama por completo: no hay forma de descargar modelos sin R2.

El usuario está fuera del equipo y delegó "implementa absolutamente todo, instalando un modelo local". La intención local no es realizable hoy. Tres caminos posibles:

1. **Esperar a que R2 vuelva** — sin garantía de tiempo, viola "implementa todo".
2. **Pivotar a HuggingFace + mlx-lm** — qwen3-30B desde HF + servidor local OpenAI-compat. ~60-90 min adicional + complejidad de integración con cognee.
3. **Pivotar a Gemini cloud** — ya verificado en ADR 0001, modelos disponibles, ~15 min para arrancar.

Coste/beneficio: opción 3 cumple "todo terminado" y la intención original "modelo local" queda como objetivo diferido (ADR futuro cuando R2 vuelva o el usuario apruebe la ruta HF+mlx-lm).

## 2. Decisión

### 2.1. Stack final operativo

| Rol | Elección | Origen |
|---|---|---|
| LLM principal Cognee | **`gemini-3-flash-preview`** | ADR 0001 sec. 2.2 reactivado |
| LLM extracción crítica | **`gemini-3.1-pro-preview`** | ADR 0001 sec. 2.2 reactivado |
| Embeddings | **`gemini-embedding-001`** (3072 dims) | ADR 0001 sec. 2.2 reactivado |
| Graph backend | **`kuzu`** (embedded) | ADR 0002 sec. 5 mantenido (excepción provisional al sec. 12 del AGENTS.md) |
| Vector store | **`lancedb`** | Sin cambios |
| Engine de KG/RAG | **Cognee 1.0.0** | Sin cambios |

### 2.2. Configuración

**`.env` de cognee-mcp:**

```env
LLM_PROVIDER=gemini
LLM_MODEL=gemini/gemini-3-flash-preview
EMBEDDING_PROVIDER=gemini
EMBEDDING_MODEL=gemini/gemini-embedding-001
EMBEDDING_DIMENSIONS=3072
GRAPH_DATABASE_PROVIDER=kuzu
VECTOR_DB_PROVIDER=lancedb
ENABLE_BACKEND_ACCESS_CONTROL=false
```

**Shim `~/.braid/bin/cognee-mcp-stdio.sh`:** revertido al patrón del ADR 0001 sec. 2.4 (lee `GEMINI_API_KEY` desde `~/.config/braid/secrets.env`).

### 2.3. Privacidad

Vuelve a aplicar la autorización del ADR 0001 sec. 6 (Q-A respondida sí: archivos públicos, Q-B indiferente). Sigue acotada al repo `~/Developer/ai/uml-class_diagram`.

### 2.4. Estado de los ADRs anteriores

- **ADR 0001 (Gemini):** vuelve a `Active` parcialmente. Las modificaciones al AGENTS.md de la sec. 6 del ADR 0001 (filas de stack) se reaplican, pero las síntomas 11.8/11.9/11.10 introducidas por ADR 0001 permanecen colapsadas en el síntoma único 11.8 que ADR 0002 dejó (calidad insuficiente del LLM medida en `braid eval`).
- **ADR 0002 (Local + kuzu):** queda como `Superseded en su parte LLM/embeddings`. La parte de **Kuzu como graph backend (sec. 5 del ADR 0002) sigue vigente** y es la que evita reabrir el blocker de Cognee 1.0 sin networkx.
- **ADR 0003:** Active. Es el ADR vigente que define el stack actual.

### 2.5. Trayectoria que el usuario tendrá al volver

Cuando el usuario regrese y revise:

1. **Snapshot disponible:** tag `braid-checkpoint-2026-05-02-1746` (commit `828824c`) — punto previo al primer pivote.
2. **Tres ADRs apilados:**
   - 0001 (Gemini, propuesto y reactivado por 0003).
   - 0002 (Local, Superseded en LLM/embeddings; mantiene kuzu).
   - 0003 (Re-pivote a Gemini por R2 caído, vigente).
3. **Decisión esperada del usuario:**
   - **Aceptar** — Fase 0 cerrada con stack mixto Gemini+kuzu.
   - **Rechazar** y volver a checkpoint — todo se descarta y replanteamos.
   - **Reabrir local** cuando R2 vuelva — ADR 0004 que vuelva a Ollama.

## 3. Consecuencias

### 3.1. Positivas

- Permite cerrar Fase 0 hoy, sin esperar a que R2 vuelva.
- Calidad de extracción superior (Gemini 3 Flash > Ollama qwen local en SWE-bench).
- Sin descarga de 17 GB de modelos.

### 3.2. Negativas

- Stack cloud — no cumple la intención "modelo local" del usuario, pero está documentado como decisión forzosa, no preferencial.
- Datos del repo viajan a Google (autorización ya concedida en ADR 0001 sec. 6 Q-A).
- Tres ADRs en un día introduce densidad de gobernanza alta — defendible porque cada pivote tiene causa técnica concreta y registrada.

## 4. Plan de cierre del re-pivote

Cuando aplique cualquiera de:

- **4.1.** R2 vuelve a ser accesible (test: `curl https://...r2.cloudflarestorage.com` no timea).
- **4.2.** El usuario configura una ruta alternativa (VPN, DNS, proxy) que llegue a R2.
- **4.3.** El usuario acepta la ruta HF+mlx-lm (descarga qwen3 desde HuggingFace + servidor mlx-lm con endpoint OpenAI).

→ ADR 0004 que reabra el camino local (probablemente parecido al ADR 0002 con ajustes), y este ADR 0003 pasa a `Superseded`.

## 5. Trazabilidad

- **Mensaje del usuario que dispara el re-pivote forzoso:** la delegación de las 17:46 ("realiza la implementación completa, instalando un modelo local, el que tú me habías recomendado, implementando absolutamente todo") choca con la realidad de la red. Este ADR documenta la imposibilidad de cumplirla literalmente y elige el camino que más se acerca al "implementación completa".
- **Logs de Ollama** que justifican el blocker:
  ```
  i/o timeout dialing 172.64.66.1:443 (Cloudflare R2)
  registry.ollama.ai → HTTP 200 OK
  huggingface.co → HTTP 200 OK
  ```
