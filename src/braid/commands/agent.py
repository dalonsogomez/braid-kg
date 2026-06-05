"""`braid agent-init`: configure Braid for supported AI agents."""
from __future__ import annotations

import copy
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from ..paths import find_git_root, find_project_root

AgentName = Literal["claude", "codex", "cursor", "copilot"]
Mode = Literal["apply", "check", "remove"]

AGENTS: tuple[AgentName, ...] = ("claude", "codex", "cursor", "copilot")
HOOK_COMMAND = "braid claude-session-start"
LEGACY_HOOK_MARKERS = ("fairlead claude-session-start", "wikiforge claude-session-start")
CLAUDE_MCP = {"command": "braid", "args": ["mcp-serve"]}


@dataclass
class AgentInitResult:
    agent: str
    target: str
    status: str
    changed: bool = False
    drift: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status in {"ok", "changed", "removed"} and not self.drift


def _root() -> Path:
    return find_project_root() or find_git_root() or Path.cwd().resolve()


def _load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text()) or {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def _hook_entry() -> dict:
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


def _hook_command(hook: dict) -> str:
    return str(hook.get("command") or "")


def _is_canonical_hook(hook: dict) -> bool:
    return HOOK_COMMAND in _hook_command(hook)


def _is_legacy_hook(hook: dict) -> bool:
    command = _hook_command(hook)
    return any(marker in command for marker in LEGACY_HOOK_MARKERS)


def _is_braid_hook(hook: dict) -> bool:
    return _is_canonical_hook(hook) or _is_legacy_hook(hook)


def _session_start_events(settings: dict) -> list[dict]:
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return []
    events = hooks.get("SessionStart")
    return events if isinstance(events, list) else []


def _hook_drift(settings: dict) -> list[str]:
    events = _session_start_events(settings)
    canonical = False
    legacy = False
    for event in events:
        for hook in event.get("hooks", []) or []:
            canonical = canonical or _is_canonical_hook(hook)
            legacy = legacy or _is_legacy_hook(hook)
    drift: list[str] = []
    if legacy:
        drift.append("legacy_hook")
    if not canonical:
        drift.append("missing_hook")
    return drift


def _strip_braid_hooks(events: list[dict]) -> tuple[list[dict], int]:
    cleaned: list[dict] = []
    removed = 0
    for event in events:
        hooks = []
        for hook in event.get("hooks", []) or []:
            if _is_braid_hook(hook):
                removed += 1
                continue
            hooks.append(hook)
        if hooks:
            cleaned.append({**event, "hooks": hooks})
    return cleaned, removed


def _ensure_hook(settings: dict) -> tuple[dict, list[str]]:
    desired = copy.deepcopy(settings)
    hooks = desired.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        hooks = {}
        desired["hooks"] = hooks
    current = hooks.get("SessionStart")
    events = current if isinstance(current, list) else []
    cleaned, removed = _strip_braid_hooks(events)
    cleaned.append(_hook_entry())
    hooks["SessionStart"] = cleaned
    actions: list[str] = []
    if removed:
        actions.append("normalized_hook")
    if not any("normalized_hook" == action for action in actions):
        actions.append("ensured_hook")
    return desired, actions


def _remove_hook(settings: dict) -> tuple[dict, list[str]]:
    desired = copy.deepcopy(settings)
    hooks = desired.get("hooks")
    if not isinstance(hooks, dict):
        return desired, []
    events = hooks.get("SessionStart")
    if not isinstance(events, list):
        return desired, []
    cleaned, removed = _strip_braid_hooks(events)
    if cleaned:
        hooks["SessionStart"] = cleaned
    else:
        hooks.pop("SessionStart", None)
    if not hooks:
        desired.pop("hooks", None)
    return desired, ["removed_hook"] if removed else []


def _mcp_drift(settings: dict) -> list[str]:
    mcp = settings.get("mcpServers")
    if not isinstance(mcp, dict):
        return ["missing_mcp"]
    drift: list[str] = []
    if "fairlead" in mcp or "wikiforge" in mcp:
        drift.append("legacy_mcp")
    if mcp.get("braid") != CLAUDE_MCP:
        drift.append("missing_mcp")
    return drift


def _ensure_mcp(settings: dict) -> tuple[dict, list[str]]:
    desired = copy.deepcopy(settings)
    mcp = desired.setdefault("mcpServers", {})
    if not isinstance(mcp, dict):
        mcp = {}
        desired["mcpServers"] = mcp
    actions: list[str] = []
    for legacy_name in ("fairlead", "wikiforge"):
        if legacy_name in mcp:
            del mcp[legacy_name]
            actions.append(f"removed_{legacy_name}_mcp")
    if mcp.get("braid") != CLAUDE_MCP:
        mcp["braid"] = dict(CLAUDE_MCP)
        actions.append("ensured_mcp")
    return desired, actions


def _remove_mcp(settings: dict) -> tuple[dict, list[str]]:
    desired = copy.deepcopy(settings)
    mcp = desired.get("mcpServers")
    if not isinstance(mcp, dict):
        return desired, []
    actions: list[str] = []
    for name in ("braid", "fairlead", "wikiforge"):
        if name in mcp:
            del mcp[name]
            actions.append(f"removed_{name}_mcp")
    if not mcp:
        desired.pop("mcpServers", None)
    return desired, actions


def _json_agent(agent: AgentName, root: Path, path: Path, mode: Mode, include_mcp: bool) -> AgentInitResult:
    settings = _load_json(path)
    drift = _hook_drift(settings)
    if include_mcp:
        drift.extend(_mcp_drift(settings))

    if mode == "check":
        return AgentInitResult(
            agent=agent,
            target=str(path),
            status="drift" if drift else "ok",
            drift=drift,
        )

    desired = copy.deepcopy(settings)
    actions: list[str] = []
    if mode == "remove":
        desired, hook_actions = _remove_hook(desired)
        actions.extend(hook_actions)
        if include_mcp:
            desired, mcp_actions = _remove_mcp(desired)
            actions.extend(mcp_actions)
    else:
        desired, hook_actions = _ensure_hook(desired)
        actions.extend(hook_actions)
        if include_mcp:
            desired, mcp_actions = _ensure_mcp(desired)
            actions.extend(mcp_actions)

    changed = desired != settings
    if changed:
        if desired:
            _save_json(path, desired)
        elif path.is_file():
            path.unlink()

    status = "removed" if mode == "remove" and changed else "changed" if changed else "ok"
    return AgentInitResult(agent=agent, target=str(path), status=status, changed=changed, actions=actions)


def _symlink_drift(root: Path, path: Path, target: str) -> list[str]:
    target_path = root / "AGENTS.md"
    drift: list[str] = []
    if not target_path.is_file():
        drift.append("missing_agents_md")
    if not path.exists() and not path.is_symlink():
        drift.append("missing_symlink")
    elif not path.is_symlink():
        drift.append("not_symlink")
    elif path.readlink() != Path(target):
        drift.append("wrong_symlink_target")
    return drift


def _symlink_agent(agent: AgentName, root: Path, rel: str, target: str, mode: Mode) -> AgentInitResult:
    path = root / rel
    drift = _symlink_drift(root, path, target)
    if mode == "check":
        return AgentInitResult(agent=agent, target=str(path), status="drift" if drift else "ok", drift=drift)

    if mode == "remove":
        if path.is_symlink() and path.readlink() == Path(target):
            path.unlink()
            return AgentInitResult(agent=agent, target=str(path), status="removed", changed=True, actions=["removed_symlink"])
        return AgentInitResult(agent=agent, target=str(path), status="ok")

    if "missing_agents_md" in drift or "not_symlink" in drift:
        return AgentInitResult(agent=agent, target=str(path), status="drift", drift=drift)

    changed = False
    actions: list[str] = []
    if path.is_symlink() and path.readlink() != Path(target):
        path.unlink()
        changed = True
        actions.append("removed_wrong_symlink")
    if not path.exists() and not path.is_symlink():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to(target)
        changed = True
        actions.append("created_symlink")

    final_drift = _symlink_drift(root, path, target)
    if final_drift:
        return AgentInitResult(agent=agent, target=str(path), status="drift", changed=changed, drift=final_drift, actions=actions)
    return AgentInitResult(agent=agent, target=str(path), status="changed" if changed else "ok", changed=changed, actions=actions)


def _run_one(agent: AgentName, root: Path, mode: Mode) -> AgentInitResult:
    if agent == "claude":
        return _json_agent("claude", root, root / ".claude" / "settings.json", mode, include_mcp=True)
    if agent == "codex":
        return _json_agent("codex", root, root / ".codex" / "hooks.json", mode, include_mcp=False)
    if agent == "cursor":
        return _symlink_agent("cursor", root, ".cursor/rules/main.mdc", "../../AGENTS.md", mode)
    if agent == "copilot":
        return _symlink_agent("copilot", root, ".github/copilot-instructions.md", "../AGENTS.md", mode)
    raise ValueError(f"unsupported agent: {agent}")


def _selected(agent: str) -> tuple[AgentName, ...]:
    if agent == "all":
        return AGENTS
    if agent not in AGENTS:
        raise ValueError(f"unsupported agent: {agent}")
    return (agent,)  # type: ignore[return-value]


def _mode(check: bool, fix: bool, remove: bool) -> Mode:
    selected = [check, fix, remove]
    if sum(1 for item in selected if item) > 1:
        raise ValueError("--check, --fix and --remove are mutually exclusive")
    if check:
        return "check"
    if remove:
        return "remove"
    return "apply"


def _print_human(root: Path, mode: Mode, results: list[AgentInitResult]) -> None:
    print(f"[braid agent-init] root={root} mode={mode}")
    for result in results:
        marker = "!" if result.drift else "+" if result.changed else "."
        print(f"  {marker} {result.agent}: {result.status} {result.target}")
        for item in result.drift:
            print(f"      drift: {item}")
        for item in result.actions:
            print(f"      action: {item}")


def run(
    agent: str = "all",
    check: bool = False,
    fix: bool = False,
    remove: bool = False,
    as_json: bool = False,
) -> int:
    root = _root()
    mode = _mode(check=check, fix=fix, remove=remove)
    selected = _selected(agent)
    results = [_run_one(name, root, mode) for name in selected]
    ok = all(result.ok for result in results)
    payload = {
        "root": str(root),
        "mode": mode,
        "ok": ok,
        "changed": any(result.changed for result in results),
        "agents": [asdict(result) for result in results],
    }
    if as_json:
        sys.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    else:
        _print_human(root, mode, results)
    return 0 if ok else 1
