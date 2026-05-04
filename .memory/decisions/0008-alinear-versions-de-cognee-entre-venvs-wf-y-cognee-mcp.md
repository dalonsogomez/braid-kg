# ADR 0008 — Alinear versions de cognee entre venvs (WF y cognee-mcp)

- **Estado:** Accepted
- **Fecha:** 2026-05-04
- **Decisor:** Daniel Alonso Gómez
- **Tags:** infra,cognee,fase-2-todo,version-skew
- **Origen:** promoción manual sesión → proyecto vía `wikiforge promote-decision`

---

## Decisión

Los venvs de WikiForge (cognee 1.0.5 + ladybug 0.16) y cognee-mcp (cognee 1.0.0 + kuzu legacy) escriben formatos de Kuzu file con version_codes incompatibles. Tras centralizar el storage (ADR 0007), si el MCP lee chunks escritos por el CLI, falla con "Could not map version_code". TODO Fase 2: alinear versions actualizando cognee-mcp venv a cognee 1.0.5 (o lo que sea last stable que tenga ladybug_version_mapping actualizado upstream). Verificar que cognee-mcp/server.py sigue siendo compatible con la API de la versión target.

## Notas

(añade contexto, motivación, consecuencias y supersedence chain según evolucione)
