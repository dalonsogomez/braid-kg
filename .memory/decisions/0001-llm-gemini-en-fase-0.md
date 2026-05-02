# ADR 0001 — Sustituir el LLM local de Fase 0 por Gemini

- **Estado:** Superseded by [ADR 0002](0002-pivote-stack-local-cognee-1-sin-networkx.md)
- **Fecha propuesta:** 2026-05-02
- **Fecha aceptada:** 2026-05-02
- **Fecha superada:** 2026-05-02 (mismo día — Cognee 1.0 sin networkx hizo inviable el stack Gemini sin pivote arquitectónico mayor)
- **Decisor:** Daniel Alonso Gómez (`daniel@dalonsogomez.com`)
- **Redactor:** sesión Claude Code (Opus 4.7), bajo brainstorming Superpowers
- **Modifica:** `AGENTS.md` sec. 3 (stack canónico) y sec. 13.2 (`.env` de cognee-mcp)
- **Relacionado:** `AGENTS.md` sec. 9 anti-patrón #5 (este ADR es el requisito previo), sec. 9 anti-patrón #7 (autorización cloud explícita), sec. 12 (estado preview de Ollama 0.19 + MLX)
- **Reemplaza:** —
- **Reemplazado por:** —

---

## 1. Contexto

El AGENTS.md sec. 3 fija el stack canónico de Fase 0/1 con **Ollama 0.19+ con backend MLX + `qwen3.5:35b-a3b`** como LLM local y **Claude Sonnet 4.6** como LLM cloud reservado para extracción crítica. La sec. 12 advierte que *"En marzo 2026 [Ollama 0.19] era preview. Si la versión disponible cuando ejecutes Día 1 no es estable, baja a Ollama 0.18 con llama.cpp o ve directo a `mlx-lm`. La arquitectura no depende de la implementación concreta del backend local."*

Hoy (2 mayo 2026), al iniciar Fase 0 sobre `~/Developer/ai/uml-class_diagram`, el usuario propone **sustituir el LLM local por Gemini API** (Google AI Studio) en lugar de instalar Ollama + descargar `qwen3.5:35b-a3b` (~22 GB en 4-bit MLX) + `bge-m3` (~570 MB).

Argumentos del usuario implícitos en la elección:

- Evitar instalar y operar Ollama 0.19 cuya estabilidad era preview en marzo 2026.
- Evitar descargar ~22 GB de pesos para un modelo que solo se usará para grounding sobre repos pequeños/medianos.
- Setup más simple: una API key, un endpoint REST, sin gestión de procesos locales.

Este ADR es el requisito previo del sec. 9 anti-patrón #5 ("Modificar este `AGENTS.md` sin ADR asociado"). Ningún cambio al `AGENTS.md` ni al plan de Fase 0 entra en commit hasta que este ADR pase de `Proposed` a `Accepted`.

## 2. Decisión

### 2.1. Cambio principal

Sustituir, **solo en Fase 0 y Fase 1**, el LLM local Ollama+qwen3.5:35b-a3b por **Gemini API** como provider de LLM en Cognee, manteniendo intacto el resto de la arquitectura (MCP-first, tres niveles de memoria, esquema de KG mínimo, promoción manual, AGENTS.md como contrato único).

### 2.2. Modelos concretos (versionado fijo, no aliases móviles)

| Rol | Modelo Gemini | Justificación |
|---|---|---|
| LLM principal Cognee (`cognify`, `codify`, `search`) | **`gemini-3-flash-preview`** (o `gemini-3-flash` cuando llegue a GA) | Lanzado 17 dic 2025. **78% en SWE-bench Verified**, supera a Gemini 2.5 Pro siendo 3× más rápido. Contexto 1M tokens. Pricing: $0.50/1M input, $3/1M output. La calidad en tareas de coding y extracción estructurada justifica preferirlo sobre 2.5 Flash. |
| LLM de respaldo para extracción crítica | **`gemini-3.1-pro-preview`** | Cuando `gemini-3-flash` falle en extracción de relaciones complejas o multi-saltos. Mismo provider, mismo SDK, no añade dependencia. |
| Embeddings | **`gemini-embedding-001`** (3072 dims) | Multilingüe sólido (el AGENTS.md sec. 11.3 cita "preguntas multilingües código-español" como síntoma de upgrade desde bge-m3 → qwen3-embedding-8b; Gemini cubre eso de salida). Permite **prescindir de Ollama por completo** en Fase 0. |

**Estado preview asumido y registrado.** A 2 mayo 2026, `gemini-3-flash` y `gemini-3.1-pro` están en preview oficial de Google. La incertidumbre se anota en `AGENTS.md` sec. 12 ("Áreas de incertidumbre vivas") como nuevo bullet. Si Google retira o reconfigura los IDs `*-preview` antes del GA, este ADR se reabre con un addendum.

**Aliases móviles prohibidos:** queda explícitamente vetado usar `gemini-flash-latest`, `gemini-pro-latest` o cualquier alias `-latest` que pueda mutar sin aviso. Cualquier upgrade de modelo (p.ej. `gemini-3-flash-preview` → `gemini-3-flash` GA) requiere addendum a este ADR — justificación: AGENTS.md sec. 7 ("migraciones por síntomas observables, nunca por anticipación").

### 2.2.bis. MiniMax Code Subscription: por qué no es la elección

Aunque el usuario tiene suscripción activa a MiniMax Code Plan, este ADR descarta MiniMax para Fase 0 por cinco razones técnicas:

1. **MiniMax no es first-class en Cognee.** Habría que configurarlo vía provider `custom` o pasar por OpenRouter como middleware. Más superficie de fallo.
2. **El Coding Plan está powered by MiniMax M2.1, no por el flagship M2.7.** La diferencia en extracción estructurada (function calling, JSON schemas) es real frente a Gemini 3 Flash.
3. **Quota en ventanas rolling de 5 h** (RPM/TPM). Una indexación inicial de Cognee paralelizada puede agotar la ventana en minutos.
4. **El Coding Plan está optimizado para coding-agent loops** (Cline, Kilo Code, Claude Code) que iteran con un humano, no para un servidor batch (cognee-mcp) que extrae KG.
5. **Calidad SWE-bench:** Gemini 3 Flash 78% vs MiniMax M2.7 ~56% (SWE-Pro). Y la suscripción te da M2.1, no M2.7.

MiniMax conserva un nicho legítimo en el setup: como **modelo de chat dentro de Claude Code/Cursor** vía el Coding Plan, no como provider de Cognee.

### 2.3. Configuración de Cognee

Reemplaza el bloque `.env` de la sec. 13.2 del AGENTS.md por:

```env
LLM_PROVIDER=gemini
LLM_MODEL=gemini/gemini-3-flash-preview
LLM_API_KEY=<leído desde ~/.config/wikiforge/secrets.env, NUNCA en este archivo>
EMBEDDING_PROVIDER=gemini
EMBEDDING_MODEL=gemini/gemini-embedding-001
EMBEDDING_DIMENSIONS=3072
GRAPH_DATABASE_PROVIDER=networkx
VECTOR_DB_PROVIDER=lancedb
```

### 2.4. Gestión de secretos

- La `GEMINI_API_KEY` vive **fuera del repo** en `~/.config/wikiforge/secrets.env` con permisos `600`.
- `cognee-mcp` la carga vía `--env-file ~/.config/wikiforge/secrets.env` o vía variable de entorno exportada por el shell del usuario.
- **Está prohibido**: escribir la key en `.env` del repo, en `AGENTS.md`, en cualquier ADR o plan, en commits, en el wrapper MCP futuro, o en cualquier archivo bajo control de versiones.
- El `.gitignore` del repo de prueba (`uml-class_diagram`) y de WikiForge incluirá `*.env`, `secrets.env`, `*.secret` por defecto.

### 2.5. Autorización de ingesta cloud (sec. 9 anti-patrón #7)

Este ADR autoriza el envío a Google Gemini API **solo** del repositorio `~/Developer/ai/uml-class_diagram` para Fase 0. La autorización cubre:

- Código fuente Python en `src/` y `tests/`.
- Documentación en `README.md`, `MEMORY.md`, `docs/`.
- Schema files en `schema/`.
- Plugin Java en `plugin/` (lectura para grounding).

La autorización **no** cubre:

- `_backup_pre_8bugs_*` ni `_backups_claude_code/` (excluidos por `.gitignore`/glob explícito).
- `output/` (artefactos generados, irrelevantes para grounding).
- Cualquier otro repositorio del usuario. **Cada repo nuevo requiere su propia autorización explícita** (puede ser por anotación en su `.kgconfig` o por ADR en su `.memory/decisions/`).

## 3. Consecuencias

### 3.1. Positivas

- **Setup en minutos, no horas.** No hay descarga de 22 GB ni gestión de procesos locales.
- **Calidad de extracción superior** a `qwen3.5:35b-a3b` en tareas de KG (Gemini 2.5 Flash supera a modelos open de tamaño comparable en benchmarks de razonamiento estructurado).
- **Embeddings de calidad sin instalar nada local** (Gemini embedding-001 cubre multilingüe).
- **Prescindible Ollama por completo en Fase 0.** Reduce superficie de fallos (Ollama 0.19 + MLX en preview) a cero.
- **Compatible con Cognee out-of-the-box** vía `LLM_PROVIDER=gemini` (LiteLLM debajo).

### 3.2. Negativas

- **Pérdida de soberanía sobre los datos del repo de prueba.** Cada llamada `cognify`/`codify` envía chunks de código y docs a Google. Mitigación: autorización explícita por repo (sec. 2.5), revisión periódica.
- **Dependencia de red.** `wikiforge index` falla offline. Mitigación: tabla de síntomas (sec. 4) define umbral para revertir a stack local.
- **Cuotas y costes potenciales.** Free tier es 15 RPM / 1500 RPD para Flash; si el repo crece o se indexan varios proyectos a la vez, puede saturar. Mitigación: monitorización de cuota en logs JSON; ADR de migración inversa cuando aplique síntoma 11.8.
- **Política de privacidad de Google puede cambiar.** Mitigación: sec. 4 cubre síntoma 11.10 que dispara reversión.
- **Free tier de Google AI Studio entrena con tus inputs** (a fecha del ADR; verificar términos antes de aprobar). Si el usuario tiene un proyecto con billing activado, los inputs no se usan para entrenar. **Pregunta abierta** (sec. 6).

### 3.3. Cambios derivados al AGENTS.md (a aplicar en el mismo commit que aprueba este ADR)

#### 3.3.1. Sec. 3 (stack canónico)

Reemplazar las dos filas de LLM por una sola, y la fila de Embeddings por su variante Gemini:

```diff
-| LLM local | **Ollama 0.19+ con backend MLX** + `qwen3.5:35b-a3b` | mlx-lm directo si Ollama 0.19 no fuera estable | Activo (preview en algunos canales) |
-| LLM cloud | **Claude Sonnet 4.6** vía API | — | Reservado para extracción crítica y wikis públicos |
+| LLM principal | **Gemini API — `gemini-3-flash-preview`** (versión fija, sin aliases `-latest`) | Reversión a Ollama+qwen3.5 cuando aplique síntoma 11.8/11.9/11.10. Claude Sonnet 4.6 sigue disponible para wikis públicos y casos donde Gemini no encaje. | Activo (Fase 0/1) |
+| LLM extracción crítica | **Gemini API — `gemini-3.1-pro-preview`** | — | Activo, uso bajo demanda |
-| Embeddings inicial | **bge-m3** (~570 MB, multilingüe sólido) | qwen3-embedding-8b cuando aplique síntoma 11.3 | Activo |
+| Embeddings | **Gemini `gemini-embedding-001`** (3072 dims, multilingüe) | qwen3-embedding-8b o bge-m3 local cuando aplique síntoma 11.3 inverso (Gemini falle) | Activo |
```

Y en "Descartados con razón documentada", añadir:

```diff
+- **Ollama + qwen3.5:35b-a3b en Día 1** — diferido por ADR 0001. La estabilidad de Ollama 0.19 + MLX en preview y el peso del modelo (~22 GB) justifican operar en cloud Gemini hasta que un síntoma de la sec. 11 fuerce la reversión.
```

#### 3.3.2. Sec. 11 (síntomas de migración)

Añadir tres síntomas nuevos que disparan la **migración inversa Gemini → local**:

```diff
+| 11.8 | Trabajo offline necesario > 2 sesiones por semana | Reversión Gemini → Ollama + qwen3.5:35b-a3b o `mlx-lm` | `brew install ollama && ollama pull qwen3.5:35b-a3b` + ajustar `.env` |
+| 11.9 | Cuota Gemini agotada > 3 veces en una semana de trabajo normal o coste mensual > €X (a definir) | Misma reversión | Idem 11.8 |
+| 11.10 | Cambio en política de privacidad de Google AI Studio que invalide la autorización del ADR 0001 | Reversión inmediata + ADR de cierre | Idem 11.8 |
```

#### 3.3.3. Sec. 13.2 (`.env` de cognee-mcp)

Reemplazar bloque completo por la versión de la sec. 2.3 de este ADR.

## 4. Alternativas consideradas

| Alternativa | Por qué no |
|---|---|
| **A) Mantener Ollama + qwen3.5:35b-a3b** | Stack original. Coste: 22 GB de descarga, riesgo de Ollama 0.19 preview. No estábamos viendo ningún síntoma que lo descartara, pero tampoco había evidencia de que estuviera operativo en este equipo hoy. Queda como punto de reversión, no como elección activa. |
| **B) Claude Sonnet 4.6 vía API** (cloud ya autorizado en AGENTS.md sec. 3) | Ya está en el stack canónico, no requiere ADR para usarlo en una indexación concreta (sec. 9 anti-patrón #7 solo pide autorización explícita por repo). Pero cuesta ~$3/M tokens input, ~$15/M output frente a $0.50/$3 de Gemini 3 Flash. Se mantiene disponible como respaldo y para Fase 2 (wikis públicos). |
| **B-bis) MiniMax M2.1 vía Code Subscription** | Sin coste marginal (suscripción ya pagada). Pero NO es first-class en Cognee (config custom), el plan da M2.1 (no M2.7), tiene quota 5h sliding que puede colapsar una indexación batch, y SWE-bench inferior (~56% M2.7 vs 78% Gemini 3 Flash). El Coding Plan está optimizado para coding-agent loops humano-en-bucle (Cline, Kilo Code), no para servidor cognee-mcp batch. **Descartado para Cognee**; conserva nicho como provider de chat dentro de Claude Code/Cursor. |
| **C) `mlx-lm` directo sin Ollama** | Sec. 12 lo cita como fallback. Sigue requiriendo descargar el modelo y operar procesos locales. Mismo problema que A. |
| **D) Mezcla: LLM Gemini + embeddings bge-m3 vía Ollama** | Conserva Ollama solo para embeddings (~570 MB en lugar de 22 GB). Es la opción más conservadora. **Considerada como punto de discusión** — si el usuario prefiere mantener algo local para los embeddings (más datos pasan por embeddings que por LLM en una indexación), revisar la sec. 2.2 de este ADR. |

## 5. Plan de reversión

Si cualquier síntoma 11.8 / 11.9 / 11.10 se verifica:

1. `brew install ollama` (M5 Pro, ARM64).
2. `ollama pull qwen3.5:35b-a3b` y `ollama pull bge-m3` (o `qwen3-embedding-8b` si el síntoma 11.3 también aplica).
3. Editar `~/.config/wikiforge/secrets.env`: comentar `GEMINI_API_KEY`.
4. Editar `cognee-mcp/.env`: revertir a `LLM_PROVIDER=ollama`, `LLM_MODEL=qwen3.5:35b-a3b`, etc.
5. `wikiforge sync` (cuando exista) o `cognee prune` + reindexar.
6. ADR 0002 cerrando la migración inversa con datos del síntoma observado.

El plan de reversión es **siempre ejecutable**: no hay schema lock-in en Cognee porque el grafo y los vectores se reindexan; lo único que cambia es el provider de embeddings y de LLM.

## 6. Preguntas abiertas — resolución

Estas preguntas se redactaron como bloqueantes en el borrador. Resolución registrada el 2026-05-02:

1. **Autorización de privacidad explícita.** **Resuelta SÍ.** El usuario declara textualmente: *"son archivos públicos"*. Se autoriza envío a Gemini API del contenido de `~/Developer/ai/uml-class_diagram` para Fase 0. La autorización aplica al estado actual del repo; si en el futuro se añade material privado, el usuario debe revisar.
2. **Tipo de proyecto en Google AI Studio.** **Indiferente al usuario.** Se asume **free tier como peor caso** (Google puede usar inputs para entrenar/mejorar). Como Q-A se respondió afirmando que los archivos son públicos, el riesgo de que Google entrene con ellos se acepta explícitamente. Si en algún momento se indexa otro repo no público, ese repo requiere su propia autorización (sec. 2.5) y posiblemente su propio ADR.
3. **Embeddings.** **Gemini puro** (`gemini-embedding-001`). Se descarta el híbrido con bge-m3 local porque mantenerlo solo para embeddings reintroduce Ollama, que es justo lo que este ADR elimina. Si surge síntoma 11.3 inverso (Gemini embedding falla en multilingüe), se evaluará bajar a bge-m3 local.
4. **Aliases móviles.** **Aceptada la prohibición.** Vetados todos los `*-latest`.
5. **Límite de coste.** **Diferido.** Mientras el usuario opere en free tier o tier no-billing, no aplica. Si en el futuro activa billing, el síntoma 11.9 se concreta entonces con un addendum a este ADR. Por ahora 11.9 se redacta como "cuota Gemini agotada > 3 veces en una semana de trabajo normal", sin cifra monetaria.

## 7. Status flow

```
Proposed  ──(2026-05-02 usuario respondió Q-A=sí, Q-B=indiferente)──▶  Accepted  ──(commit con cambios al AGENTS.md)──▶  Active
```

A partir de la aceptación de este ADR, el plan de Fase 0 puede asumir Gemini 3 Flash + gemini-embedding-001 como stack canónico.

## 7.1. Datos del proyecto Google AI Studio (informativo)

El usuario confirma los siguientes datos para el proyecto que aloja la API key:

- **Nombre:** `WikiForge`
- **Project number:** `846938751343`
- **Tipo:** asumido `free tier` mientras el usuario no confirme lo contrario (Q-B respondida como "indiferente"; ver sec. 6).

Estos datos son informativos. La key vive en `~/.config/wikiforge/secrets.env` (chmod 600) y **no aparece en este documento**.

## 8. Trazabilidad de la conversación que llevó a este ADR

- **Mensaje del usuario que pidió cambio de stack:** "El modelo quiero que implementes uno de Gemini que me puedas recomendar."
- **Mensaje del usuario que descartó MiniMax y aceptó la recomendación Gemini 3 Flash:** "¿Qué modelo realmente me recomiendas?" → respuesta: Gemini 3 Flash.
- **Mensaje de aceptación final:** "Si, no hay ningún problema, ya que son archivos públicos. Me da igual el tipo de proyecto. Hazlo, implementalo de una vez."

Este ADR no se da por concluido sin el commit asociado que aplica los cambios derivados al `AGENTS.md`.
