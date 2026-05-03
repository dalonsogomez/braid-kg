# WikiForge

MCP-first persistent memory + Knowledge Graph + RAG **per project** for AI dev tools (Claude Code, Codex CLI, Cursor, Cline, Aider, Goose).

WikiForge gives those tools grounded answers about the active repository — the code, decisions, and documentation it actually sees — instead of hallucinating from training data.

## Status

- **Fase 0** (núcleo): ✅ PASS 4.0/5.0 (2026-05-03). Tag `wf-fase-0-completed-2026-05-03`.
- **Fase 1** (gobierno): 🚧 en curso — CLI `wikiforge`, perfil global, dogfooding sobre este propio repo.

Ver `AGENTS.md` (canonical) y `.memory/MEMORY.md` (índice operacional) para el detalle.

## Quick start

```bash
# Instalar el CLI (modo editable)
uv venv && uv pip install -e .

# En el repo donde quieres memoria
cd ~/Developer/mi-proyecto
~/Developer/claude/code-projects/WikiForge/.venv/bin/wikiforge init
~/Developer/claude/code-projects/WikiForge/.venv/bin/wikiforge index
~/Developer/claude/code-projects/WikiForge/.venv/bin/wikiforge ask "What does this repo do?"
```

## Stack vigente

Ver ADR 0005 + ADR 0006 en `.memory/decisions/`. Resumen: Cognee 1.0 + Ollama Cloud `kimi-k2.6:cloud` + bge-m3 local + Kuzu + LanceDB.

## Contrato canónico

`AGENTS.md` en la raíz. Modificarlo requiere ADR (anti-patrón #5).
