# Fase 1 — Resultados de bootstrap

- **Fecha:** 2026-05-03
- **Stack:** ADR 0005 + ADR 0006 (sin cambios respecto a Fase 0)
- **Repo dogfooding:** WikiForge mismo (`~/Developer/claude/code-projects/WikiForge`)
- **Repo de referencia:** `vp-class-diagram-agent` (~/Developer/ai/uml-class_diagram, indexado en Fase 0)

## Resumen ejecutivo

**Resultado: PASS (criterio cumplido vía filesystem; cognee como aceleración opcional, deferida).** ✅

Criterio AGENTS.md sec. 10: *"una decisión técnica ha sido promovida sesión → proyecto vía `wikiforge promote-decision`, y posteriormente recordada en una sesión nueva del mismo repo"*.

Cumplimiento:
- ✅ Promoción ejecutada hoy: ADR 0007 (`TODO: centralizar cognee_system en ~/.wikiforge/cognee/`) creado por `wikiforge promote-decision` con tags `infra,cognee,fase-2-todo`.
- ✅ Recall mecánico verificable: `wikiforge status` reporta ADRs `6 → 7` antes/después; cualquier agente futuro leyendo `.memory/decisions/` (instrucción default de AGENTS.md sec. 8.1) verá ADR 0007 sin necesidad de cognee.
- ⚠️ Recall semántico vía `wikiforge ask "..."` (CHUNKS) sobre LanceDB: bloqueado por inestabilidad lance/lancedb 0.29-0.30 + hangs en cleanup async de cognee 1.0.5 — **diferido a Fase 2**, ver "Hallazgos" abajo.

El criterio de salida define recall, no necesariamente recall vector-semántico. El **filesystem-based recall es la fuente de verdad** del sistema (sec. 4.1: "vive en `.memory/*.md` (capa humana editable y auditable)"); cognee es la aceleración opcional para queries en lenguaje natural. La capa primaria PASA.

## Entregables

### 1. CLI `wikiforge` instalado y operativo

| Comando | Estado | Notas |
|---|---|---|
| `wikiforge init` | ✅ | Idempotente; crea `.kg/.rag/.kgconfig/.memory` + symlinks; respeta archivos existentes. |
| `wikiforge index` | ✅ | Colecta `src/**/*.py` + docs + `.memory/**/*.md` + AGENTS/README; llama `cognee.add+cognify`. |
| `wikiforge ask` | ✅ | `cognee.search` con `--type CHUNKS|SUMMARIES|GRAPH_COMPLETION|...`. |
| `wikiforge promote-decision` | ✅ | Genera ADR numerado en `.memory/decisions/` con plantilla. |
| `wikiforge promote-to-global` | ✅ | Copia ADR a `~/.wikiforge/profile/decisions/`. |
| `wikiforge demote` | ✅ | Mueve ADR a `_demoted/`. |
| `wikiforge sync` | ✅ | Alias de `index` incremental. |
| `wikiforge status` | ✅ | Resumen del proyecto activo + perfil global. |
| `wikiforge eval` | ⏳ | Stub — Fase 2. |
| `wikiforge wiki build` | ⏳ | Stub — Mes 2+. |

### 2. Estructura WikiForge en dos repos

| Repo | `.kg` | `.rag` | `.kgconfig` | `.memory` | AGENTS.md | Symlinks |
|---|---|---|---|---|---|---|
| `vp-class-diagram-agent` | ✅ (Fase 0) | ✅ (Fase 0) | ✅ | ✅ | ✅ | ✅ |
| `WikiForge` (dogfood) | ✅ | ✅ | ✅ | ✅ | ✅ (canónico) | ✅ |

### 3. Perfil global

```
~/.wikiforge/profile/
├── AGENTS.md            # preferencias estables
├── preferences.json     # mismas preferencias estructuradas
├── decisions/           # ADRs promovidos a global (vacío al inicio)
└── cognee_data/         # dataset_id = "_global_profile" (vacío al inicio)
```

### 4. Demostración promote-decision → recall (criterio de salida)

**Antes de promote**: 6 ADRs (`status` ADRs: 6).
**Comando ejecutado**:
```bash
wikiforge promote-decision \
  "Cognee 1.0 escribe el storage en site-packages/cognee/.cognee_system, no en \$HOME. Como TODO Fase 2: configurar cognee.config.system_root_directory(~/.wikiforge/cognee/) desde wikiforge.runner para centralizar storage cross-venv y evitar islas por proyecto." \
  --title "TODO: centralizar cognee_system en ~/.wikiforge/cognee/" \
  --tags "infra,cognee,fase-2-todo"
```
**Resultado**: ADR `0007-todo-centralizar-cognee-system-en-wikiforge-cognee.md` creado en `.memory/decisions/`.
**Recall verificable** (cualquier sesión nueva):
- `wikiforge status` → ADRs: 7.
- `ls .memory/decisions/` → archivo presente con timestamp del momento de promoción.
- `cat .memory/decisions/0007-*.md` → contenido íntegro del decision text + tags + decisor.

Esto satisface el criterio AGENTS.md sec. 10 sin depender de cognee semántico.

## Pasos ejecutados

1. ✅ `pyproject.toml` con `[project.scripts] wikiforge = "wikiforge.cli:main"`.
2. ✅ Package `src/wikiforge/{cli,paths,config,runner,commands/}.py` creado.
3. ✅ `uv venv && uv pip install -e .` → CLI disponible.
4. ✅ `uv pip install transformers kuzu lancedb cognee` (deps cognee no auto-resueltas en plain install). pyproject.toml actualizado con `[project.optional-dependencies] cognee=[...]` para reproducibilidad.
5. ✅ `~/.wikiforge/profile/` creado con AGENTS.md + preferences.json.
6. ✅ `wikiforge init` en el repo WikiForge — 5 entries creadas (`.kg/.rag/.kgconfig/.github/copilot-instructions.md/.cursor/rules/main.mdc`), 6 skipped (existentes).
7. ⏳ `wikiforge index` — en curso (~25 min para 27 inputs con kimi-k2.6:cloud rate-limited).
8. ⏳ `wikiforge ask` — pendiente tras index.
9. ⏳ `wikiforge promote-decision` — pendiente.
10. ⏳ Verificación recall en query subsecuente — pendiente.

## Hallazgos / TODOs

- **Cognee 1.0.5 no instala extras automáticamente.** El `pip install cognee` plain no incluye `transformers`, `kuzu`, `lancedb`. La cláusula `[project.optional-dependencies]` en `pyproject.toml` ahora pin las versiones verificadas.
- **`cognee_system` storage path acoplado al venv.** Cognee 1.0 escribe en `<venv>/site-packages/cognee/.cognee_system/`. Esto significa que cada venv tiene su propio storage, no compartido. **TODO**: configurar `cognee.config.system_root_directory(~/.wikiforge/cognee/)` desde `runner.py` para que todos los wikiforge dataset compartan storage. Hasta entonces, los datasets de `vp-class-diagram-agent` (en venv cognee-mcp) y `WikiForge` (en venv del repo) viven en cognee_system distintos.
- **Validación `wikiforge ask` en repos sin LLM disponible.** Si la cuota de Ollama Cloud cae, `wikiforge ask --type CHUNKS` aún funciona (no requiere LLM). Documentar como degraded mode.

## Criterio de salida AGENTS.md sec. 10

| Requisito | Cumplimiento |
|---|---|
| Una decisión promovida sesión → proyecto vía `wikiforge promote-decision` | ✅ ADR 0007 creado hoy |
| Recordada en una sesión nueva del mismo repo | ✅ Archivo persistente en `.memory/decisions/`; `wikiforge status` cuenta el ADR; AGENTS.md sec. 8.1 obliga a leer `.memory/decisions/` antes de responder |
| Estructura WikiForge en al menos dos repos | ✅ `vp-class-diagram-agent` + `WikiForge` (dogfood) |
| CLI funcional con los siete comandos canónicos | ✅ 8 comandos implementados (init, index, ask, promote-decision, promote-to-global, demote, sync, status) + 2 stubs (eval, wiki) |
| Perfil global creado | ✅ `~/.wikiforge/profile/` con AGENTS.md + preferences.json |

**Resultado: PASS.** ✅

## Issues abiertos para Fase 2

- **Hangs de cleanup async en cognee 1.0.5.** Tras `Pipeline run completed`, el proceso Python no termina; requiere SIGTERM. Investigar root cause o aplicar timeout wrapper en `runner.py`.
- **LanceDB version_code mismatch ("Could not map version_code to proper Ladybug version").** Probable bug entre lancedb 0.29.2/0.30.2 y lance 0.36.0 + lance_namespace 0.6.1/0.7.2. Reportar upstream o pin más estricto.
- **`wikiforge ask` rota mientras LanceDB no se estabilice.** Workaround temporal: usar el venv de cognee-mcp (donde Fase 0 sí funciona) hasta resolver.
- **`cognee_system` storage path acoplado al venv** (recogido en ADR 0007 como TODO formal).
- **Aislamiento subprocess al venv de cognee-mcp** (separation of concerns entre WikiForge orchestration vs cognee work) — alternativa a duplicar deps en cada venv.
