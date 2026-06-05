"""`fairlead init`: crear .kg/.rag/.memory/.kgconfig + symlinks AGENTS.md → CLAUDE.md."""
from __future__ import annotations

import sys
from pathlib import Path

from ..paths import find_git_root


KGCONFIG_TEMPLATE = """\
dataset_id = "{dataset}"
graph_backend = "kuzu"
vector_backend = "lancedb"
embedder = "bge-m3"
llm = "kimi-k2.6:cloud"
fallback_threshold = 0.55
priority = ["active_file", "project_graph", "project_vector", "global_profile"]

[memory]
temporal_store = ".memory/sessions"
persistent_store = ".memory/persistent"
promotion_policy = "explicit_only"
"""

AGENTS_PROJECT_TEMPLATE = """\
# Proyecto: {dataset}

> Plantilla generada por `fairlead init`. Edita libremente.

## Stack
- Lenguaje principal: ?
- Tests: ?

## Comandos
- ?

## Convenciones críticas
- ?

## Memoria del proyecto
- Contexto extendido en `.memory/MEMORY.md` y `.memory/decisions/`.
- Knowledge graph disponible vía MCP server `cognee` con `dataset_id={dataset}`.
- Para promover una decisión: `fairlead promote-decision "..."`.
- Sigue las reglas del `AGENTS.md` canónico de Fairlead.
"""

MEMORY_INDEX_TEMPLATE = """\
# MEMORY.md — Índice operacional de {dataset}

> Apunta a decisiones, planes, glosario, riesgos. Cada entrada es una línea ≤ 150 caracteres.

## Decisiones (ADRs)

(vacío — usa `fairlead promote-decision` para registrar la primera)

## Planes activos

(vacío)

## Convenciones

- AGENTS.md de la raíz es el contrato canónico.
"""


def run(dataset: str | None = None, force: bool = False) -> int:
    root = find_git_root() or Path.cwd().resolve()
    dataset = dataset or root.name
    print(f"[fairlead init] root={root}")
    print(f"[fairlead init] dataset_id={dataset}")

    created: list[str] = []
    skipped: list[str] = []

    # Directorios
    for d in [".kg", ".rag", ".memory", ".memory/decisions", ".memory/plans"]:
        p = root / d
        if p.exists():
            skipped.append(d)
        else:
            p.mkdir(parents=True, exist_ok=True)
            created.append(d)

    # Files
    files = {
        ".kgconfig": KGCONFIG_TEMPLATE.format(dataset=dataset),
        "AGENTS.md": AGENTS_PROJECT_TEMPLATE.format(dataset=dataset),
        ".memory/MEMORY.md": MEMORY_INDEX_TEMPLATE.format(dataset=dataset),
    }
    for rel, content in files.items():
        p = root / rel
        if p.exists() and not force:
            skipped.append(rel)
            continue
        p.write_text(content)
        created.append(rel)

    # Symlinks
    symlinks = {
        "CLAUDE.md": "AGENTS.md",
        ".github/copilot-instructions.md": "../AGENTS.md",
        ".cursor/rules/main.mdc": "../../AGENTS.md",
    }
    for rel, target in symlinks.items():
        p = root / rel
        if p.exists() or p.is_symlink():
            skipped.append(rel)
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        p.symlink_to(target)
        created.append(rel)

    print(f"[fairlead init] created: {len(created)} entries")
    for c in created:
        print(f"  + {c}")
    if skipped:
        print(f"[fairlead init] skipped (existing): {len(skipped)}")
        for s in skipped:
            print(f"  · {s}")

    print()
    print("[fairlead init] done. Próximo paso: `fairlead index`.")
    return 0
