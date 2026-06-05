# Plan 0002 — Bootstrap Fase 1 (Gobierno)

- **Status:** en curso (2026-05-03)
- **Criterio de salida AGENTS.md sec. 10:** una decisión técnica ha sido promovida sesión → proyecto vía `braid promote-decision`, y posteriormente recordada en una sesión nueva del mismo repo.
- **Stack:** ADR 0005 + ADR 0006 (sin cambios respecto a Fase 0).

## Entregables

1. **CLI `braid`** instalado y operativo con los 7 comandos canónicos (algunos como stub).
2. **Estructura `.kg/.rag/.memory/.kgconfig`** vía `braid init` en al menos dos repos.
3. **Perfil global** en `~/.braid/profile/` con AGENTS.md + preferences.json.
4. **Demostración promote-decision → recall** sobre el repo dogfooding (Braid mismo).

## Repos operativos al cierre

| Repo | Path | Rol | Estado |
|---|---|---|---|
| `vp-class-diagram-agent` | `~/Developer/ai/uml-class_diagram` | Test-bed Fase 0 | Indexado (ADR 0005+0006) — KG con ~30 inputs |
| `Braid` (dogfood) | `~/Developer/claude/code-projects/Braid` | Dogfooding de la propia herramienta | Indexar en este plan |

## Comandos implementados

- ✅ `braid init` — scaffold idempotente
- ✅ `braid index` — colecta src/**/*.py + docs + .memory + AGENTS + README, llama cognee.add+cognify
- ✅ `braid ask` — cognee.search con `--type CHUNKS|SUMMARIES|GRAPH_COMPLETION|...`
- ✅ `braid promote-decision` — genera ADR numerado en .memory/decisions/
- ✅ `braid promote-to-global` — copia ADR a `~/.braid/profile/decisions/`
- ✅ `braid demote` — mueve ADR a `_demoted/`
- ✅ `braid sync` — alias de index incremental
- ✅ `braid status` — resumen del proyecto activo + perfil global
- ⏳ `braid eval` — stub (Fase 2)
- ⏳ `braid wiki build` — stub (Mes 2+)

## Arquitectura del paquete

```
src/braid/
├── __init__.py
├── cli.py              # argparse, despacha a commands/
├── config.py           # apply_stack_env (ADR 0005+0006)
├── paths.py            # resolve_context: cwd → git root → .kgconfig → ~/.braid/profile/
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

1. ✅ `pyproject.toml` con `[project.scripts] braid = "braid.cli:main"`.
2. ✅ `uv venv && uv pip install -e .` → CLI disponible en `.venv/bin/braid`.
3. ✅ `braid --help` y `braid status` smoke-tests OK.
4. ✅ `~/.braid/profile/` creado con AGENTS.md + preferences.json.
5. ✅ `braid init` en el propio repo Braid (dogfooding).
6. 🚧 `braid index` indexa AGENTS.md + ADRs + planes + src/braid/.
7. ⏳ `braid ask "What is the stack vigente?"` debe devolver chunks de ADR 0005/0006.
8. ⏳ `braid promote-decision "..."` → genera ADR 0007.
9. ⏳ `braid ask "What was promoted recently?"` (simulando nueva sesión) debe surfacear ADR 0007.

## Criterio de salida — chequeo

- [ ] CLI instalado y todos los comandos responden.
- [ ] Dos repos con estructura Braid.
- [ ] Perfil global creado.
- [ ] Una decisión promovida y recordada.
