"""`wikiforge index`: ingestar código + docs del proyecto activo a Cognee."""
from __future__ import annotations

import sys
from pathlib import Path

from ..paths import resolve_context
from ..runner import annotate_file, run_add, run_cognify, run_prune


DEFAULT_CODE_GLOBS = ["src/**/*.py", "**/*.py"]
DEFAULT_DOC_GLOBS = ["README.md", "MEMORY.md", "AGENTS.md", "CLAUDE.md", "docs/**/*.md", ".memory/**/*.md"]
EXCLUDE_PARTS = {"_backup", "output", "__pycache__", ".venv", ".git", "build", ".kg", ".rag"}


def _is_excluded(p: Path) -> bool:
    parts = set(p.parts)
    return bool(parts & EXCLUDE_PARTS)


def _collect(root: Path, globs: list[str], kind: str) -> list[str]:
    inputs: list[str] = []
    seen: set[Path] = set()
    for g in globs:
        for p in root.glob(g):
            if not p.is_file() or _is_excluded(p) or p in seen:
                continue
            try:
                inputs.append(annotate_file(p, root, kind))
                seen.add(p)
            except OSError as e:
                print(f"  skip {p}: {e}", file=sys.stderr)
    return inputs


def run(rebuild: bool = False, extra_globs: list[str] | None = None) -> int:
    ctx = resolve_context()
    print(f"[wikiforge index] root={ctx.root} dataset={ctx.dataset_id}")
    if not ctx.has_kg and not (ctx.root / ".kgconfig").is_file():
        print("[wikiforge index] no .kg/ ni .kgconfig encontrados — corre `wikiforge init` primero.", file=sys.stderr)
        return 1

    if rebuild:
        print("[wikiforge index] --rebuild: prune_data + prune_system (DESTRUCTIVO)...")
        run_prune()

    code = _collect(ctx.root, DEFAULT_CODE_GLOBS, "code")
    docs = _collect(ctx.root, DEFAULT_DOC_GLOBS, "doc")
    extra = _collect(ctx.root, list(extra_globs or []), "extra") if extra_globs else []

    inputs = code + docs + extra
    if not inputs:
        print("[wikiforge index] FATAL: no inputs collected", file=sys.stderr)
        return 1

    print(f"[wikiforge index] collected {len(code)} code + {len(docs)} doc + {len(extra)} extra = {len(inputs)} total")
    print(f"[wikiforge index] adding to dataset {ctx.dataset_id}...")
    run_add(inputs, ctx.dataset_id)

    print("[wikiforge index] cognifying (esto invoca el LLM, puede tardar varios minutos)...")
    run_cognify(ctx.dataset_id)

    print("[wikiforge index] done.")
    return 0
