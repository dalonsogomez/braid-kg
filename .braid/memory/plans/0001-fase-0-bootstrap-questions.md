# Fase 0 — 5 preguntas de validación

> Plan 0001, criterio de salida AGENTS.md sec. 10: ≥ 4 / 5 correctas sin abrir archivos.

Cada pregunta cubre uno de los tipos de la sec. 5.3 del AGENTS.md (CALLS, IMPORTS, CONTAINS, DOCUMENTS, MENTIONS).

**Stack ejecutivo:** Cognee 1.0 + Gemini 3 Flash + gemini-embedding-001 + Kuzu (ADR 0003).

## Q1 — Comportamiento de un símbolo (CONTAINS + descripción)

**Pregunta:** "¿Qué hace la función `generate_from_statement` en el repo `vp-class-diagram-agent`? ¿Qué argumentos toma y qué retorna?"

**Ground truth:** vive en `src/vp_class_diagram_agent/generator.py`. Firma:
`def generate_from_statement(statement_path: str | Path, style: dict[str, Any] | None = None) -> dict[str, Any]:`
Genera un draft `ClassDiagramSpec.json` a partir de un PDF de enunciado, opcionalmente sesgado por un perfil de estilo del profesor.

**Aceptable si la respuesta:** menciona el archivo correcto (o el paquete `vp_class_diagram_agent`), identifica los dos parámetros (`statement_path` y `style`), y describe el propósito (generar spec/draft a partir de un statement/enunciado).

## Q2 — Llamadas (relación CALLS)

**Pregunta:** "¿Qué función o método llama a `audit_exam_associations`?"

**Ground truth:** `_generate_bdbol_specs` y/o `generate_iweb_class_diagrams` en `src/vp_class_diagram_agent/iweb_generator.py`.

**Aceptable si la respuesta:** nombra al menos un archivo y un símbolo concreto que lo llame, y NO inventa un callsite que no exista.

## Q3 — Estructura del repo (CONTAINS / IMPORTS)

**Pregunta:** "¿Qué archivos componen el plugin de Visual Paradigm en este repo?"

**Ground truth:** `plugin/plugin.xml` + `plugin/src/**/*.java` (16 archivos Java).

**Aceptable si la respuesta:** identifica el directorio `plugin/` como raíz, menciona `plugin.xml` y reconoce que el código es Java bajo `plugin/src/`.

## Q4 — Documentación (DOCUMENTS)

**Pregunta:** "¿En qué sección del README se describe el flujo `Direct .vpp Solution Output` para WEB MYSPORT?"

**Ground truth:** sección `## Direct \`.vpp\` Solution Output` del README. Describe el pipeline `generate_iweb_exam_solution_vpp` → review bundles → copia plantilla `resources/vp-uml/templates/empty_project.vpp` → plugin VP aplica spec.

**Aceptable si la respuesta:** cita el heading correcto del README y resume los pasos clave.

## Q5 — Privacidad / convención del repo (MENTIONS / DOC chunks)

**Pregunta:** "¿Cuál es el flujo por defecto de privacidad de este repo: local o cloud?"

**Ground truth:** sección `## Privacy Notes` del README. Flujo default privado/local (PDFs ingeridos localmente, plugin Java aplica spec en `.vpp`, sin envío a APIs cloud salvo autorización explícita).

**Aceptable si la respuesta:** dice "local/privado por defecto" y cita la sección Privacy Notes o equivalente.

---

## Reglas de scoring

- **Correcta (1 pt):** la respuesta cubre el ground truth sin inventar nombres, archivos o comportamientos. Citas a `file:line` aproximadas (±5 líneas) cuentan como correctas.
- **Parcial (0.5 pt):** menciona el archivo correcto pero el comportamiento es vago, o el comportamiento correcto pero atribuido al archivo equivocado.
- **Incorrecta (0 pt):** alucina un símbolo, archivo o comportamiento que no existe en el repo.
- **Criterio de salida:** suma ≥ 4.0 / 5.0.

## Procedimiento programático (sin sesión interactiva)

Como el usuario está fuera, las preguntas se ejecutan vía `validate_phase0.py` que invoca `cognee.search(...)` con los 5 search types disponibles (GRAPH_COMPLETION, RAG_COMPLETION, INSIGHTS, CHUNKS, SUMMARIES) por cada pregunta. La respuesta cruda se guarda en `0001-fase-0-bootstrap-raw-answers.json`. El scoring se hace inspeccionando ese JSON y produciendo `0001-fase-0-bootstrap-results.md`.
