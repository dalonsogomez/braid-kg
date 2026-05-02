# Snapshot — 2026-05-02 17:46 (timestamp del usuario)

> **Timestamp real del sistema al crear el snapshot:** 2026-05-02 19:59:35 (la diferencia es zona horaria; el usuario dijo "17:46 de ahora" en su zona local; lo etiquetamos como pidió).

## Razón del snapshot

El usuario pidió "máquina del tiempo" antes de un pivote arquitectónico mayor:

- Cognee 1.0.0 eliminó `networkx` como graph backend.
- ADR 0001 (Gemini 3 Flash) iba a quedar como `Superseded` por un nuevo ADR 0002 que pivota a stack local (Ollama + qwen + bge-m3) con kuzu como graph backend (excepción documentada al sec. 12 del AGENTS.md).
- Antes de tocar nada más, dejamos este punto recuperable.

## Cómo restaurar este punto

```bash
# Volver al commit etiquetado
cd ~/Developer/claude/code-projects/WikiForge
git reset --hard wf-checkpoint-2026-05-02-1746

# Restaurar archivos externos
cp .memory/snapshots/2026-05-02-1746-pre-pivot/cognee-mcp.env ~/.wikiforge/cognee-mcp/cognee-mcp/.env
cp .memory/snapshots/2026-05-02-1746-pre-pivot/cognee-mcp-stdio.sh ~/.wikiforge/bin/cognee-mcp-stdio.sh
chmod +x ~/.wikiforge/bin/cognee-mcp-stdio.sh

# Si necesitas la API key de Gemini, recupérala del sistema (o vuelve a generarla en aistudio.google.com)
# El archivo ~/.config/wikiforge/secrets.env NO está respaldado aquí por seguridad.
```

## Estado del repo en este snapshot

- Branch: `master`
- Último commit: `c02e860` (`docs: add Phase 0 bootstrap implementation plan`)
- ADR 0001 status: `Accepted` (con stack Gemini)
- AGENTS.md sec. 3: contiene LLM principal Gemini, embeddings Gemini
- `.memory/plans/0001-fase-0-bootstrap.md`: plan completo escrito, NO ejecutado más allá de Task 3 (instalación cognee-mcp + .env + shim)

## Estado de instalaciones externas en este snapshot

- `~/.wikiforge/cognee-mcp/` — clone de `topoteretes/cognee` con `uv sync` completado (cognee 1.0.0 instalado).
- `~/.wikiforge/bin/cognee-mcp-stdio.sh` — shim funcional (lee de secrets.env y ejecuta server stdio).
- `~/.wikiforge/cognee-mcp/cognee-mcp/.env` — config Gemini.
- `~/.config/wikiforge/secrets.env` — chmod 600, contiene GEMINI_API_KEY y MINIMAX_API_KEY (no respaldado aquí).
- Ollama: NO instalado.
- Modelos locales: NO descargados.
- MCP server `cognee` en Claude Code: NO registrado.

## Blocker conocido en este punto

`cognee 1.0.0` no soporta `networkx` como graph backend. Providers disponibles: `neo4j, kuzu, kuzu-remote, postgres, neptune, neptune_analytics`. El smoke test E2E con Gemini falló con `OSError: Unsupported graph database provider: networkx`.

## Plan después de este snapshot (ADR 0002)

Pivote a stack local: Ollama + qwen (modelo del registry actual) + bge-m3 + cognee 1.0.0 + kuzu (excepción provisional). ADR 0001 → Superseded.
