# Braid — Project Instructions

> **Cómo usar este documento.** Este es el archivo canónico de instrucciones del proyecto Braid. Vive simultáneamente como (i) `AGENTS.md` en la raíz del repositorio, (ii) Project Instructions en Claude.ai, y (iii) referencia técnica de las decisiones tomadas. Todo lo que contradiga este documento es obsoleto. Lo que no esté aquí, no es decisión del proyecto.
>
> Las modificaciones a este archivo se hacen vía pull request con un ADR asociado en `.braid/memory/decisions/`.

---

## 1. Misión y prioridades

Braid es un sistema **MCP-first** que da a las herramientas de desarrollo asistido (Claude Code, Codex CLI, Cursor, Cline, Aider, Goose) **memoria persistente y contexto estructurado por proyecto**, de forma que respondan con grounding real al código, las decisiones y la documentación del repositorio activo en lugar de inventar.

Las prioridades son ordenadas y no se negocian:

- **Prioridad A — Calidad en CLI/IDE.** Que un agente trabajando dentro de un proyecto responda preguntas concretas sobre ese código sin alucinar nombres, sin pedir abrir archivos manualmente, y respetando decisiones técnicas previas. Métrica única: **% de respuestas correctas sin necesidad de reformular ni aportar archivos a mano**.
- **Prioridad B — Generación de wikis publicables.** Wikis personales offline navegables y, opcionalmente, un wiki público de portfolio. Subordinada a A.
- **Prioridad C — Que ambas brillen.** Si dos componentes empatan en A, gana el que también ayude a B.

**No-objetivos explícitos:**

- No es un producto SaaS, no es un servidor multi-tenant, no es una plataforma de equipo.
- No optimiza coste de tokens; optimiza calidad y grounding.
- No reemplaza a Claude Code/Codex CLI/Cursor; los **alimenta** vía MCP.
- No persigue benchmarks de hype (GraphRAG global, ColBERT) si la medida directa de A no lo justifica.

---

## 2. Decisiones arquitectónicas fundamentales

Estas siete decisiones están firmes. El resto se deriva de ellas.

1. **MCP-first como protocolo único de consumo.** Todo lo que un IDE necesita se expone como herramienta MCP. No hay APIs custom por IDE, no hay plugins específicos. Añadir un editor compatible MCP es una entrada en su config; nada más.
2. **Engine preferente, no dogma.** Cognee es el engine elegido por su MCP server oficial maduro y su pipeline ECL declarativo, pero la arquitectura está diseñada para que pueda sustituirse por LlamaIndex PropertyGraphIndex (o una implementación propia) **sin rediseñar nada por encima**. Cognee acelera; no es la base de la arquitectura.
3. **Contexto resuelto por directorio.** El proyecto activo siempre tiene prioridad sobre cualquier contexto global. Resolución estricta: `cwd -> git root -> .braid/config.toml -> legacy .kgconfig -> ~/.braid/profile/` como fallback final. Nunca se mezclan niveles por defecto.
4. **Memoria explícita en tres niveles.** Sesión (volátil), proyecto (persistente vinculada a la raíz Git), global personal (fallback cross-proyectos). Cada nivel tiene un dataset distinto y un store separado.
5. **Promoción exclusivamente manual.** No existe auto-promote en ninguna dirección. La memoria solo asciende de nivel cuando el usuario lo decide con un comando explícito. Esta es **la regla de oro**: cualquier auto-promotion futura contamina los niveles superiores y degrada la calidad.
6. **AGENTS.md como contrato único.** Un solo archivo gobierna las instrucciones para todos los IDEs. `CLAUDE.md`, `.github/copilot-instructions.md` y `.cursor/rules/main.mdc` son symlinks al `AGENTS.md`. Cuando Claude Code soporte AGENTS.md de forma nativa (issue Anthropic #6235), se eliminará el symlink correspondiente.
7. **Migraciones por síntomas observables, nunca por anticipación.** No se introduce ArcadeDB, Qdrant, Graphiti, Langfuse ni Microsoft GraphRAG hasta que una métrica concreta —no una intuición— lo justifique. Cada migración tiene un síntoma de entrada documentado en este archivo.

---

## 3. Stack canónico

| Componente | Elección actual (Fase 0/1) | Migración prevista | Estado |
|---|---|---|---|
| Engine de KG/RAG | **Cognee** (`cognify`, `codify`, `search`, `prune`) | LlamaIndex PropertyGraphIndex si Cognee impone fricción no compensada | Activo |
| Graph backend | **Kuzu** embedded (excepción provisional documentada en ADR 0002 sec. 5; Cognee 1.0 eliminó networkx) | networkx si Cognee lo reintroduce; ArcadeDB Embedded cuando aplique síntoma 11.1 | Activo |
| Vector store | **LanceDB embebida** (Rust + Arrow, ARM64 nativo, default Cognee) | Qdrant local cuando aplique síntoma 11.2 | Activo |
| LLM principal | **Ollama Cloud — `kimi-k2.6:cloud`** (Kimi K2.6 de Moonshot AI servido remotamente vía plan Ollama Cloud del usuario) — ver ADR 0005 | Local `qwen3:30b` si Ollama Cloud falla; Claude Sonnet 4.6 vía API si calidad insuficiente | Activo (Fase 0/1) |
| LLM cloud secundario | **Claude Sonnet 4.6** vía API | — | Reservado para wikis públicos y casos donde Kimi no aplique |
| Embeddings | **Ollama local — `bge-m3`** (~570 MB descarga, multilingüe sólido, 1024 dims) — ver ADR 0005 | `qwen3-embedding-8b` cuando aplique síntoma 11.3 | Activo |
| Reranker | **No instalado en Día 1** | qwen3-reranker-4b o bge-reranker-v2-m3 cuando aplique síntoma 11.4 | Diferido |
| Ingesta de código | **tree-sitter vía `cognee.run_code_graph_pipeline`** (Python sólido) | `kg_extractors` custom para C#/Java/PHP mientras esté abierto issue Cognee #1502 | Activo |
| Ingesta de PDFs/docs | **Docling local** (Apache 2.0, ARM64) | — | Activo (solo si el repo tiene PDFs relevantes) |
| Ingesta web | Diferido a Mes 2-3: **Crawl4AI** | — | Diferido |
| Memoria episódica temporal | Diferido: **Graphiti MCP** sobre FalkorDB | — | Diferido — ver síntoma 11.5 |
| Wiki personal offline | Diferido a Mes 2: **Astro Starlight** + plantillas Jinja2 | — | Diferido (Prioridad B) |
| Wiki público portfolio | Diferido a Mes 2: **DeepWiki-Open** apuntado al repo público | — | Diferido (Prioridad B) |
| Contrato cross-tool | **AGENTS.md** + symlinks a CLAUDE.md / copilot-instructions.md / .cursor/rules/main.mdc | Eliminar symlink CLAUDE.md cuando issue #6235 se cierre | Activo |
| Observabilidad | **Logs JSON estructurados a stdout** | DeepEval ad-hoc (Mes 2), Langfuse self-hosted solo si aplica síntoma 11.6 | Activo |

**Descartados con razón documentada:**

- **Kuzu como elección de largo plazo** — sigue archivado tras adquisición Apple. **Se usa provisionalmente en Fase 0/1 por excepción del ADR 0002 sec. 5** (única opción in-process en Cognee 1.0 compatible con AGENTS.md sec. 9). Migrar antes de que rompa cuando aplique cualquier síntoma de cierre listado en ADR 0002 sec. 5.
- **Neo4j Community como graph backend del Día 1** — overkill, JVM consume RAM que se necesita para los modelos MLX, no aporta nada que ArcadeDB no cubra cuando llegue el momento.
- **PostgreSQL + JSONB + pgvector como capa canónica del Día 1** — propuesta del Flujo 2 original; correcta para empresa, excesiva para un solo desarrollador con foco en CLI.
- **Microsoft GraphRAG** — reservado solo para corpus enormes (>500 páginas) con queries globales y presupuesto cloud. No aplica al caso. LightRAG se descarta también por ausencia de MCP server oficial.
- **Langfuse en Día 1** — overhead injustificado hasta tener métricas concretas de regresión.
- **Ollama + qwen local** — intentado bajo ADR 0002 pero bloqueado por inaccesibilidad de Cloudflare R2 (donde Ollama hosta los blobs) desde esta red. ADR 0003 re-pivota a Gemini cloud temporalmente; el stack local volverá cuando R2 sea accesible o se adopte ruta HF+mlx-lm.
- **MiniMax M2.x para Cognee** — descartado en ADR 0001 sec. 2.2.bis (ADR ahora `Superseded`, pero el descarte sigue vigente por las mismas razones técnicas: no es first-class en Cognee, Code Subscription da acceso a M2.1 no al flagship M2.7, quota rolling 5 h colapsa en indexación batch).

---

## 4. Modelo de memoria de tres niveles

### 4.1. Definición de cada nivel

**Nivel 0 — Temporal de sesión.** Vida: una sesión de Claude Code/Codex/Cursor. Contiene estado activo (archivos abiertos, top-k chunks recuperados, plan en curso, hipótesis de depuración). Vive en el proceso de Cognee con `session_id` auto-generado. **Nunca persiste a disco a menos que el usuario lo promueva con un comando explícito.**

**Nivel 1 — Persistente de proyecto.** Vida: hasta `git rm`. Contiene convenciones del repo, ADRs, glosario de dominio, resúmenes estructurales, decisiones técnicas. Vinculada a la raíz Git del proyecto. Cognee `dataset_id = <project_slug>`. Vive bajo `.braid/`: `.braid/kg/` (grafo + metadata), `.braid/rag/` (vectores), `.braid/memory/*.md` (capa humana editable y auditable) y `.braid/wiki/` (wiki generado).

**Nivel 2 — Persistente personal/global.** Vida: cross-proyectos. Contiene preferencias estables del usuario que aplican a cualquier repositorio: estilo de código, librerías preferidas, idioma de comentarios, patrones que rechaza. Cognee `dataset_id = "_global_profile"`. Vive en `~/.braid/profile/`. **Solo se consulta como fallback** cuando la búsqueda local devuelve score por debajo del umbral.

### 4.2. Reglas de promoción (no negociables)

1. **No existe promoción automática en ninguna dirección.** Bajo ninguna circunstancia.
2. La promoción sesión → proyecto requiere `braid promote-decision "<texto>"`.
3. La promoción proyecto → global requiere `braid promote-to-global "<texto>"`.
4. El descenso de nivel se hace con `braid demote --id <decision_id>`.
5. Una decisión solo se promueve si cumple alguno de estos criterios:
   - Aparece repetidamente en varias sesiones del mismo proyecto.
   - Afecta a varios módulos o archivos.
   - Es una decisión arquitectónica con impacto funcional estable.
   - Fue validada por edición real del repositorio (commit) o evidencia repetida.
6. La promoción a global requiere además que la regla **aplique a múltiples proyectos**, no solo al actual.

### 4.3. Resolución de contexto (orden estricto)

Cada llamada del agente a `mcp__cognee__search` (o equivalente) pasa por este algoritmo:

1. **`cwd`** -> subir hasta la raíz Git o hasta encontrar `.braid/config.toml`.
2. **`.braid/config.toml`** -> si existe, su `dataset_id`, rutas y umbrales ganan sobre lo deducido.
3. **Legacy `.kgconfig`** -> se lee solo para migración de repos antiguos; las escrituras nuevas van a `.braid/`.
4. **`~/.braid/profile/`** -> solo se consulta si los pasos 1-3 devuelven un top-k con score por debajo del umbral configurado (default `0.55`).

Esto se implementa en un wrapper MCP custom de ~150 líneas que intercepta la llamada a Cognee y decide qué `dataset_id` consultar. Es el cerebro del sistema; sin él no hay tres niveles, hay un solo cajón global contaminado.

---

## 5. Esquema de Knowledge Graph: mínimo útil

### 5.1. Regla rectora

**Solo se modela lo que mejora retrieval y grounding en preguntas reales de desarrollo.** Cualquier nodo o relación que no haya demostrado mejorar respuestas concretas se rechaza. Más semántica antes de validar la base equivale a más complejidad sin más valor.

### 5.2. Nodos del grafo inicial

| Tipo | Descripción | Obligatorio |
|---|---|---|
| `File` | Archivo del repositorio. Metadata: `path`, `language`, `lines`, `last_modified` | Sí |
| `Symbol` | Función, clase, método, módulo. Metadata: `kind`, `name`, `file_path`, `start_line`, `end_line`, `signature` | Sí |
| `DocChunk` | Fragmento de documentación (README, docstring, ADR). Metadata: `source`, `heading_path`, `text` | Sí |
| `Concept` | Solo si una entidad de dominio aparece repetida y mejora retrieval | Opcional, validar antes de añadir |

### 5.3. Relaciones del grafo inicial

| Tipo | Origen → Destino | Descripción |
|---|---|---|
| `CONTAINS` | `File` → `Symbol`, `File` → `DocChunk` | Pertenencia estructural |
| `CALLS` | `Symbol` → `Symbol` | Llamada explícita en el código |
| `IMPORTS` | `File` → `File` | Dependencia de imports |
| `DOCUMENTS` | `DocChunk` → `Symbol` o `File` | La documentación describe ese símbolo |
| `MENTIONS` | `DocChunk` → `Concept` | Aparición de un concepto de dominio |

Esto es **suficiente** para responder con calidad: "qué hace esta función", "dónde se usa esto", "qué archivos toca este endpoint", "qué documentación describe este módulo". Cualquier ampliación del esquema se hace solo después de medir que las preguntas reales que falla el sistema requieren más estructura, y se documenta como ADR.

---

## 6. Estructura de directorios

```
~/.braid/                        # NIVEL 2 — global personal
  profile/
    AGENTS.md                        # preferencias estables (fuente humana)
    preferences.json                 # mismas preferencias estructuradas
    cognee_data/                     # dataset_id = "_global_profile"
  cache/
  bin/                               # CLI: braid

mi-proyecto/                         # NIVEL 1 — proyecto
  .git/
  .braid/
    config.toml                      # TOML: dataset_id, embedder, umbrales
    kg/                              # grafo + metadata Cognee/DuckLake
    rag/
      lancedb/                       # vector store embebido
    memory/                          # capa humana editable
      MEMORY.md                      # índice operacional
      decisions/                     # ADRs en Markdown numerados
      plans/
      eval/questions.json
      eval/runs/
    wiki/                            # wiki generado
  AGENTS.md                          # contrato único cross-tool
  CLAUDE.md -> AGENTS.md             # symlink (eliminar tras Anthropic #6235)
  .github/copilot-instructions.md -> ../AGENTS.md
  .cursor/rules/main.mdc -> ../../AGENTS.md
  src/
  README.md
```

---

## 7. CLI `braid` — comandos canónicos

El CLI es deliberadamente pequeño. Hace pocas cosas y las hace bien. Cualquier comando adicional requiere un ADR.

| Comando | Acción |
|---|---|
| `braid init` | Crea `.braid/config.toml`, `.braid/kg/`, `.braid/rag/`, `.braid/memory/`, `.braid/wiki/`, `AGENTS.md` y los symlinks raíz. Idempotente. |
| `braid index` | Ejecuta la ingesta de código (tree-sitter vía Cognee `codify`) y de docs (`cognify`). Construye vectores y actualiza el grafo. Incremental por defecto. |
| `braid ask "<query>"` | Resuelve proyecto por `cwd` y consulta el índice + grafo. Devuelve `project context bundle` (chunks + nodos + caminos + señales). Útil sobre todo para depurar el sistema; los IDEs lo consumen vía MCP, no este CLI. |
| `braid promote-decision "<texto>"` | Promueve sesión → proyecto. Genera ADR en `.braid/memory/decisions/NNNN-<slug>.md`. |
| `braid promote-to-global "<texto>"` | Promueve proyecto → global. Solo si el texto aplica cross-proyectos. |
| `braid demote --id <decision_id>` | Revierte una promoción indebida. |
| `braid sync` | Reescanea `.braid/kg/` y reconcilia con el sistema de archivos (útil tras git pull). Incremental real por `mtime` desde ADR 0009: at-rest exit 0 sin invocar el LLM. |
| `braid eval` | (ADR 0010) Ejecuta `.braid/memory/eval/questions.json` (10-20 preguntas con ground truth). Scoring por substring + recall@1 + recall@K. Run JSON guardado en `.braid/memory/eval/runs/<ISO>.json`. Flags: `--questions`, `--top-k`, `--no-save`, `--per-question-timeout`. Herramienta canónica para validar regresiones y para activar/desactivar síntomas sec. 11.4 / 11.10. |
| `braid wiki build` | (Mes 2+) Genera Markdown desde Cognee y compila Astro Starlight. |
| `braid claude-session-start` | (ADR 0009) Subcomando de hook. Lee filesystem, reporta estado de memoria del repo activo en una línea (al día / stale / no inicializado / no-repo) en p50 ≈ 250 ms. **No llama al LLM ni crea `.braid/kg/`.** Soporta `--json`. Su stdout entra en el contexto de Claude Code (sec. 4 schema oficial Anthropic). |
| `braid claude-init` | (ADR 0009) Cablea hook `SessionStart` (matchers `startup\|resume\|clear\|compact`, `timeout: 5s`, `statusMessage`) en `<git_root>/.claude/settings.json`. Idempotente; preserva otras claves (`permissions`, `env`, otros hooks). `--remove` lo desinstala. |

---

## 8. Instrucciones para agentes IA que operen en este proyecto

Las siguientes reglas se aplican a cualquier agente (Claude Code, Codex CLI, Cursor, Cline, Aider, Goose) trabajando dentro de un repositorio gobernado por este `AGENTS.md`.

### 8.1. Antes de responder

1. **Lee el banner `[Braid] …` del primer mensaje del sistema** si aparece (lo emite el hook `SessionStart` configurado por `braid claude-init` — ADR 0009). Te dice si la memoria del repo está al día, stale, no indexada o no inicializada. Si dice "no inicializado" / "no indexado", **no consultes cognee**: pídele al usuario `braid init && braid index` antes de responder. Si dice "stale", avisa que las respuestas pueden estar desactualizadas y sugiere `braid sync`.
2. **Resuelve el contexto vía MCP `cognee`** (o el wrapper de Braid si está disponible) **antes** de responder a cualquier pregunta sobre código o decisiones del proyecto. No respondas de memoria sobre símbolos del repo: consulta primero.
3. **Si el grafo no devuelve resultados con score suficiente**, dilo explícitamente. No inventes el comportamiento de funciones que no estén en el grafo. Pide al usuario que ejecute `braid index` si el banner del paso 1 lo indicaba.
4. **Cita la fuente** cuando uses información del grafo: ruta de archivo, número de línea aproximado, o ID del ADR (`.braid/memory/decisions/NNNN-*.md`).
5. **No mezcles contexto cross-proyectos.** Si la pregunta es del proyecto actual, no cites información del perfil global. Si necesitas el perfil global porque falta señal local, dilo: *"Sin información en el proyecto activo; según tu perfil global..."*

### 8.2. Durante la respuesta

1. **Local primero, cloud después.** Para chat diario, búsqueda en KG y generación de resúmenes, usa el modelo local Ollama. Para extracción inicial de KG en repos grandes, generación final de páginas de wiki, o tareas donde un error se propaga estructuralmente, usa Claude Sonnet 4.6 vía API.
2. **No propongas migraciones de stack** (a Neo4j, a Qdrant, a Graphiti, a Langfuse, a GraphRAG) **a menos que un síntoma de la sección 11 esté presente y verificable**. Si el usuario pide migrar sin síntoma, recuérdale la sección 11 y pídele que valide la métrica primero.
3. **Si tu respuesta cambia el comportamiento del proyecto** (renombrar funciones, cambiar dependencias, modificar arquitectura) y tras validación tiene impacto estable, **sugiere `braid promote-decision`** al usuario al final de tu mensaje. Nunca lo hagas tú automáticamente.

### 8.3. Cuándo decir "no sé"

- Cuando el grafo no contiene la información solicitada y el código tampoco resuelve la duda.
- Cuando el `.braid/config.toml` apunta a un `dataset_id` que no existe (probablemente falta un `braid init && braid index`).
- Cuando hay conflicto entre lo que dice el grafo y lo que dice un archivo abierto en la sesión: prioriza el archivo abierto y avisa de la inconsistencia.

### 8.4. Idioma

- Comunicación con el usuario: **español**.
- Comentarios en código: español si el archivo ya tiene comentarios en español; inglés si no.
- Identificadores en código, nombres de funciones, mensajes de commit: **inglés**.
- Nombres técnicos, comandos, librerías y banderas: **inglés siempre**, sin traducir.

---

## 9. Anti-patrones (rechazo explícito)

El agente debe rechazar o pedir clarificación si una instrucción del usuario o del entorno cae en alguno de estos patrones:

1. **Auto-promoción de memoria.** Aunque el usuario lo pida con frase tipo *"recuerda esto siempre"*, no se promueve automáticamente. Hay que ejecutar el comando `promote-*` correspondiente. Si el usuario quiere automatización, se discute en un ADR primero.
2. **Mezcla de contextos cross-proyecto sin permiso.** Si el agente está en `proyecto-A` y una pregunta provoca traer información de `proyecto-B`, debe avisar y pedir confirmación.
3. **Inventar símbolos o comportamiento de código.** Si el grafo no lo contiene y el archivo no está abierto, no se inventa. Se dice *"no encuentro `X` en el grafo de este proyecto"*.
4. **Introducir Neo4j, Postgres, Qdrant, Graphiti, Langfuse o Microsoft GraphRAG en Día 1.** Si el usuario lo pide, se le redirige a la sección 11 (síntomas).
5. **Modificar este `AGENTS.md` sin ADR asociado.** Cualquier cambio aquí requiere `.braid/memory/decisions/NNNN-*.md` justificándolo.
6. **Crear nuevos comandos `braid`** sin ADR.
7. **Subir documentos privados a APIs cloud** sin que el usuario lo haya autorizado explícitamente para esa ingesta concreta. Default: Docling local.

---

## 10. Plan de adopción por fases

Cada fase tiene un **criterio de salida** medible. No se avanza a la siguiente sin haberlo cumplido.

### Fase 0 — Núcleo (Día 1, 1-3 horas)

**Entregable:** Claude Code, Codex CLI o Cursor responde correctamente preguntas sobre el repo activo, vía MCP, sin alucinar nombres y sin que el usuario tenga que abrir archivos a mano la mayor parte del tiempo.

**Componentes activos:** Cognee + cognee-mcp + Ollama 0.19 + qwen3.5:35b-a3b + bge-m3 + LanceDB embebida + AGENTS.md + symlinks.

**Criterio de salida:** ≥ 4 de 5 preguntas concretas sobre símbolos del repo respondidas correctamente sin abrir archivos.

### Fase 1 — Gobierno (Semana 1)

**Entregable:** estructura `.braid/` operativa en al menos dos repos, CLI `braid` funcional con los siete comandos canónicos, perfil global creado en `~/.braid/profile/`.

**Criterio de salida:** una decisión técnica ha sido promovida sesión → proyecto vía `braid promote-decision`, y posteriormente recordada en una sesión nueva del mismo repo.

### Fase 2 — Calidad medida (Mes 2)

**Entregable:** suite `braid eval` con 10-20 preguntas por repo activo, embedder upgrade a `qwen3-embedding-8b`, ingesta de documentos con Docling si el repo lo justifica, y opcionalmente activación de **Prioridad B** (Astro Starlight + DeepWiki-Open).

**Criterio de salida:** baseline de calidad medido y registrado; primer wiki personal navegable o público desplegado.

### Fase 3 — Escalado por síntoma (Mes 3+)

Solo se ejecutan migraciones de la sección 11 cuyo síntoma esté **verificado y registrado** en `.braid/memory/decisions/`. Cada migración cierra con un ADR de antes/después.

---

## 11. Síntomas de migración (criterios objetivos)

Las migraciones aquí listadas **solo se ejecutan si el síntoma se ha medido**, no por anticipación.

| ID | Síntoma observable | Migración asociada | Comando indicativo |
|---|---|---|---|
| 11.1 | Grafo > 100 000 nodos o `braid ask` tarda > 2 s en p50 | networkx → ArcadeDB Embedded | `pip install arcadedb-embedded` + cambiar `GRAPH_DATABASE_PROVIDER` en `.env` |
| 11.2 | Recall@10 < 0.7 medido en `braid eval` con corpus heterogéneo grande | LanceDB → Qdrant local | `docker run -p 6333:6333 qdrant/qdrant` + `VECTOR_DB_PROVIDER=qdrant` |
| 11.3 | bge-m3 falla repetidamente en preguntas multilingües código-español | bge-m3 → qwen3-embedding-8b | `huggingface-cli download mlx-community/Qwen3-Embedding-8B-MLX-4bit` |
| 11.4 | Top-k contiene > 30 % de chunks irrelevantes en `braid eval` | Añadir reranker | qwen3-reranker-4b o bge-reranker-v2-m3 vía sentence-transformers |
| 11.5 | Aparecen contradicciones entre decisiones recientes y antiguas en el grafo | Añadir Graphiti MCP para memoria episódica bi-temporal | `git clone graphiti && docker-compose up -d` + `claude mcp add --transport sse graphiti http://localhost:8765/sse` |
| 11.6 | > 5 flujos productivos coexistiendo y necesidad de comparar prompts/modelos entre versiones | Añadir Langfuse self-hosted | `docker run langfuse/langfuse` |
| 11.7 | Corpus único > 500 páginas + necesidad real de queries globales sobre todo el corpus | Considerar Microsoft GraphRAG (no obligatorio) | Aislado en pipeline secundario; no toca el core |
| 11.8 | Ollama Cloud caído > 1 vez por semana o latencia > 5s p50 | Reversión a `qwen3:30b` local — ADR 0005 sec. 4 | `ollama pull qwen3:30b` + cambiar `LLM_MODEL` en `.env` |
| 11.9 | Coste mensual del plan Ollama Cloud sobre umbral acordado | Reversión a stack 100% local o cambio de plan | Idem 11.8 + revisar plan |
| 11.10 | Calidad de extracción del LLM insuficiente medida en `braid eval` (Fase 2) — < 60% en preguntas de grounding | Considerar Claude Sonnet 4.6 (ya en stack); requiere ADR autorizando ingesta cloud por repo | `cognee` con `LLM_PROVIDER=anthropic` + autorización privacidad por repo |
| 11.11 | `GGML_ASSERT([rsets->data count] == 0) failed` o "model runner has unexpectedly stopped" al cargar modelo Ollama local | Verificar que solo hay UN `ollama serve` en port 11434 — ADR 0006 sec. 2.4 | `lsof -nP -iTCP:11434 -sTCP:LISTEN`. Si hay dos (homebrew + Ollama.app): apagar Ollama.app O `brew services stop ollama`, dejar solo uno. |

---

## 12. Áreas de incertidumbre vivas

Estas son hipótesis externas que pueden invalidar partes del documento. Se vigilan.

- **AGENTS.md nativo en Claude Code (issue Anthropic #6235).** Si se cierra, el symlink `CLAUDE.md → AGENTS.md` se elimina y se actualiza este archivo con un ADR.
- **Estado de Ollama y MLX.** El AGENTS.md original asumía Ollama 0.19 + MLX preview con `qwen3.5:35b-a3b`. ADR 0002 documenta el pivote a `qwen3:30b` (mejor aproximación disponible en Ollama hoy). Si la familia Qwen 3.5 llega a Ollama o si `qwen3:30b` rinde por debajo del umbral en `braid eval`, ADR de actualización.
- **Cognee 1.0 sin networkx (descubrimiento del 2026-05-02).** El stack canónico original asumía networkx; ADR 0002 documenta el pivote a Kuzu como excepción. Si Cognee reintroduce networkx, ADR 0002 sec. 5.1 dispara reversión.
- **Gemini API explorada como alternativa cloud (ADR 0001 — Superseded).** Las API keys siguen disponibles en `~/.config/braid/secrets.env`; los modelos `gemini-3-flash-preview`, `gemini-3.1-pro-preview` y `gemini-embedding-001` quedaron verificados como disponibles en el proyecto Google AI Studio "Braid" (#846938751343). Si la calidad local resulta insuficiente, Gemini sigue siendo opción cloud disponible bajo nuevo ADR.
- **Kuzu archivado.** Si Cognee aún lo lista como graph provider en el código, **no lo selecciones**. Verifica en `cognee/cognee/infrastructure/databases/graph/` antes de cualquier configuración.
- **Cognee `codify` para C#/Java/PHP** (issue #1502). Si tus repositorios son mayoritariamente C#/.NET, el grafo de código será más pobre que en Python hasta que el issue se cierre. Mitigación: `kg_extractors` custom basados en tree-sitter directo.
- **DeepWiki-Open futuro.** El equipo está moviendo desarrollo a "AsyncReview". Si el proyecto se discontinúa, replantear capa B con generación propia desde Cognee + Astro Starlight.
- **Costes cloud Claude Sonnet 4.6.** Vigilar gasto si se delega extracción inicial de repos grandes. Default: extracción local con Ollama; cloud solo cuando la calidad del grafo local sea insuficiente medida en `braid eval`.
- **Benchmarks de vendors (FalkorDB, ArcadeDB).** Publicados por los propios fabricantes. Cualquier decisión derivada de números crudos requiere validación cruzada con `braid eval` propio antes de actuar.

---

## 13. Apéndice — configuración mínima

### 13.1. `.braid/config.toml` (TOML, raíz del proyecto)

```toml
dataset_id = "mi-proyecto"
graph_backend = "networkx"
vector_backend = "lancedb"
embedder = "bge-m3"
llm = "qwen3.5:35b-a3b"
fallback_threshold = 0.55       # umbral para consultar perfil global
priority = ["active_file", "project_graph", "project_vector", "global_profile"]

[memory]
temporal_store = ".braid/memory/sessions"
persistent_store = ".braid/memory/persistent"
promotion_policy = "explicit_only"
```

### 13.2. `.env` para `cognee-mcp` (raíz de la instalación de cognee-mcp)

> Versión actualizada por **ADR 0006** con dodges para tres bugs upstream descubiertos durante el bootstrap de Fase 0 (LiteLLM `:` parsing, OllamaEmbeddingEngine `/api/embed` 422, pydantic tokenizer gate). Esta es la versión que **realmente funciona**, no la teórica.

```env
# Stack ADR 0005 con dodges ADR 0006 (Ollama Cloud + bge-m3 local + kuzu)

# --- LLM ---
# Dodge LiteLLM ':' parser: provider=openai con model=openai/<name> apuntando al endpoint
# OpenAI-compat de Ollama (puerto 11434/v1). Bypassea el codepath nativo LiteLLM-ollama
# que parte el name en el primer ':' y rompe modelos `:cloud`.
LLM_PROVIDER=openai
LLM_MODEL=openai/kimi-k2.6:cloud
LLM_ENDPOINT=http://localhost:11434/v1
LLM_API_KEY=ollama

# Rate limit estricto: cognee dispara extracciones LLM paralelas durante cognify y
# Ollama Cloud devuelve 429 "too many concurrent requests" sin esto.
LLM_RATE_LIMIT_ENABLED=true
LLM_RATE_LIMIT_REQUESTS=2
LLM_RATE_LIMIT_INTERVAL=5

# --- Embeddings ---
# Dodge OllamaEmbeddingEngine /api/embed 422: usar el path OpenAI-compat /v1/embeddings
# (acepta `dimensions` aunque lo ignore). Mantener provider=ollama para que el engine
# use HUGGINGFACE_TOKENIZER en lugar de TikToken (que no conoce bge-m3 → KeyError).
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=bge-m3
EMBEDDING_ENDPOINT=http://localhost:11434/v1/embeddings
EMBEDDING_API_KEY=ollama
EMBEDDING_DIMENSIONS=1024

# Pydantic gate: requerido cuando se setean los EMBEDDING_* manualmente.
HUGGINGFACE_TOKENIZER=BAAI/bge-m3

# --- Backend graph + vector ---
GRAPH_DATABASE_PROVIDER=kuzu
VECTOR_DB_PROVIDER=lancedb

# --- Ergonomía Cognee 1.0 ---
ENABLE_BACKEND_ACCESS_CONTROL=false
COGNEE_SKIP_CONNECTION_TEST=true

# Autenticación con Ollama Cloud para modelos `:cloud` se hace una vez vía `ollama login`.
```

**Gestión de secretos (heredada del ADR 0001 sec. 2.4, sigue vigente):**

- API keys de cualquier provider cloud (Gemini, MiniMax, Anthropic, etc.) viven **fuera del repo** en `~/.config/braid/secrets.env` con permisos `600`.
- Prohibido escribir cualquier API key real en `.env` del repo, en ADRs, en planes, en commits, o en cualquier archivo bajo control de versiones.

### 13.3. Plantilla `AGENTS.md` por proyecto (la específica de cada repo, no esta canónica)

```markdown
# Proyecto: <nombre>

<una o dos líneas describiendo el proyecto>

## Stack
- <lenguaje> <versión>, <framework principal>
- Tests: <herramienta>

## Comandos
- `make dev` — arrancar entorno de desarrollo
- `make test` — correr tests

## Convenciones críticas
- <reglas duras del repo>

## Memoria del proyecto
- Contexto extendido en `.braid/memory/MEMORY.md` y `.braid/memory/decisions/`.
- Knowledge graph disponible vía MCP server `braid` con `dataset_id=<slug>`.
- Para promover una decisión: `braid promote-decision "..."`.
- El sistema sigue las reglas del `AGENTS.md` canónico de Braid.
```

### 13.4. Plantilla `~/.braid/profile/AGENTS.md`

```markdown
# Perfil global

## Stack habitual
- <tus lenguajes y frameworks>

## IDEs
- Claude Code, Codex CLI, Cursor

## Hardware
- MacBook Pro M5 Pro 64 GB, macOS Tahoe 26.4

## Preferencias estables
- Idioma de comentarios: español; identificadores: inglés.
- <otras preferencias cross-proyectos>
```

---

## 14. Una sola línea

**Proyecto activo primero, knowledge graph mínimo pero correcto, vector store embebido, memoria manual en tres niveles, MCP como capa universal, y escalado únicamente cuando un síntoma de la sección 11 esté verificado.**

Cualquier desviación de esta línea requiere ADR.
