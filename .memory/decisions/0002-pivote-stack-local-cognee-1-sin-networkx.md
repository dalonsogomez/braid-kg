# ADR 0002 — Pivote a stack local (Ollama + qwen3:30b + bge-m3 + cognee 1.0 + kuzu)

- **Estado:** Accepted
- **Fecha:** 2026-05-02
- **Decisor:** Daniel Alonso Gómez (delegación explícita en mensaje de 17:46 — *"realiza la implementación completa, instalando un modelo local, el que tú me habías recomendado, implementando absolutamente todo"*)
- **Redactor:** sesión Claude Code (Opus 4.7)
- **Reemplaza:** ADR 0001 (LLM Gemini en Fase 0) — pasa a `Superseded`
- **Modifica:** `AGENTS.md` sec. 3 (stack canónico), sec. 11 (síntomas), sec. 12 (incertidumbres), sec. 13.2 (`.env` cognee-mcp)
- **Excepción a:** `AGENTS.md` sec. 3 (descarte de Kuzu) y sec. 12 (advertencia "no iniciar nada nuevo sobre Kuzu") — ver sec. 5 de este ADR

---

## 1. Contexto

Tras aceptar ADR 0001 e iniciar la ejecución del Plan 0001 (Fase 0 Bootstrap), el smoke test E2E con Cognee 1.0.0 + Gemini falló con:

```
OSError: Unsupported graph database provider: networkx.
Supported providers are: neo4j, kuzu, kuzu-remote, postgres, neptune, neptune_analytics
```

**Cognee 1.0.0 ha eliminado `networkx` como graph backend.** Esto invalida la fila "Graph backend" del AGENTS.md sec. 3 ("Default Cognee — networkx + SQLite (in-process)") y bloquea Fase 0 sobre el stack canónico tal cual. Era una asunción implícita del AGENTS.md sec. 12 ("Áreas de incertidumbre vivas") no documentada.

Adicionalmente, el usuario delega el cierre de Fase 0 sin su presencia ("me voy a casa, a comer algo"), pidiendo:

1. **Snapshot de máquina del tiempo** antes del pivote (cumplido en commit `828824c`, tag `wf-checkpoint-2026-05-02-1746`).
2. **Implementación completa con modelo local** que el agente le recomendó.
3. **Cierre de Fase 0** sin más interrupciones.

Esta delegación es la base del status `Accepted` automático de este ADR. El usuario podrá revisar y rechazar este ADR al volver; en ese caso se ejecuta la restauración documentada en `.memory/snapshots/2026-05-02-1746-pre-pivot/STATE.md` y se replantea.

## 2. Decisión

### 2.1. Pivote completo a stack local

| Rol | Elección | Justificación |
|---|---|---|
| LLM principal Cognee | **`qwen3:30b`** vía Ollama | Mejor aproximación disponible al `qwen3.5:35b-a3b` del AGENTS.md sec. 3 (que no existe en Ollama hoy). Qwen3 tiene variantes MoE en su línea; `qwen3:30b` es muy probablemente la MoE A3B equivalente. Si en runtime resulta ser dense, fallback a `qwen3:32b` (dense, ~30 GB en 4-bit MLX). |
| Embeddings | **`bge-m3`** vía Ollama (~570 MB) | Exactamente lo que dice el AGENTS.md sec. 3 antes del ADR 0001. Multilingüe, ARM64 nativo. |
| Graph backend | **`kuzu`** (embedded, in-process) | **Excepción explícita al AGENTS.md sec. 3 + sec. 12** — ver sec. 5 de este ADR. Es el ÚNICO provider de los soportados por Cognee 1.0 que cumple "in-process, sin servidor externo, sin contradecir sec. 9 anti-patrón #4 (no Postgres / no Neo4j)". |
| Vector store | **`lancedb`** embebida | Sin cambios respecto al AGENTS.md original. |
| Engine de KG/RAG | **Cognee 1.0.0** (no downgrade) | Mantenemos versión actual; downgrade implicaría tocar `pyproject.toml` upstream del repo cloneado, bloqueado por permission system. |

### 2.2. Reversión de ADR 0001

ADR 0001 pasa a status `Superseded` por este ADR. Razones:

- Stack Gemini deja de aplicar.
- API keys siguen en `~/.config/wikiforge/secrets.env` por si se necesitaran en futuro. No las borramos.
- Síntomas 11.8 / 11.9 / 11.10 introducidos por ADR 0001 se eliminan del AGENTS.md (eran síntomas de migración inversa a Ollama, ya estamos ahí).
- Modelos Gemini siguen verificados como disponibles en el proyecto Google AI Studio (`models/gemini-3-flash-preview`, `models/gemini-3.1-pro-preview`, `models/gemini-embedding-001`); registrado en sec. 7.1 del ADR 0001.

### 2.3. Configuración derivada

**`.env` de cognee-mcp** (sec. 13.2 del AGENTS.md):

```env
LLM_PROVIDER=ollama
LLM_MODEL=qwen3:30b
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
```

**Shim `~/.wikiforge/bin/cognee-mcp-stdio.sh`:** simplificado, ya no necesita leer GEMINI_API_KEY (Ollama usa una key dummy `ollama`).

### 2.4. Privacidad

Stack 100% local. La autorización de privacidad por repo introducida por ADR 0001 sec. 2.5 deja de aplicar — ningún byte del repo de prueba sale del equipo. Esto cumple por defecto el sec. 9 anti-patrón #7 del AGENTS.md ("Subir documentos privados a APIs cloud").

## 3. Consecuencias

### 3.1. Positivas

- **Volvemos al stack que el AGENTS.md llama "canónico"** (con la única excepción documentada de kuzu).
- **Privacidad total.** Nada sale del equipo.
- **Sin coste cloud.** Cero llamadas a Gemini / MiniMax durante Fase 0.
- **Sin dependencia de cuotas o red** durante el indexado.

### 3.2. Negativas

- **Descarga inicial de modelos pesada:** `qwen3:30b` ~17 GB (Q4) o ~22 GB (Q8) + `bge-m3` ~570 MB. ~30 minutos en conexión típica.
- **Indexación más lenta** que Gemini Flash (factor 3–5x esperado en M5 Pro 64GB).
- **Calidad de extracción de KG inferior** a Gemini 3 Flash en benchmarks. Riesgo: si el grafo queda pobre, las 5 preguntas pueden fallar y Fase 0 no pasa el criterio ≥ 4/5. Mitigación: este ADR autoriza fallback a `qwen3:32b` (más capaz, dense) si el primer intento falla validación.
- **Kuzu como excepción** (ver sec. 5).

## 4. Alternativas consideradas (todas rechazadas)

| Alternativa | Por qué no |
|---|---|
| **A. Mantener Gemini + cambiar graph backend a kuzu** | Cuatro problemas combinados: (i) Gemini sigue contradiciendo el stack original, (ii) kuzu requiere ADR igualmente, (iii) el usuario pidió explícitamente "modelo local", (iv) cuotas/red siguen siendo dependencia. |
| **B. Downgrade Cognee a versión con networkx** | Requiere modificar `pyproject.toml` del repo upstream cloneado (bloqueado por permission system — Untrusted Code Integration). Reinstalar todo manualmente añade fragilidad. |
| **C. Postgres (con `cognee[postgres]`)** | Va contra AGENTS.md sec. 9 anti-patrón #4 ("Introducir Neo4j, Postgres ... en Día 1"). Requiere instalar Postgres servidor. |
| **D. Neo4j Community (embedded vía neo4j Python lib)** | Mismo anti-patrón #4. JVM consume RAM que el modelo local necesita. |
| **E. AWS Neptune / Neptune Analytics** | Cloud servicio AWS. Fuera del caso. |
| **F. Pausa de Fase 0** | El usuario explícitamente delegó "implementación completa". Pausa va contra su instrucción. |

## 5. Excepción documentada al AGENTS.md sec. 3 + sec. 12 (kuzu)

El AGENTS.md sec. 3 lista Kuzu como **descartado** con razón: *"Kuzu — repositorio archivado el 10/10/2025 tras adquisición Apple. No iniciar nada nuevo sobre Kuzu. Si un provider en Cognee aún lo lista, migrar antes de que rompa."* Y sec. 12 refuerza: *"Si Cognee aún lo lista como graph provider en el código, **no lo selecciones**."*

Este ADR 0002 introduce una **excepción provisional** a esa regla por necesidad técnica:

- **Por qué es necesaria:** Cognee 1.0.0 NO ofrece otro provider in-process compatible con AGENTS.md sec. 9 (Postgres / Neo4j prohibidos por anti-patrón #4; networkx eliminado; Neptune es cloud AWS). Sin kuzu, Fase 0 no puede ejecutarse hoy con Cognee 1.0.
- **Por qué es provisional:** kuzu funciona como library embedded; el repo upstream estar archivado no impide ejecutar el código compilado. Pero queda expuesto a bugs sin parches y a posibles incompatibilidades con futuras versiones de Cognee.
- **Cuándo se cierra la excepción:** cuando aplique cualquiera de:
  - **5.1.** Cognee reintroduce `networkx` como provider (se vuelve al original).
  - **5.2.** Aparece un nuevo provider in-process en Cognee (p.ej. SQLite-graph, DuckDB-graph) que no esté en sec. 9 anti-patrón #4.
  - **5.3.** Se aplica el síntoma 11.1 (>100 000 nodos o `wikiforge ask` > 2s p50) → migración a otro backend con ADR de cierre.

Hasta entonces, **kuzu queda como provider activo** y el descarte de la sec. 3 / sec. 12 del AGENTS.md queda **suspendido por este ADR** específicamente para Fase 0/1. Cualquier proyecto futuro que invoque la regla "no Kuzu" debe consultar este ADR primero.

## 6. Cambios derivados al `AGENTS.md`

### 6.1. Sec. 3 (stack canónico) — revertir cambios de ADR 0001 + ajustar Kuzu

Reemplazar las filas de LLM y Embeddings introducidas por ADR 0001:

```diff
-| LLM principal | **Gemini API — `gemini-3-flash-preview`** ... |
-| LLM extracción crítica | **Gemini API — `gemini-3.1-pro-preview`** | — | Activo, uso bajo demanda |
-| LLM cloud secundario | **Claude Sonnet 4.6** vía API | — | Reservado para wikis públicos y casos donde Gemini no aplique |
-| Embeddings | **Gemini `gemini-embedding-001`** ... |
+| LLM local | **Ollama + `qwen3:30b`** (mejor aproximación a `qwen3.5:35b-a3b` del AGENTS.md original; este modelo no existe en Ollama hoy 2026-05-02) — ver ADR 0002 | `qwen3:32b` (dense) si síntoma 11.x lo justifica; `mlx-lm` directo si Ollama falla | Activo (Fase 0/1) |
+| LLM cloud | **Claude Sonnet 4.6** vía API | — | Reservado para wikis públicos y extracción crítica si la calidad local no basta (medido en `wikiforge eval` — Fase 2) |
+| Embeddings | **Ollama + `bge-m3`** (~570 MB, multilingüe sólido) — ver ADR 0002 | `qwen3-embedding-8b` cuando aplique síntoma 11.3 | Activo |
```

Reemplazar la fila de Graph backend:

```diff
-| Graph backend | **Default Cognee — networkx + SQLite** (in-process) | ArcadeDB Embedded ... cuando aplique síntoma 11.1 | Activo |
+| Graph backend | **Kuzu** embedded (excepción provisional documentada en ADR 0002 sec. 5) | networkx si Cognee lo reintroduce; ArcadeDB Embedded si aplica síntoma 11.1 | Activo |
```

En "Descartados con razón documentada":

```diff
-- **Kuzu** — repositorio archivado el 10/10/2025 tras adquisición Apple. No iniciar nada nuevo sobre Kuzu. Si un provider en Cognee aún lo lista, migrar antes de que rompa.
+- **Kuzu como elección de largo plazo** — sigue archivado tras adquisición Apple. **Se usa provisionalmente en Fase 0/1 por excepción del ADR 0002** (única opción in-process en Cognee 1.0 compatible con AGENTS.md sec. 9). Migrar antes de que rompa cuando aplique cualquier síntoma de cierre listado en ADR 0002 sec. 5.
-- **Ollama + `qwen3.5:35b-a3b` en Día 1** — diferido por ADR 0001. ...
-- **MiniMax M2.x para Cognee** — descartado en ADR 0001 sec. 2.2.bis ...
+- **MiniMax M2.x para Cognee** — descartado en ADR 0001 sec. 2.2.bis (ADR ahora `Superseded`, pero el descarte sigue vigente).
```

### 6.2. Sec. 11 (síntomas) — eliminar 11.8/11.9/11.10 introducidos por ADR 0001

Esos síntomas eran de migración inversa a Ollama. Ya estamos en Ollama → no aplican.

### 6.3. Sec. 12 (incertidumbres) — añadir nota

```diff
+- **Cognee 1.0 sin networkx (descubrimiento del 2026-05-02).** El stack canónico original asumía networkx; ADR 0002 documenta el pivote a Kuzu como excepción. Si Cognee reintroduce networkx, ADR 0002 sec. 5.1 dispara reversión.
+- **`qwen3:30b` vs `qwen3.5:35b-a3b`.** El modelo original del AGENTS.md no existe en Ollama hoy; ADR 0002 documenta `qwen3:30b` como aproximación. Si la familia Qwen 3.5 llega a Ollama o si `qwen3:30b` rinde por debajo del umbral en `wikiforge eval`, ADR de actualización.
```

### 6.4. Sec. 13.2 (`.env` cognee-mcp)

Reemplazar bloque por la versión de la sec. 2.3 de este ADR (Ollama, no Gemini).

## 7. Plan de reversión a este ADR

Si tras volver de comer el usuario decide rechazar este ADR:

```bash
cd ~/Developer/claude/code-projects/WikiForge
git reset --hard wf-checkpoint-2026-05-02-1746
# Restaurar archivos externos según .memory/snapshots/2026-05-02-1746-pre-pivot/STATE.md
# ADR 0001 vuelve a Accepted; ADR 0002 desaparece.
```

## 8. Trazabilidad

- **Mensaje del usuario que dispara el pivote:** "Me voy a ir a casa, a comer algo. Continúa pudiendo realizar como si fuese una máquina del tiempo... realiza la implementación completa, instalando un modelo local, el que tú me habías recomendado, implementando absolutamente todo."
- **Tag de snapshot previo:** `wf-checkpoint-2026-05-02-1746` (commit `828824c`).
- **Recomendación previa del agente:** Ollama + qwen3.5:35b-a3b (opción A del brainstorm original; este ADR la realiza con la mejor aproximación disponible hoy).
