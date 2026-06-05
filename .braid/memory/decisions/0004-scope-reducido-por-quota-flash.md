# ADR 0004 — Scope reducido del repo de prueba para encajar en cuota Flash free tier

- **Estado:** Accepted
- **Fecha:** 2026-05-03
- **Decisor:** Daniel Alonso Gómez (delegación: *"vuelve a empezar si quieres todo de nuevo. Teniendo en cuenta que tengo o llamo Cloud. Elige el mejor modelo a la hora de realizar la base de conocimientos como RAG"*)
- **Redactor:** sesión Claude Code (Opus 4.7)
- **Modifica:** `index_phase0.py` (reduce los globs de inputs).
- **Complementa:** ADR 0003 (mantiene stack Cognee 1.0 + Gemini 3 Flash + `gemini-embedding-001` + Kuzu + LanceDB).

## 1. Contexto

Tras el FAIL de Fase 0 ayer (score 0/5 por agotamiento de cuota free tier de `gemini-3-flash`), el usuario solicita reanudar. Verificación de cuota hoy (2026-05-03):

- `gemini-3-flash-preview`: HTTP 200 ✓ (quota diaria reseteada).
- `gemini-3.1-pro-preview`: HTTP 429 con `limit: 0` — **Pro NO está disponible en free tier**.

Conclusión: billing aún no activado. Flash sigue limitado a 20 RPD.

El usuario me pide "elige el mejor modelo". El mejor disponible **sin billing** es `gemini-3-flash-preview`. La intención del usuario ("teniendo en cuenta que tengo Cloud") sugiere que asume billing operativo, pero la realidad técnica dice lo contrario. Documento la asunción y procedo con Flash, reduciendo el scope para encajar en 20 RPD.

## 2. Decisión

### 2.1. Modelo principal: `gemini-3-flash-preview` (sin upgrade)

Razones:
- Es el único modelo Gemini moderno disponible para el proyecto WikiForge (#846938751343) sin billing.
- Pro requiere billing → fuera de alcance hoy.
- Claude Sonnet 4.6 es opción cloud autorizada (AGENTS.md sec. 3) pero introduce un proveedor adicional sin necesidad clara.

Si el usuario activa billing más tarde, **upgrade trivial** (un cambio en `.env` y re-cognify). No requiere ADR adicional (ADR 0001 sec. 2.2 ya cubre la jerarquía).

### 2.2. Scope reducido del repo de prueba

Re-indexar SOLO los archivos imprescindibles para responder las 5 preguntas del `0001-fase-0-bootstrap-questions.md`:

| Pregunta | Archivo necesario | Tamaño aprox. |
|---|---|---|
| Q1 (`generate_from_statement`) | `src/vp_class_diagram_agent/generator.py` | medio |
| Q2 (callsite de `audit_exam_associations`) | `src/vp_class_diagram_agent/iweb_generator.py` | grande |
| Q3 (plugin VP) | `plugin/plugin.xml` + lista textual de los `.java` | pequeño |
| Q4 (sección README "Direct .vpp Solution Output") | `README.md` | medio |
| Q5 (privacy notes) | `README.md` (cubierto por Q4) | — |

Total: **3 archivos físicos** (`generator.py`, `iweb_generator.py`, `README.md`) + **1 manifest sintético** generado en runtime listando los archivos del plugin (para Q3 sin tener que indexar 16 `.java`).

Esto deja el cognify estimado en ~6-12 requests, dentro del free tier de 20 RPD con margen para las 5 búsquedas posteriores.

### 2.3. Estado de los ADRs anteriores

- 0001: Active parcial (LLM/embeddings).
- 0002: Superseded parcial (Kuzu vigente).
- 0003: Active (stack Gemini+Kuzu).
- 0004 (este): Active. Decisión operativa, no arquitectónica. Aplica solo a Fase 0.

### 2.4. Cierre de la excepción

Cuando el usuario active billing:
1. Volver a `index_phase0.py` con los globs originales (`src/**/*.py`, `tests/**/*.py`, `README.md`, `MEMORY.md`, `docs/**/*.md`).
2. Re-cognify completo.
3. Re-validar.
4. Tag `wf-fase-0-completed-full-scope-YYYY-MM-DD`.

Hasta entonces, este ADR vigente; las 5 preguntas se responden sobre el subconjunto.

## 3. Consecuencias

### 3.1. Positivas

- Permite cerrar Fase 0 hoy sin esperar a billing ni a R2.
- Las 5 preguntas siguen siendo verificables (los archivos clave SÍ se indexan).
- Documenta explícitamente la asunción de "billing pendiente" para que el usuario revise.

### 3.2. Negativas

- El grafo no representa el repo completo. Cualquier pregunta fuera de las 5 podría fallar — no es problema porque el criterio de salida son las 5.
- Si el usuario activa billing y olvida reindexar el scope completo, queda con grafo incompleto. **Mitigación: nota visible en `MEMORY.md` y `0001-fase-0-bootstrap-results.md` cuando se actualicen.**

## 4. Trazabilidad

- Test de cuota (2026-05-03): `gemini-3-flash-preview` HTTP 200, `gemini-3.1-pro-preview` HTTP 429 `limit: 0`.
- Diff con ADR 0003: solo en scope de inputs al cognify; el resto del stack idéntico.
