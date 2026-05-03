# MEMORY.md — Índice de gobernanza de WikiForge

> Índice operacional del proyecto. Apunta a documentos de gobernanza (decisiones, planes, glosario, riesgos). Cada entrada es una línea ≤ 150 caracteres.

## Decisiones (ADRs)

- [ADR 0001 — LLM Gemini en Fase 0](decisions/0001-llm-gemini-en-fase-0.md) — Status: **Superseded** definitivo por ADR 0005.
- [ADR 0002 — Pivote a stack local + Kuzu](decisions/0002-pivote-stack-local-cognee-1-sin-networkx.md) — Status: **Superseded en parte** (Kuzu sigue vigente, mantenido por ADR 0005).
- [ADR 0003 — Re-pivote a Gemini por bloqueo R2](decisions/0003-re-pivote-gemini-por-bloqueo-r2.md) — Status: **Superseded** por ADR 0005 (R2 vuelve y usuario confirma plan Ollama Cloud activo).
- [ADR 0004 — Scope reducido por quota Flash](decisions/0004-scope-reducido-por-quota-flash.md) — Status: **Superseded** por ADR 0005 (sin cuota → scope completo viable).
- [ADR 0005 — Ollama Cloud + bge-m3 + Kuzu](decisions/0005-ollama-cloud-kimi-bge-m3-local-kuzu.md) — **Stack vigente**. Status: **Active** (2026-05-03). Su sec. 2.2 fue corregida por ADR 0006.
- [ADR 0006 — `.env` real con dodges LiteLLM/Ollama/pydantic](decisions/0006-env-litellm-colon-dodge.md) — **Active** (2026-05-03). Sustituye sec. 13.2 de AGENTS.md y sec. 2.2 de ADR 0005.

## Planes activos

- [Plan 0001 — Bootstrap Fase 0](plans/0001-fase-0-bootstrap.md) — Status: **PASS 4.0/5.0** (2026-05-03) con stack ADR 0005.
- [Plan 0001 — Preguntas de validación](plans/0001-fase-0-bootstrap-questions.md) — 5 preguntas con ground truth.
- [Plan 0001 — Resultados validación](plans/0001-fase-0-bootstrap-results.md) — **PASS 4.0/5.0**. Q1/Q4/Q5 = 1.0, Q2/Q3 = 0.5 (recuperables top-5, no top-1; reranker pendiente).
- [Plan 0001 — Respuestas crudas](plans/0001-fase-0-bootstrap-raw-answers.json) — output de validate_phase0.py (CHUNKS+SUMMARIES).
- [Plan 0001 — Post-mortem día 1](plans/0001-fase-0-postmortem.md) — historial de los 5 pivotes hasta ADR 0005.

## Convenciones

- AGENTS.md de la raíz es el contrato canónico. CLAUDE.md es symlink.
- Modificaciones al AGENTS.md requieren ADR previo (sec. 9 anti-patrón #5).
- Secretos viven en `~/.config/wikiforge/secrets.env` (`chmod 600`), nunca en el repo.

## Estado del repositorio

- Repo de prueba para Fase 0: `~/Developer/ai/uml-class_diagram` (autorización de privacidad: ADR 0001 sec. 6).
- Stack canónico activo (post-ADR 0005): Cognee 1.0 + Ollama Cloud (`kimi-k2.6:cloud`) + `bge-m3` local + Kuzu embedded + LanceDB embebida.
- Snapshot previo al primer pivote: tag `wf-checkpoint-2026-05-02-1746` (commit `828824c`).
- Tag al final del bootstrap día 1 (FAIL por quota): `wf-fase-0-blocked-by-gemini-quota-2026-05-02`.
- Tag al cierre PASS de Fase 0 (día 2 con ADR 0005): `wf-fase-0-completed-2026-05-03`.
