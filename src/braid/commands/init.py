"""`braid init`: create .braid state plus root-level agent discovery files."""
from __future__ import annotations

from pathlib import Path

from ..paths import config_path, find_git_root, find_project_root


CONFIG_TEMPLATE = """\
dataset_id = "{dataset}"
graph_backend = "kuzu"
vector_backend = "lancedb"
embedder = "bge-m3"
llm = "kimi-k2.6:cloud"
fallback_threshold = 0.55
priority = ["active_file", "project_graph", "project_vector", "global_profile"]

[memory]
temporal_store = ".braid/memory/sessions"
persistent_store = ".braid/memory/persistent"
promotion_policy = "explicit_only"
"""

AGENTS_PROJECT_TEMPLATE = """\
# Proyecto: {dataset}

> Plantilla generada por `braid init`. Edita libremente.

## Stack
- Lenguaje principal: ?
- Tests: ?

## Comandos
- ?

## Convenciones críticas
- ?

## Memoria del proyecto
- Contexto extendido en `.braid/memory/MEMORY.md` y `.braid/memory/decisions/`.
- Knowledge graph disponible vía MCP server `cognee` con `dataset_id={dataset}`.
- Para promover una decisión: `braid promote-decision "..."`.
- Sigue las reglas del `AGENTS.md` canónico de Braid.
"""

MEMORY_INDEX_TEMPLATE = """\
# MEMORY.md - Indice operacional de {dataset}

> Apunta a decisiones, planes, glosario, riesgos. Cada entrada es una linea <= 150 caracteres.

## Decisiones (ADRs)

(vacio - usa `braid promote-decision` para registrar la primera)

## Planes activos

(vacio)

## Convenciones

- AGENTS.md de la raiz es el contrato canonico.
"""


def run(dataset: str | None = None, force: bool = False) -> int:
    root = find_project_root() or find_git_root() or Path.cwd().resolve()
    dataset = dataset or root.name
    print(f"[braid init] root={root}")
    print(f"[braid init] dataset_id={dataset}")

    created: list[str] = []
    skipped: list[str] = []

    for rel in [
        ".braid",
        ".braid/kg",
        ".braid/rag",
        ".braid/memory",
        ".braid/memory/decisions",
        ".braid/memory/plans",
        ".braid/memory/eval",
        ".braid/memory/eval/runs",
        ".braid/wiki",
    ]:
        path = root / rel
        if path.exists():
            skipped.append(rel)
        else:
            path.mkdir(parents=True, exist_ok=True)
            created.append(rel)

    files = {
        str(config_path(root).relative_to(root)): CONFIG_TEMPLATE.format(dataset=dataset),
        "AGENTS.md": AGENTS_PROJECT_TEMPLATE.format(dataset=dataset),
        ".braid/memory/MEMORY.md": MEMORY_INDEX_TEMPLATE.format(dataset=dataset),
    }
    for rel, content in files.items():
        path = root / rel
        if path.exists() and not force:
            skipped.append(rel)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        created.append(rel)

    symlinks = {
        "CLAUDE.md": "AGENTS.md",
        ".github/copilot-instructions.md": "../AGENTS.md",
        ".cursor/rules/main.mdc": "../../AGENTS.md",
    }
    for rel, target in symlinks.items():
        path = root / rel
        if path.exists() or path.is_symlink():
            skipped.append(rel)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to(target)
        created.append(rel)

    print(f"[braid init] created: {len(created)} entries")
    for item in created:
        print(f"  + {item}")
    if skipped:
        print(f"[braid init] skipped (existing): {len(skipped)}")
        for item in skipped:
            print(f"  . {item}")

    print()
    print("[braid init] done. Proximo paso: `braid index`.")
    return 0
