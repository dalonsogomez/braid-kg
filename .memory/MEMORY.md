# MEMORY.md — Índice de gobernanza de WikiForge

> Índice operacional del proyecto. Apunta a documentos de gobernanza (decisiones, planes, glosario, riesgos). Cada entrada es una línea ≤ 150 caracteres.

## Decisiones (ADRs)

- [ADR 0001 — LLM Gemini en Fase 0](decisions/0001-llm-gemini-en-fase-0.md) — Status: **Superseded** by ADR 0002 (2026-05-02). Cognee 1.0 sin networkx forzó pivote.
- [ADR 0002 — Pivote a stack local + Kuzu](decisions/0002-pivote-stack-local-cognee-1-sin-networkx.md) — Stack actual: Ollama + qwen3:30b + bge-m3 + Kuzu (excepción a sec. 12). Status: Accepted (2026-05-02, delegación explícita del usuario).

## Planes activos

- [Plan 0001 — Bootstrap Fase 0](plans/0001-fase-0-bootstrap.md) — *(pendiente de redactar tras aceptación ADR 0001)*

## Convenciones

- AGENTS.md de la raíz es el contrato canónico. CLAUDE.md es symlink.
- Modificaciones al AGENTS.md requieren ADR previo (sec. 9 anti-patrón #5).
- Secretos viven en `~/.config/wikiforge/secrets.env` (`chmod 600`), nunca en el repo.

## Estado del repositorio

- Repo de prueba para Fase 0: `~/Developer/ai/uml-class_diagram` (autorización de privacidad: ADR 0001 sec. 6).
- Stack canónico activo (post-ADR 0002): Cognee 1.0 + Ollama (`qwen3:30b` + `bge-m3`) + Kuzu embedded + LanceDB embebida.
- Snapshot de máquina del tiempo previo al pivote: tag `wf-checkpoint-2026-05-02-1746` (commit `828824c`).
