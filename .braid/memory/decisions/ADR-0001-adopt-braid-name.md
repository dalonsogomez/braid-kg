# ADR-0001 - Adopt Braid As The Project Name

## Status
Historical

## Date
2025-08-21

## Context
Braid needs a short, durable name for a repo-scoped memory and retrieval layer
used by coding agents. The name must work as a CLI command, Python package,
MCP server identifier, documentation label, and project-local state namespace.

## Decision
Use **Braid** as the canonical product, package, CLI, MCP, and documentation
name.

- Project name: Braid
- CLI command: `braid`
- Python package: `braid`
- Project-local state directory: `.braid/`
- Global profile directory: `~/.braid/profile/`
- Secrets directory: `~/.config/braid/`
- MCP server name: `braid`
- Tool names: `braid_search`, `braid_memory`, `braid_adrs`, `braid_status`, `braid_kg`

## Rationale
Braid matches the core purpose: weaving repo evidence, human decisions, memory,
knowledge graph data, and retrieval results into a coherent context surface for
agents. It is short, readable in command lines, and broad enough for MCP,
KG/RAG, memory promotion, evals, hooks, and wiki generation.

## Consequences
- Current docs, commands, paths, and examples use `Braid` / `braid`.
- Generated and operational project state is isolated under `.braid/`.
- Tool-discovery files stay at repository root so external agents can find them.
- Legacy compatibility, where present, is explicitly transitional and must warn
  before delegating to `braid`.

## Verification
1. `braid --help` responds.
2. `braid status` resolves project or global context.
3. Repository docs and tracked state use Braid as the only canonical name.
