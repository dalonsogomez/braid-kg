# MEMORY.md — Índice de gobernanza de Braid

> Índice operacional del proyecto. Apunta a documentos de gobernanza (decisiones, planes, glosario, riesgos). Cada entrada es una línea ≤ 150 caracteres.

## Decisiones (ADRs)

- [ADR-0001 — Rename histórico WikiForge -> Fairlead](decisions/ADR-0001-rename-wikiforge-to-fairlead.md) — **Historical** (2025-08-21). Conservado solo para trazabilidad de nombres previos.
- [ADR 0001 — LLM Gemini en Fase 0](decisions/0001-llm-gemini-en-fase-0.md) — Status: **Superseded** definitivo por ADR 0005.
- [ADR 0002 — Pivote a stack local + Kuzu](decisions/0002-pivote-stack-local-cognee-1-sin-networkx.md) — Status: **Superseded en parte** (Kuzu sigue vigente, mantenido por ADR 0005).
- [ADR 0003 — Re-pivote a Gemini por bloqueo R2](decisions/0003-re-pivote-gemini-por-bloqueo-r2.md) — Status: **Superseded** por ADR 0005 (R2 vuelve y usuario confirma plan Ollama Cloud activo).
- [ADR 0004 — Scope reducido por quota Flash](decisions/0004-scope-reducido-por-quota-flash.md) — Status: **Superseded** por ADR 0005 (sin cuota → scope completo viable).
- [ADR 0005 — Ollama Cloud + bge-m3 + Kuzu](decisions/0005-ollama-cloud-kimi-bge-m3-local-kuzu.md) — **Stack vigente**. Status: **Active** (2026-05-03). Su sec. 2.2 fue corregida por ADR 0006.
- [ADR 0006 — `.env` real con dodges LiteLLM/Ollama/pydantic](decisions/0006-env-litellm-colon-dodge.md) — **Active** (2026-05-03). Sustituye sec. 13.2 de AGENTS.md y sec. 2.2 de ADR 0005.
- [ADR 0007 — Centralizar cognee_system en ~/.braid/cognee/](decisions/0007-todo-centralizar-cognee-system-en-wikiforge-cognee.md) — **Resolved** (2026-05-04). Centralización vía env vars `SYSTEM_ROOT_DIRECTORY` + `DATA_ROOT_DIRECTORY` + `CACHE_ROOT_DIRECTORY` aplicadas en `braid.config` y `cognee-mcp-stdio.sh`. Promovido en sesión N, resuelto en N+1.
- [ADR 0008 — Alinear versions de cognee entre venvs](decisions/0008-alinear-versions-de-cognee-entre-venvs-wf-y-cognee-mcp.md) — **Resolved** (2026-05-07). Ambos venvs ahora usan ladybug 0.16.1 + patch del version mapping; cognee-mcp upgrade a 1.0.8 vía edit del pyproject + `uv lock --upgrade-package cognee`. Cross-venv recall validado end-to-end.
- [ADR 0009 — Auto-bootstrap RAG vía SessionStart hook](decisions/0009-auto-bootstrap-rag-via-session-hook.md) — **Active** (2026-05-09). Comando `claude-session-start` (<500 ms, sin LLM) reporta estado memoria a cada inicio de sesión Claude Code; `claude-init` cablea hook idempotente; `sync` incremental por mtime + timeout 120s mitiga cleanup hang upstream.
- [ADR 0010 — Suite `braid eval`](decisions/0010-suite-wikiforge-eval.md) — **Active** (2026-05-09). Comando `braid eval` operativo (ya no stub); 10 preguntas en `.braid/memory/eval/questions.json`; scoring por substring + recall@1/recall@K; runs guardados en `.braid/memory/eval/runs/`. Cumple criterio AGENTS.md sec. 10 Fase 2.
- [ADR 0011 — Reranker bge-reranker-v2-m3](decisions/0011-reranker-bge-v2-m3.md) — **Superseded** por ADR 0012 (2026-05-09 mismo día). User vetó descarga local; deep-research validó cloud-only.
- [ADR 0012 — Reranker cloud vía OpenRouter (Cohere Rerank 4 Fast)](decisions/0012-reranker-cloud-cohere-openrouter.md) — **Active** (2026-05-09). Sin descarga local, passthrough $0 en OpenRouter, multilingüe 100+, 32K context. `runner.rerank_via_openrouter` implementado. Activable via `braid eval --rerank` (requiere `OPENROUTER_API_KEY` en secrets.env). Validado por deep-research 30+ sources.
- [ADR 0014 — DuckDB Catalog](decisions/0014-duckdb-catalog.md) — **Accepted** (2026-05-10). Usa DuckDB/DuckLake como catalog storage SQL-queryable para memoria, KG y RAG.
- [ADR 0015 — Adopt Braid name and layout](decisions/0015-adopt-braid-name-and-layout.md) — **Accepted** (2026-06-05). Nombre canónico `braid`; layout proyecto-local bajo `.braid/`.

## Planes activos

- [Plan 0001 — Bootstrap Fase 0](plans/0001-fase-0-bootstrap.md) — Status: **PASS 4.0/5.0** (2026-05-03) con stack ADR 0005.
- [Plan 0001 — Preguntas de validación](plans/0001-fase-0-bootstrap-questions.md) — 5 preguntas con ground truth.
- [Plan 0001 — Resultados validación](plans/0001-fase-0-bootstrap-results.md) — **PASS 4.0/5.0**. Q1/Q4/Q5 = 1.0, Q2/Q3 = 0.5 (recuperables top-5, no top-1; reranker pendiente).
- [Plan 0001 — Respuestas crudas](plans/0001-fase-0-bootstrap-raw-answers.json) — output de validate_phase0.py (CHUNKS+SUMMARIES).
- [Plan 0001 — Post-mortem día 1](plans/0001-fase-0-postmortem.md) — historial de los 5 pivotes hasta ADR 0005.
- [Plan 0002 — Bootstrap Fase 1](plans/0002-fase-1-bootstrap.md) — Status: **PASS** (2026-05-03). CLI `braid` funcional + 2 repos operativos + perfil global + ADR 0007 promovido.
- [Plan 0002 — Resultados Fase 1](plans/0002-fase-1-bootstrap-results.md) — criterio de salida cumplido vía filesystem-based recall; cognee semántico diferido a Fase 2 por bugs upstream.
- [Plan 0003 — Progresos hacia Fase 2](plans/0003-fase-2-progresos.md) — log vivo. Sesión 2026-05-04: ADR 0007 resuelto (storage centralizado + ladybug patch); ADR 0008 promovido (version skew entre venvs); 2026-05-09: ADR 0009 (auto-bootstrap RAG); cleanup async hang **mitigado** vía `asyncio.wait_for(timeout=120)` en `runner.cognify`.
- [Plan 0004 — Auto-bootstrap RAG](plans/0004-auto-bootstrap-rag.md) — Status: **PASS** (2026-05-09). `claude-session-start` p50=250ms, `claude-init` idempotente, `sync` at-rest 0.41s, dogfooding activo en `.claude/settings.json` del repo.
- [Plan 0005 — Suite `braid eval` + baseline Fase 2](plans/0005-wikiforge-eval-baseline.md) — Status: **PASS criterio sec. 10** (2026-05-09). Baseline `5.5/10` (recall@1=0.40, recall@K=0.70) registrado en `.braid/memory/eval/runs/baseline-fase-2.json` contra dataset parcial. Reindex completo bloqueado por síntoma 11.8 activo (Ollama Cloud caído).
- [Plan 0006 — Activación reranker](plans/0006-reranker-activation.md) — Status: **Blocked** (2026-05-09). ADR 0011 Proposed; activación pendiente de cierre síntoma 11.8.

## Convenciones

- AGENTS.md de la raíz es el contrato canónico. CLAUDE.md es symlink.
- Modificaciones al AGENTS.md requieren ADR previo (sec. 9 anti-patrón #5).
- Secretos viven en `~/.config/braid/secrets.env` (`chmod 600`), nunca en el repo.

## Estado del repositorio

- Repo de prueba para Fase 0: `~/Developer/ai/uml-class_diagram` (autorización de privacidad: ADR 0001 sec. 6).
- Stack canónico activo (post-ADR 0005): Cognee 1.0 + Ollama Cloud (`kimi-k2.6:cloud`) + `bge-m3` local + Kuzu embedded + LanceDB embebida.
- Snapshot previo al primer pivote: tag `wf-checkpoint-2026-05-02-1746` (commit `828824c`).
- Tag al final del bootstrap día 1 (FAIL por quota): `wf-fase-0-blocked-by-gemini-quota-2026-05-02`.
- Tag al cierre PASS de Fase 0 (día 2 con ADR 0005): `wf-fase-0-completed-2026-05-03`.
- Tag al cierre PASS de Fase 1 (CLI + perfil global + promote-decision demostrado): `wf-fase-1-completed-2026-05-03`.
