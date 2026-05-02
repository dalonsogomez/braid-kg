# MEMORY.md — Índice de gobernanza de WikiForge

> Índice operacional del proyecto. Apunta a documentos de gobernanza (decisiones, planes, glosario, riesgos). Cada entrada es una línea ≤ 150 caracteres.

## Decisiones (ADRs)

- [ADR 0001 — LLM Gemini en Fase 0](decisions/0001-llm-gemini-en-fase-0.md) — Status: **Active parcial** (LLM/embeddings reactivados por ADR 0003).
- [ADR 0002 — Pivote a stack local + Kuzu](decisions/0002-pivote-stack-local-cognee-1-sin-networkx.md) — Status: **Superseded en parte** por ADR 0003 (la decisión sobre Kuzu sigue vigente; la de Ollama no por bloqueo de red R2).
- [ADR 0003 — Re-pivote a Gemini por bloqueo R2](decisions/0003-re-pivote-gemini-por-bloqueo-r2.md) — Stack actual: Cognee 1.0 + Gemini 3 Flash + gemini-embedding-001 + Kuzu + LanceDB. Status: **Active** (2026-05-02).

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
- Stack canónico activo (post-ADR 0003): Cognee 1.0 + Gemini 3 Flash + `gemini-embedding-001` + Kuzu embedded + LanceDB embebida.
- Snapshot de máquina del tiempo previo al primer pivote: tag `wf-checkpoint-2026-05-02-1746` (commit `828824c`).
- Tag al final del bootstrap (FAIL por quota): `wf-fase-0-blocked-by-gemini-quota-2026-05-02`.
- Acción siguiente: activar billing en GCP proyecto WikiForge #846938751343 (5 min) y re-ejecutar `index_phase0.py` + `validate_phase0.py`. Ver `.memory/plans/0001-fase-0-bootstrap-results.md` "Próxima acción".
