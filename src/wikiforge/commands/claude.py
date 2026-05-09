"""`wikiforge claude-session-start` y `wikiforge claude-init`.

Pieza ADR 0009. El primero reporta estado de memoria del repo activo en <500 ms
sin tocar el LLM ni cognee. El segundo cablea el hook SessionStart en
.claude/settings.json del git root, idempotente.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from ..paths import find_git_root


# Espejo de los globs canónicos definidos en commands/index.py — fuente única
# de verdad de "qué se considera input del repo". Si cambian allí, cambian aquí.
DEFAULT_CODE_GLOBS = ["src/**/*.py", "**/*.py"]
DEFAULT_DOC_GLOBS = [
    "README.md",
    "MEMORY.md",
    "AGENTS.md",
    "CLAUDE.md",
    "docs/**/*.md",
    ".memory/**/*.md",
]
EXCLUDE_PARTS = {"_backup", "output", "__pycache__", ".venv", ".git", "build", ".kg", ".rag"}

INDEX_STATE_FILENAME = "last_index.json"

HOOK_COMMAND = "wikiforge claude-session-start"
HOOK_MARKER = "wikiforge claude-session-start"  # substring usado para localizar la entrada al --remove


def _is_excluded(p: Path) -> bool:
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

    kg_dir = root / ".kg"
    if not kg_dir.is_dir():
        report = {"status": "uninitialized", "root": str(root)}
        msg = "[WikiForge] repo no inicializado · ejecuta 'wikiforge init && wikiforge index'"
        return _emit(report, as_json, msg)

    state = _load_index_state(kg_dir)
    n_adrs = _count_adrs(root / ".memory")

    if state is None or "timestamp" not in state:
        report = {"status": "indexed_pending", "root": str(root), "nadrs": n_adrs}
        msg = "[WikiForge] repo inicializado pero no indexado · ejecuta 'wikiforge index'"
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
        msg = f"[WikiForge] memoria al día ({n_inputs} inputs · {n_adrs} ADRs)"
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
    msg = f"[WikiForge] memoria stale ({n_stale} {plural} · ejecuta 'wikiforge sync')"
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
    para que Claude reciba el estado de WikiForge tras cualquier transición.
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
                "statusMessage": "Cargando memoria WikiForge...",
            }
        ],
    }


def _has_wikiforge_hook(events: list[dict]) -> bool:
    for evt in events:
        for hook in evt.get("hooks", []) or []:
            if HOOK_MARKER in (hook.get("command") or ""):
                return True
    return False


def _strip_wikiforge_hook(events: list[dict]) -> list[dict]:
    cleaned = []
    for evt in events:
        new_hooks = [h for h in (evt.get("hooks") or []) if HOOK_MARKER not in (h.get("command") or "")]
        if new_hooks:
            cleaned.append({**evt, "hooks": new_hooks})
        # si el evento queda sin hooks, lo descartamos
    return cleaned


def run_init(remove: bool = False) -> int:
    """Cablea (o elimina) el hook SessionStart en <git_root>/.claude/settings.json."""
    root = find_git_root()
    if root is None:
        sys.stderr.write("[wikiforge claude-init] no estás dentro de un repo git\n")
        return 1

    target = _settings_path(root)
    settings = _load_settings(target)
    hooks = settings.setdefault("hooks", {})
    session_start = hooks.setdefault("SessionStart", [])

    if remove:
        if not _has_wikiforge_hook(session_start):
            print(f"[wikiforge claude-init] sin hook que retirar en {target}")
            return 0
        hooks["SessionStart"] = _strip_wikiforge_hook(session_start)
        if not hooks["SessionStart"]:
            del hooks["SessionStart"]
        if not hooks:
            del settings["hooks"]
        if settings:
            _save_settings(target, settings)
        elif target.is_file():
            target.unlink()
        print(f"[wikiforge claude-init] hook retirado de {target}")
        return 0

    if _has_wikiforge_hook(session_start):
        print(f"[wikiforge claude-init] hook ya presente en {target} — sin cambios")
        return 0

    session_start.append(_hook_entry())
    _save_settings(target, settings)
    print(f"[wikiforge claude-init] hook SessionStart añadido en {target}")
    print("  comando: " + HOOK_COMMAND)
    return 0
