"""`braid claude-session-start` y `braid claude-init`.

Pieza ADR 0009. El primero reporta estado de memoria del repo activo en <500 ms
sin tocar el LLM ni cognee. El segundo cablea el hook SessionStart en
.claude/settings.json del git root, idempotente.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from ..paths import config_path, find_git_root, project_state_dir


# Espejo de los globs canónicos definidos en commands/index.py — fuente única
# de verdad de "qué se considera input del repo". Si cambian allí, cambian aquí.
DEFAULT_CODE_GLOBS = ["src/**/*.py", "**/*.py"]
DEFAULT_DOC_GLOBS = [
    "README.md",
    "MEMORY.md",
    "AGENTS.md",
    "CLAUDE.md",
    "docs/**/*.md",
    ".braid/memory/**/*.md",
]
EXCLUDE_PARTS = {"_backup", "output", "__pycache__", ".venv", ".git", "build", "kg", "rag", "wiki", "sessions"}

INDEX_STATE_FILENAME = "last_index.json"

HOOK_COMMAND = "braid claude-session-start"
HOOK_MARKER = "braid claude-session-start"  # substring usado para localizar la entrada al --remove
LEGACY_HOOK_MARKERS = ("fairlead claude-session-start", "wikiforge claude-session-start")


def _is_excluded(p: Path) -> bool:
    if ".braid" in set(p.parts) and (set(p.parts) & {"kg", "rag", "wiki", "sessions"}):
        return True
    return bool(set(p.parts) & EXCLUDE_PARTS)


def _collect(root: Path, globs: list[str]) -> list[Path]:
    seen: set[Path] = set()
    out: list[Path] = []
    for g in globs:
        for p in root.glob(g):
            if not p.is_file() or _is_excluded(p) or p in seen:
                continue
            seen.add(p)
            out.append(p)
    return out


def _load_index_state(kg_dir: Path) -> dict | None:
    f = kg_dir / INDEX_STATE_FILENAME
    if not f.is_file():
        return None
    try:
        return json.loads(f.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _count_adrs(memory_dir: Path) -> int:
    decisions = memory_dir / "decisions"
    if not decisions.is_dir():
        return 0
    return sum(1 for _ in decisions.glob("[0-9]*-*.md"))


def _stale_files(root: Path, last_ts: float) -> list[Path]:
    files = _collect(root, DEFAULT_CODE_GLOBS) + _collect(root, DEFAULT_DOC_GLOBS)
    out = []
    for p in files:
        try:
            if p.stat().st_mtime > last_ts:
                out.append(p)
        except OSError:
            continue
    return out


def _emit(report: dict, as_json: bool, message: str | None) -> int:
    if as_json:
        sys.stdout.write(json.dumps(report))
        sys.stdout.write("\n")
    elif message:
        sys.stdout.write(message)
        sys.stdout.write("\n")
    return 0


def run_session_start(as_json: bool = False) -> int:
    """ADR 0009 sec. 1. Lee filesystem, reporta estado en una línea. NO toca LLM."""
    root = find_git_root()
    if root is None:
        report = {"status": "no_repo", "root": str(Path.cwd())}
        return _emit(report, as_json, message=None)

    state_dir = project_state_dir(root)
    kg_dir = state_dir / "kg"
    memory_dir = state_dir / "memory"
    if not state_dir.is_dir() or not config_path(root).is_file():
        report = {"status": "uninitialized", "root": str(root)}
        msg = "[Braid] repo no inicializado · ejecuta 'braid init && braid index'"
        return _emit(report, as_json, msg)

    state = _load_index_state(kg_dir)
    n_adrs = _count_adrs(memory_dir)

    if state is None or "timestamp" not in state:
        report = {"status": "indexed_pending", "root": str(root), "nadrs": n_adrs}
        msg = "[Braid] repo inicializado pero no indexado · ejecuta 'braid index'"
        return _emit(report, as_json, msg)

    last_ts = float(state.get("timestamp_unix") or 0)
    n_inputs = int(state.get("count") or 0)
    stale = _stale_files(root, last_ts) if last_ts > 0 else []

    if not stale:
        report = {
            "status": "ready",
            "root": str(root),
            "ndocs": n_inputs,
            "nadrs": n_adrs,
            "stale_count": 0,
        }
        msg = f"[Braid] memoria al día ({n_inputs} inputs · {n_adrs} ADRs)"
        return _emit(report, as_json, msg)

    n_stale = len(stale)
    plural = "archivo modificado" if n_stale == 1 else "archivos modificados"
    report = {
        "status": "stale",
        "root": str(root),
        "ndocs": n_inputs,
        "nadrs": n_adrs,
        "stale_count": n_stale,
    }
    msg = f"[Braid] memoria stale ({n_stale} {plural} · ejecuta 'braid sync')"
    return _emit(report, as_json, msg)


# ---------------------------------------------------------------------------
# claude-init: cablea el hook SessionStart en <git_root>/.claude/settings.json
# ---------------------------------------------------------------------------


def _settings_path(root: Path) -> Path:
    return root / ".claude" / "settings.json"


def _load_settings(p: Path) -> dict:
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text()) or {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_settings(p: Path, data: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def _hook_entry() -> dict:
    """Estructura del hook según docs oficiales Claude Code (code.claude.com/docs/en/hooks).

    SessionStart admite `matcher` (startup|resume|clear|compact) — usamos los cuatro
    para que Claude reciba el estado de Braid tras cualquier transición.
    `timeout` en segundos: el comando p50 = 250 ms, ponemos 5 s por seguridad
    (default 600 s sería absurdo bloquear la sesión).
    `statusMessage` se muestra al usuario durante la ejecución del hook.
    """
    return {
        "matcher": "startup|resume|clear|compact",
        "hooks": [
            {
                "type": "command",
                "command": HOOK_COMMAND,
                "timeout": 5,
                "statusMessage": "Cargando memoria Braid...",
            }
        ],
    }


def _has_braid_hook(events: list[dict]) -> bool:
    for evt in events:
        for hook in evt.get("hooks", []) or []:
            command = hook.get("command") or ""
            if HOOK_MARKER in command or any(marker in command for marker in LEGACY_HOOK_MARKERS):
                return True
    return False


def _strip_braid_hook(events: list[dict]) -> list[dict]:
    cleaned = []
    for evt in events:
        new_hooks = []
        for hook in evt.get("hooks") or []:
            command = hook.get("command") or ""
            if HOOK_MARKER in command or any(marker in command for marker in LEGACY_HOOK_MARKERS):
                continue
            new_hooks.append(hook)
        if new_hooks:
            cleaned.append({**evt, "hooks": new_hooks})
        # si el evento queda sin hooks, lo descartamos
    return cleaned


def run_init(remove: bool = False) -> int:
    """Compatibility wrapper for ADR 0009; implementation lives in agent-init."""
    from . import agent as agent_cmd

    return agent_cmd.run(agent="claude", remove=remove)
