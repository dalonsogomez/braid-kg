# Braid

Repo-scoped context, memory, Knowledge Graph, and RAG for coding agents.

Braid is an MCP-first system for AI development tools such as Claude Code,
Codex CLI, Cursor, Cline, Aider, and Goose. Its goal is to answer questions
about the active repository from the code, ADRs, and documentation that are
actually present in that repository.

The canonical project, package, and CLI name is `braid`. Older command names
are transitional compatibility aliases only: they warn and delegate to
`braid`.

## Project Layout

Project-local operational state lives under `.braid/`:

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

Tool-discovery files stay at repository root because external agents expect
them there: `AGENTS.md`, `CLAUDE.md`, `.cursor/rules/main.mdc`, and
`.github/copilot-instructions.md`.

## Quick Start

```bash
uv venv
uv pip install -e .

cd ~/Developer/my-project
braid init
braid index
braid ask "What does this repo do?"
```

## Status

- Phase 0: PASS, repository-grounded recall baseline.
- Phase 1: PASS, CLI/governance/manual promotion flow.
- Phase 2: in progress, `braid eval`, DuckLake catalog, reranking, and quality measurement.

See `AGENTS.md` for the canonical architecture and `.braid/memory/MEMORY.md`
for the operational memory index.
