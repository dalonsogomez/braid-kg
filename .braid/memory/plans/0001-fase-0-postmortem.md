# Fase 0 — Post-mortem (sesión solitaria 2026-05-02)

> Síntesis del flujo del día. Acta del brainstorm más amplio que el usuario solicitó tras topar con el blocker `networkx` en Cognee 1.0. No reemplaza los ADRs (que son la decisión auditada), solo les añade contexto humano y aprendizajes para Fase 1.

## Línea de tiempo

| Hora aprox. | Evento | Decisión / artefacto |
|---|---|---|
| ~16:10 | Brainstorm inicial — ¿qué repo y qué stack? | Repo: `uml-class_diagram`. Stack inicial: Gemini cloud (recomendado por brillo en SWE-bench tras descartar MiniMax). |
| ~16:30 | Aviso de privacidad + Q-A/Q-B al usuario | Usuario aprueba: archivos públicos, Q-B indiferente. |
| ~16:45 | ADR 0001 → Accepted, AGENTS.md modificado, plan 0001 escrito | Commits `d8e446b`, `c02e860` |
| ~17:46 | Usuario se va; pide máquina del tiempo + implementación local | Tag `braid-checkpoint-2026-05-02-1746` (`828824c`). |
| ~20:14 | Smoke test E2E con Cognee 1.0 → falla `Unsupported graph database provider: networkx` | Blocker arquitectónico real. |
| ~20:18 | ADR 0002 → Pivote a stack local (Ollama qwen3:30b + bge-m3 + Kuzu) | Commit `faf350f` |
| ~20:20 | `ollama pull bge-m3` y `qwen3:30b` → timeout contra Cloudflare R2 | Blocker de red. |
| ~20:22 | ADR 0003 → re-pivote a Gemini+Kuzu | Commit `c9c8f49` |
| ~20:25 | Smoke test E2E con Gemini+Kuzu → PASS | Stack actual definitivo. |
| ~20:26 | `cognify` de uml-class_diagram → `RESOURCE_EXHAUSTED 429` (1904 errores) | Free tier Gemini = 20 RPD. |
| ~20:38 | Validate ejecutado con CHUNKS+SUMMARIES (sin completion) | Score 0.0/5.0. |
| ~20:48 | Resultados commit + tag `braid-fase-0-blocked-by-gemini-quota-2026-05-02` | Commit `886ada5`, `4d89a34` |

## Tres blockers descubiertos hoy

1. **Cognee 1.0 eliminó `networkx`.** El AGENTS.md sec. 3 lo daba por "default in-process" sin verificación con la versión actual. Aprendizaje: cualquier asunción del AGENTS.md sobre defaults de upstream debe validarse con un smoke test antes de comprometerse en plan.
2. **Cloudflare R2 inaccesible desde esta red** (`ping` y `curl` con timeout). Manifest endpoint de Ollama responde, pero los blobs no. Aprendizaje: el bootstrap necesita un check de conectividad por proveedor en Step 1, no solo verificar binarios.
3. **Free tier de Gemini = 20 RPD.** Insuficiente para `cognify` de un repo con 30 archivos. ADR 0001 sec. 6 Q-B advertía el riesgo y el usuario respondió "indiferente". Aprendizaje: cuando una decisión de privacidad/cuota tiene "indiferente" como respuesta, asumir el peor caso operativo y dimensionar el plan acorde.

## Estado del sistema al cierre

| Componente | Estado |
|---|---|
| Cognee 1.0 | Instalado en `~/.braid/cognee-mcp/cognee-mcp/` (uv venv). |
| Stack `.env` | Gemini 3 Flash + `gemini-embedding-001` + Kuzu + LanceDB. |
| Shim cognee-mcp-stdio.sh | Funcional, lee key desde `~/.config/braid/secrets.env`. |
| MCP server `cognee` en Claude Code | Registrado scope user, `✓ Connected`. |
| Repo de prueba `uml-class_diagram` | git inicializado, governance completa, 2 commits propios. |
| Grafo Kuzu | 64 nodes / 145 edges (parcial — solo primer DataPoint procesado completo). |
| Validación 5/5 | FAIL 0.0/5.0 por grafo parcial. |
| ADRs | 0001 Active parcial, 0002 Superseded parcial (Kuzu vigente), 0003 Active. |
| Tags | `braid-checkpoint-2026-05-02-1746`, `braid-fase-0-blocked-by-gemini-quota-2026-05-02`. |
| Secretos expuestos en transcript | Gemini key (×4 veces), MiniMax key (×1) — pendiente de rotación por el usuario. |

## Próxima acción cuando el usuario vuelva (orden recomendado)

1. **Rotar las dos keys** que quedaron en transcripción.
2. **Decidir camino de desbloqueo** (ver `0001-fase-0-bootstrap-results.md` "Próxima acción"):
   - Camino 1 (recomendado): activar billing en GCP `Braid` #846938751343 y re-ejecutar `index_phase0.py` + `validate_phase0.py`.
   - Camino 2: probar `curl -m 5 https://dd20bb891979d25aebc8bec07b2b3bbc.r2.cloudflarestorage.com`; si responde HTTP, reabrir ruta Ollama local (ADR 0004).
   - Camino 3: HuggingFace + mlx-lm.
3. **Si decisión es camino 1:** la indexación + validación tarda ~5-10 min. Si pasa el gate ≥4/5, tag `braid-fase-0-completed-YYYY-MM-DD`.
4. **Cualquier camino:** abrir Fase 1 (CLI `braid`, wrapper MCP de tres niveles, perfil global).

## Aprendizajes para Fase 1 (no son decisiones, son insumos)

1. **Test de stack canónico antes de fijar AGENTS.md.** Cualquier nuevo bullet en sec. 3 debe pasar un mini-smoke test (provider funciona, modelo existe, backend está soportado por el engine en su versión actual). Esto se traduce a un comando `braid doctor` en Fase 1.
2. **Diagnóstico de red por proveedor en `braid init`.** Verificar conectividad a los endpoints relevantes (Ollama R2, HF Hub, Gemini, Anthropic) y reportar al usuario antes de elegir stack.
3. **Suite `braid eval` con quota awareness.** Antes de ejecutar el cognify completo, estimar requests necesarios y verificar contra cuotas conocidas del provider. Abortar con mensaje claro si la cuota es insuficiente.
4. **El wrapper MCP de tres niveles debe ser el cerebro en Fase 1** (sec. 4.3 del AGENTS.md). Sin él, las búsquedas siempre van al dataset global; el flujo `cwd → git root → .kgconfig` es lo que da valor real.

## Cierre

Sistema listo para producir resultados en cuanto se desbloquee la cuota Gemini o vuelva la conectividad a R2. La densidad de gobernanza de hoy (3 ADRs en una tarde) es alta pero defendible: cada pivote tiene causa técnica concreta, y la trazabilidad permite restaurar cualquier punto previo con un solo `git checkout` al tag.

Cualquier crítica al flujo es bienvenida — quedó documentada para que la sesión siguiente parta de la realidad y no de las asunciones del AGENTS.md original.
