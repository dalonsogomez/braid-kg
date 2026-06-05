# Fairlead

Repo-scoped context guidance for coding agents.

MCP-first persistent memory + Knowledge Graph + RAG **per project** for AI dev tools
(Claude Code, Codex CLI, Cursor, Cline, Aider, Goose).

Fairlead gives those tools grounded answers about the active repository — the code,
decisions, and documentation it actually sees — instead of hallucinating from training data.

> Fairlead fue desarrollado originalmente bajo el codename interno WikiForge.
> Ver ADR-0001 (`.memory/decisions/ADR-0001-rename-wikiforge-to-fairlead.md`) para la trazabilidad del rename.

## Status

- **Fase 0** (núcleo): ✅ PASS 4.0/5.0 (2026-05-03). Tag `wf-fase-0-completed-2026-05-03`.
- **Fase 1** (gobierno): ✅ PASS (2026-05-03). CLI `fairlead`, perfil global, dogfooding activo.
- **Fase 2** (calidad medida): 🚧 en curso — suite `fairlead eval`, reranker cloud, baseline registrado.

Ver `AGENTS.md` (canonical) y `.memory/MEMORY.md` (índice operacional) para el detalle.

## Quick start

```bash
# Instalar el CLI (modo editable)
uv venv && uv pip install -e .

# En el repo donde quieres memoria
cd ~/Developer/mi-proyecto
fairlead init
fairlead index
fairlead ask "What does this repo do?"
```

## Stack vigente

Ver ADR 0005 + ADR 0006 en `.memory/decisions/`. Resumen: Cognee 1.0 + Ollama Cloud
`kimi-k2.6:cloud` + bge-m3 local + Kuzu + LanceDB.

## Contrato canónico

`AGENTS.md` en la raíz. Modificarlo requiere ADR (anti-patrón #5).
