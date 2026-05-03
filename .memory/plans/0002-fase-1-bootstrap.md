# Plan 0002 — Bootstrap Fase 1 (Gobierno)

- **Status:** en curso (2026-05-03)
- **Criterio de salida AGENTS.md sec. 10:** una decisión técnica ha sido promovida sesión → proyecto vía `wikiforge promote-decision`, y posteriormente recordada en una sesión nueva del mismo repo.
- **Stack:** ADR 0005 + ADR 0006 (sin cambios respecto a Fase 0).

## Entregables

1. **CLI `wikiforge`** instalado y operativo con los 7 comandos canónicos (algunos como stub).
2. **Estructura `.kg/.rag/.memory/.kgconfig`** vía `wikiforge init` en al menos dos repos.
3. **Perfil global** en `~/.wikiforge/profile/` con AGENTS.md + preferences.json.
4. **Demostración promote-decision → recall** sobre el repo dogfooding (WikiForge mismo).

## Repos operativos al cierre

| Repo | Path | Rol | Estado |
|---|---|---|---|
| `vp-class-diagram-agent` | `~/Developer/ai/uml-class_diagram` | Test-bed Fase 0 | Indexado (ADR 0005+0006) — KG con ~30 inputs |
| `WikiForge` (dogfood) | `~/Developer/claude/code-projects/WikiForge` | Dogfooding de la propia herramienta | Indexar en este plan |

## Comandos implementados

- ✅ `wikiforge init` — scaffold idempotente
- ✅ `wikiforge index` — colecta src/**/*.py + docs + .memory + AGENTS + README, llama cognee.add+cognify
- ✅ `wikiforge ask` — cognee.search con `--type CHUNKS|SUMMARIES|GRAPH_COMPLETION|...`
- ✅ `wikiforge promote-decision` — genera ADR numerado en .memory/decisions/
- ✅ `wikiforge promote-to-global` — copia ADR a `~/.wikiforge/profile/decisions/`
- ✅ `wikiforge demote` — mueve ADR a `_demoted/`
- ✅ `wikiforge sync` — alias de index incremental
- ✅ `wikiforge status` — resumen del proyecto activo + perfil global
- ⏳ `wikiforge eval` — stub (Fase 2)
- ⏳ `wikiforge wiki build` — stub (Mes 2+)

## Arquitectura del paquete

```
src/wikiforge/
├── __init__.py
├── cli.py              # argparse, despacha a commands/
├── config.py           # apply_stack_env (ADR 0005+0006)
├── paths.py            # resolve_context: cwd → git root → .kgconfig → ~/.wikiforge/profile/
├── runner.py           # wrappers cognee.add/cognify/search async + helpers síncronos
└── commands/
    ├── init.py
    ├── index.py
    ├── ask.py
    ├── promote.py
    ├── sync.py
    └── status.py
```

## Pasos del bootstrap

1. ✅ `pyproject.toml` con `[project.scripts] wikiforge = "wikiforge.cli:main"`.
2. ✅ `uv venv && uv pip install -e .` → CLI disponible en `.venv/bin/wikiforge`.
3. ✅ `wikiforge --help` y `wikiforge status` smoke-tests OK.
4. ✅ `~/.wikiforge/profile/` creado con AGENTS.md + preferences.json.
5. ✅ `wikiforge init` en el propio repo WikiForge (dogfooding).
6. 🚧 `wikiforge index` indexa AGENTS.md + ADRs + planes + src/wikiforge/.
7. ⏳ `wikiforge ask "What is the stack vigente?"` debe devolver chunks de ADR 0005/0006.
8. ⏳ `wikiforge promote-decision "..."` → genera ADR 0007.
9. ⏳ `wikiforge ask "What was promoted recently?"` (simulando nueva sesión) debe surfacear ADR 0007.

## Criterio de salida — chequeo

- [ ] CLI instalado y todos los comandos responden.
- [ ] Dos repos con estructura WikiForge.
- [ ] Perfil global creado.
- [ ] Una decisión promovida y recordada.
