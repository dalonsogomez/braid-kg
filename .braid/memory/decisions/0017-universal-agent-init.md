# ADR 0017 - Universal Agent Init

- **Estado:** Accepted
- **Fecha:** 2026-06-05
- **Decisor:** Daniel Alonso Gomez
- **Tags:** cli, agents, mcp, hooks, migration

---

## Contexto

Braid ya expone herramientas MCP genericas y mantiene archivos de descubrimiento
para varios agentes, pero la activacion operativa estaba centrada en Claude Code
mediante `braid claude-init`. En instalaciones reales pueden quedar hooks legacy
con `fairlead` o `wikiforge`, y Codex/Cursor/Copilot no tienen un comando unico
para verificar o reparar su integracion.

## Decision

Anadir `braid agent-init` como comando canonico para aplicar, verificar, reparar o
retirar la integracion Braid por agente.

El comando soporta:

- `--agent claude|codex|cursor|copilot|all`
- `--check`
- `--fix`
- `--remove`
- `--json`

`braid agent-init` aplica la configuracion Braid para todos los agentes soportados
sin ejecutar indexacion, sin llamar al LLM y sin promover memoria. `--check` es
read-only y reporta drift. `--fix` normaliza configuraciones legacy. `--remove`
borra solo bloques gestionados por Braid y preserva configuracion ajena.

`braid claude-init` queda como alias compatible que delega en `agent-init --agent
claude`.

## Consecuencias

- Claude y Codex pueden recibir hooks `SessionStart` que invocan
  `braid claude-session-start`.
- Claude registra el MCP server `braid` con `braid mcp-serve`.
- Cursor y Copilot se validan mediante symlinks a `AGENTS.md`.
- Los hooks legacy `fairlead`/`wikiforge` se consideran drift y se migran a
  `braid` cuando se usa `--fix` o el modo apply por defecto.
- La superficie nueva no cambia KG/RAG ni los tres niveles de memoria.
