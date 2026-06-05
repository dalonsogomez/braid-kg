"""`braid index`: ingest active-project code and docs into Cognee."""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from ..paths import ProjectContext, resolve_context
from ..runner import annotate_file, run_add, run_cognify, run_prune


DEFAULT_CODE_GLOBS = ["src/**/*.py", "**/*.py"]
DEFAULT_DOC_GLOBS = [
    "README.md",
    "MEMORY.md",
    "AGENTS.md",
    "CLAUDE.md",
    "docs/**/*.md",
    ".braid/memory/**/*.md",
]
EXCLUDE_PARTS = {
    "_backup",
    "output",
    "__pycache__",
    ".venv",
    ".git",
    "build",
}
INDEX_STATE_FILENAME = "last_index.json"


def _is_excluded(path: Path) -> bool:
    parts = set(path.parts)
    if ".braid" in parts and (parts & {"kg", "rag", "wiki", "sessions"}):
        return True
    if ".kg" in parts or ".rag" in parts:
        return True
    if ".memory" in parts and "sessions" in parts:
        return True
    return bool(parts & EXCLUDE_PARTS)


def _collect(
    root: Path, globs: list[str], kind: str, since_ts: float | None = None
) -> list[tuple[Path, str]]:
    out: list[tuple[Path, str]] = []
    seen: set[Path] = set()
    for glob in globs:
        for path in root.glob(glob):
            if not path.is_file() or _is_excluded(path) or path in seen:
                continue
            try:
                if since_ts is not None and path.stat().st_mtime <= since_ts:
                    seen.add(path)
                    continue
                out.append((path, annotate_file(path, root, kind)))
                seen.add(path)
            except OSError as exc:
                print(f"  skip {path}: {exc}", file=sys.stderr)
    return out


def _state_path(ctx: ProjectContext) -> Path:
    return ctx.kg_dir / INDEX_STATE_FILENAME


def _load_state(ctx: ProjectContext) -> dict | None:
    path = _state_path(ctx)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _write_state(ctx: ProjectContext, paths: list[Path]) -> None:
    now = time.time()
    state = {
        "dataset": ctx.dataset_id,
        "timestamp": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
        "timestamp_unix": now,
        "count": len(paths),
        "files": sorted(str(path.relative_to(ctx.root)) for path in paths),
    }
    path = _state_path(ctx)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")


def run(rebuild: bool = False, extra_globs: list[str] | None = None) -> int:
    ctx = resolve_context()
    print(f"[braid index] root={ctx.root} dataset={ctx.dataset_id}")
    if not ctx.has_config and not ctx.kg_dir.is_dir():
        print(
            "[braid index] no .braid/config.toml ni .braid/kg encontrados - corre `braid init` primero.",
            file=sys.stderr,
        )
        return 1

    ctx.kg_dir.mkdir(parents=True, exist_ok=True)
    ctx.rag_dir.mkdir(parents=True, exist_ok=True)

    if rebuild:
        print("[braid index] --rebuild: prune_data + prune_system (DESTRUCTIVO)...")
        run_prune()

    state = _load_state(ctx) if not rebuild else None
    since_ts = float(state.get("timestamp_unix") or 0) if state else None

    code_pairs = _collect(ctx.root, DEFAULT_CODE_GLOBS, "code", since_ts=since_ts)
    doc_pairs = _collect(ctx.root, DEFAULT_DOC_GLOBS, "doc", since_ts=since_ts)
    extra_pairs = _collect(ctx.root, list(extra_globs or []), "extra", since_ts=since_ts) if extra_globs else []

    pairs = code_pairs + doc_pairs + extra_pairs
    inputs = [text for _, text in pairs]

    if state and not pairs:
        print(f"[braid index] al dia - sin cambios desde {state.get('timestamp')}")
        all_paths = (
            [path for path, _ in _collect(ctx.root, DEFAULT_CODE_GLOBS, "code")]
            + [path for path, _ in _collect(ctx.root, DEFAULT_DOC_GLOBS, "doc")]
        )
        _write_state(ctx, all_paths)
        return 0

    if not inputs and not state:
        print("[braid index] FATAL: no inputs collected", file=sys.stderr)
        return 1

    print(
        f"[braid index] collected {len(code_pairs)} code + {len(doc_pairs)} doc "
        f"+ {len(extra_pairs)} extra = {len(inputs)} total"
        + (f" (incremental desde {state.get('timestamp')})" if state else "")
    )
    print(f"[braid index] adding to dataset {ctx.dataset_id}...")
    run_add(inputs, ctx.dataset_id)

    print("[braid index] cognifying (esto invoca el LLM, puede tardar varios minutos)...")
    run_cognify(ctx.dataset_id)

    all_paths = (
        [path for path, _ in _collect(ctx.root, DEFAULT_CODE_GLOBS, "code")]
        + [path for path, _ in _collect(ctx.root, DEFAULT_DOC_GLOBS, "doc")]
    )
    _write_state(ctx, all_paths)
    print(f"[braid index] done. state escrito en {_state_path(ctx)}.")
    return 0
