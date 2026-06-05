# ADR 0015 - Adopt Braid Name and `.braid/` Layout

- **Estado:** Accepted
- **Fecha:** 2026-06-05
- **Decisor:** Daniel Alonso Gomez
- **Tags:** naming, layout, cli, mcp, memory

---

## Contexto

El proyecto mantiene una finalidad estable: memoria persistente por repositorio,
KG/RAG, promocion manual de decisiones, evaluacion de grounding, hooks de sesion y
exposicion MCP-first para herramientas de desarrollo asistido.

El layout anterior repartia estado operacional en la raiz del repositorio activo
(`.kg/`, `.rag/`, `.memory/`, `.kgconfig`). Ese diseno funcionaba, pero ensuciaba
cada repo consumidor y obligaba a comandos, hooks, tests y documentacion a conocer
varias rutas internas.

## Decision

El nombre canonico del proyecto pasa a ser **Braid** y el comando canonico pasa a
ser `braid`.

Todo el estado local del proyecto generado o administrado por Braid vive bajo una
unica raiz `.braid/`:

```text
.braid/
  config.toml
  kg/
  rag/
  memory/
    MEMORY.md
    decisions/
    plans/
    eval/questions.json
    eval/runs/
  wiki/
```

Los archivos de descubrimiento que otras herramientas esperan en ubicaciones
concretas se mantienen en la raiz: `AGENTS.md`, `CLAUDE.md`,
`.cursor/rules/main.mdc` y `.github/copilot-instructions.md`.

## Consecuencias

- El nuevo codigo debe leer `.braid/config.toml` como fuente canonica y conservar
  lectura legacy de `.kgconfig` solo para migraciones.
- Las escrituras nuevas deben ir a `.braid/*`.
- Los comandos legacy deben delegar con warning hacia `braid` durante la ventana de
  transicion.
- Los tests de DuckLake deben usar catalogos temporales y no depender del estado
  local real.
- Los nombres historicos pueden permanecer en ADRs y notas de migracion cuando sean
  necesarios para trazabilidad, pero no deben aparecer como nombre activo del
  producto.
