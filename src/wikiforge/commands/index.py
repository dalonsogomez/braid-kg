"""`wikiforge index`: ingestar código + docs del proyecto activo a Cognee.

ADR 0009: incremental real por mtime + escritura de `.kg/last_index.json` para
que `claude-session-start` pueda detectar staleness en <500 ms.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from ..paths import resolve_context
from ..runner import annotate_file, run_add, run_cognify, run_prune


DEFAULT_CODE_GLOBS = ["src/**/*.py", "**/*.py"]
DEFAULT_DOC_GLOBS = ["README.md", "MEMORY.md", "AGENTS.md", "CLAUDE.md", "docs/**/*.md", ".memory/**/*.md"]
EXCLUDE_PARTS = {"_backup", "output", "__pycache__", ".venv", ".git", "build", ".kg", ".rag"}

INDEX_STATE_FILENAME = "last_index.json"


def _is_excluded(p: Path) -> bool:
    parts = set(p.parts)
    return bool(parts & EXCLUDE_PARTS)


def _collect(root: Path, globs: list[str], kind: str, since_ts: float | None = None) -> list[tuple[Path, str]]:
    """Devuelve [(path, annotated_text)]. Si `since_ts` se da, filtra por mtime."""
    out: list[tuple[Path, str]] = []
    seen: set[Path] = set()
    for g in globs:
        for p in root.glob(g):
            if not p.is_file() or _is_excluded(p) or p in seen:
                continue
            try:
                if since_ts is not None and p.stat().st_mtime <= since_ts:
                    seen.add(p)
                    continue
                out.append((p, annotate_file(p, root, kind)))
                seen.add(p)
            except OSError as e:
                print(f"  skip {p}: {e}", file=sys.stderr)
    return out


def _state_path(root: Path) -> Path:
    return root / ".kg" / INDEX_STATE_FILENAME


def _load_state(root: Path) -> dict | None:
    f = _state_path(root)
    if not f.is_file():
        return None
    try:
        return json.loads(f.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _write_state(root: Path, dataset: str, paths: list[Path]) -> None:
    now = time.time()
    state = {
        "dataset": dataset,
        "timestamp": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
        "timestamp_unix": now,
        "count": len(paths),
        "files": sorted(str(p.relative_to(root)) for p in paths),
    }
    p = _state_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")


def run(rebuild: bool = False, extra_globs: list[str] | None = None) -> int:
    ctx = resolve_context()
    print(f"[wikiforge index] root={ctx.root} dataset={ctx.dataset_id}")
    if not ctx.has_kg and not (ctx.root / ".kgconfig").is_file():
        print("[wikiforge index] no .kg/ ni .kgconfig encontrados — corre `wikiforge init` primero.", file=sys.stderr)
        return 1

    if rebuild:
        print("[wikiforge index] --rebuild: prune_data + prune_system (DESTRUCTIVO)...")
        run_prune()

    state = _load_state(ctx.root) if not rebuild else None
    since_ts = float(state.get("timestamp_unix") or 0) if state else None

    code_pairs = _collect(ctx.root, DEFAULT_CODE_GLOBS, "code", since_ts=since_ts)
    doc_pairs = _collect(ctx.root, DEFAULT_DOC_GLOBS, "doc", since_ts=since_ts)
    extra_pairs = _collect(ctx.root, list(extra_globs or []), "extra", since_ts=since_ts) if extra_globs else []

    pairs = code_pairs + doc_pairs + extra_pairs
    inputs = [text for _, text in pairs]
    paths_processed = [p for p, _ in pairs]

    if state and not pairs:
        print(f"[wikiforge index] al día — sin cambios desde {state.get('timestamp')}")
        # Re-escribimos state para refrescar el conteo total (si cambió por nuevos archivos no-modificados).
        # Para eso necesitamos el snapshot completo de paths actuales:
        all_paths = (
            [p for p, _ in _collect(ctx.root, DEFAULT_CODE_GLOBS, "code")]
            + [p for p, _ in _collect(ctx.root, DEFAULT_DOC_GLOBS, "doc")]
        )
        _write_state(ctx.root, ctx.dataset_id, all_paths)
        return 0

    if not inputs and not state:
        print("[wikiforge index] FATAL: no inputs collected", file=sys.stderr)
        return 1

    print(
        f"[wikiforge index] collected {len(code_pairs)} code + {len(doc_pairs)} doc "
        f"+ {len(extra_pairs)} extra = {len(inputs)} total"
        + (f" (incremental desde {state.get('timestamp')})" if state else "")
    )
    print(f"[wikiforge index] adding to dataset {ctx.dataset_id}...")
    run_add(inputs, ctx.dataset_id)

    print("[wikiforge index] cognifying (esto invoca el LLM, puede tardar varios minutos)...")
    run_cognify(ctx.dataset_id)

    # State con TODOS los paths actuales del repo, no solo los modificados.
    all_paths = (
        [p for p, _ in _collect(ctx.root, DEFAULT_CODE_GLOBS, "code")]
        + [p for p, _ in _collect(ctx.root, DEFAULT_DOC_GLOBS, "doc")]
    )
    _write_state(ctx.root, ctx.dataset_id, all_paths)
    print(f"[wikiforge index] done. state escrito en {_state_path(ctx.root)}.")
    return 0
