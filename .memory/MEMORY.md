# MEMORY.md — Índice de gobernanza de WikiForge

> Índice operacional del proyecto. Apunta a documentos de gobernanza (decisiones, planes, glosario, riesgos). Cada entrada es una línea ≤ 150 caracteres.

## Decisiones (ADRs)

- [ADR 0001 — LLM Gemini en Fase 0](decisions/0001-llm-gemini-en-fase-0.md) — Status: **Superseded** definitivo por ADR 0005.
- [ADR 0002 — Pivote a stack local + Kuzu](decisions/0002-pivote-stack-local-cognee-1-sin-networkx.md) — Status: **Superseded en parte** (Kuzu sigue vigente, mantenido por ADR 0005).
- [ADR 0003 — Re-pivote a Gemini por bloqueo R2](decisions/0003-re-pivote-gemini-por-bloqueo-r2.md) — Status: **Superseded** por ADR 0005 (R2 vuelve y usuario confirma plan Ollama Cloud activo).
- [ADR 0004 — Scope reducido por quota Flash](decisions/0004-scope-reducido-por-quota-flash.md) — Status: **Superseded** por ADR 0005 (sin cuota → scope completo viable).
- [ADR 0005 — Ollama Cloud + bge-m3 + Kuzu](decisions/0005-ollama-cloud-kimi-bge-m3-local-kuzu.md) — **Stack vigente**. Status: **Active** (2026-05-03).

## Planes activos

- [Plan 0001 — Bootstrap Fase 0](plans/0001-fase-0-bootstrap.md) — Status: **infrastructure DONE, validation gate FAIL** (2026-05-02). Cognify cortado por quota Gemini free tier.
- [Plan 0001 — Preguntas de validación](plans/0001-fase-0-bootstrap-questions.md) — 5 preguntas con ground truth.
- [Plan 0001 — Resultados validación](plans/0001-fase-0-bootstrap-results.md) — 0.0/5.0, FAIL. Causa raíz + caminos de desbloqueo documentados.
- [Plan 0001 — Respuestas crudas](plans/0001-fase-0-bootstrap-raw-answers.json) — output de validate_phase0.py (CHUNKS+SUMMARIES).

## Convenciones

- AGENTS.md de la raíz es el contrato canónico. CLAUDE.md es symlink.
- Modificaciones al AGENTS.md requieren ADR previo (sec. 9 anti-patrón #5).
- Secretos viven en `~/.config/wikiforge/secrets.env` (`chmod 600`), nunca en el repo.

## Estado del repositorio

- Repo de prueba para Fase 0: `~/Developer/ai/uml-class_diagram` (autorización de privacidad: ADR 0001 sec. 6).
- Stack canónico activo (post-ADR 0005): Cognee 1.0 + Ollama Cloud (`kimi-k2.6:cloud`) + `bge-m3` local + Kuzu embedded + LanceDB embebida.
- Snapshot previo al primer pivote: tag `wf-checkpoint-2026-05-02-1746` (commit `828824c`).
- Tag al final del bootstrap día 1 (FAIL por quota): `wf-fase-0-blocked-by-gemini-quota-2026-05-02`.
- Reanudación día 2 con Ollama Cloud — pendiente tag final tras validation gate.
