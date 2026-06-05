"""Tests for `braid agent-init` universal agent activation."""
from __future__ import annotations

import json
from pathlib import Path

from braid.cli import main as cli_main
from braid.commands import agent as agent_cmd
from braid.commands import claude as claude_cmd


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    (root / ".git").mkdir()
    (root / "AGENTS.md").write_text("# Project instructions\n")
    return root


def _legacy_settings() -> dict:
    return {
        "hooks": {
            "SessionStart": [
                {
                    "matcher": "startup|resume|clear|compact",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "wikiforge claude-session-start",
                            "timeout": 5,
                            "statusMessage": "Cargando memoria WikiForge...",
                        }
                    ],
                }
            ],
        },
        "mcpServers": {
            "fairlead": {"command": "fairlead", "args": ["mcp-serve"]},
        },
    }


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def test_check_detects_legacy_claude_without_writing(tmp_path: Path, monkeypatch, capsys):
    root = _project(tmp_path)
    settings_path = root / ".claude" / "settings.json"
    _write_json(settings_path, _legacy_settings())
    before = settings_path.read_text()

    monkeypatch.chdir(root)
    assert agent_cmd.run(agent="claude", check=True, as_json=True) == 1

    assert settings_path.read_text() == before
    payload = json.loads(capsys.readouterr().out)
    result = payload["agents"][0]
    assert result["agent"] == "claude"
    assert "legacy_hook" in result["drift"]
    assert "legacy_mcp" in result["drift"]


def test_fix_migrates_legacy_hooks_and_creates_discovery_symlinks(tmp_path: Path, monkeypatch):
    root = _project(tmp_path)
    _write_json(root / ".claude" / "settings.json", _legacy_settings())
    _write_json(root / ".codex" / "hooks.json", {"hooks": _legacy_settings()["hooks"]})

    monkeypatch.chdir(root)
    assert agent_cmd.run(agent="all", fix=True) == 0

    claude = _read_json(root / ".claude" / "settings.json")
    command = claude["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    assert command == "braid claude-session-start"
    assert claude["mcpServers"] == {"braid": {"command": "braid", "args": ["mcp-serve"]}}
    assert "wikiforge" not in json.dumps(claude)
    assert "fairlead" not in json.dumps(claude)

    codex = _read_json(root / ".codex" / "hooks.json")
    assert codex["hooks"]["SessionStart"][0]["hooks"][0]["command"] == "braid claude-session-start"
    assert "wikiforge" not in json.dumps(codex)

    assert (root / ".cursor" / "rules" / "main.mdc").is_symlink()
    assert (root / ".cursor" / "rules" / "main.mdc").readlink() == Path("../../AGENTS.md")
    assert (root / ".github" / "copilot-instructions.md").is_symlink()
    assert (root / ".github" / "copilot-instructions.md").readlink() == Path("../AGENTS.md")

    snapshot = {
        "claude": (root / ".claude" / "settings.json").read_text(),
        "codex": (root / ".codex" / "hooks.json").read_text(),
    }
    assert agent_cmd.run(agent="all", fix=True) == 0
    assert (root / ".claude" / "settings.json").read_text() == snapshot["claude"]
    assert (root / ".codex" / "hooks.json").read_text() == snapshot["codex"]


def test_remove_preserves_unrelated_claude_settings(tmp_path: Path, monkeypatch):
    root = _project(tmp_path)
    settings = {
        "hooks": {
            "SessionStart": [
                {
                    "matcher": "startup",
                    "hooks": [{"type": "command", "command": "echo keep"}],
                },
                {
                    "matcher": "startup|resume|clear|compact",
                    "hooks": [{"type": "command", "command": "braid claude-session-start"}],
                },
            ]
        },
        "mcpServers": {
            "braid": {"command": "braid", "args": ["mcp-serve"]},
            "other": {"command": "other", "args": []},
        },
    }
    _write_json(root / ".claude" / "settings.json", settings)

    monkeypatch.chdir(root)
    assert agent_cmd.run(agent="claude", remove=True) == 0

    updated = _read_json(root / ".claude" / "settings.json")
    assert updated["hooks"]["SessionStart"] == [
        {"matcher": "startup", "hooks": [{"type": "command", "command": "echo keep"}]}
    ]
    assert updated["mcpServers"] == {"other": {"command": "other", "args": []}}


def test_agent_init_uses_child_project_boundary(tmp_path: Path, monkeypatch):
    container = tmp_path / "Developer"
    child = container / "stock-pattern-classifier-orchestrator"
    child.mkdir(parents=True)
    (container / ".git").mkdir()
    (container / "AGENTS.md").write_text("# Parent\n")
    (child / "requirements.txt").write_text("pytest\n")
    (child / "AGENTS.md").write_text("# Child\n")

    monkeypatch.chdir(child)
    assert agent_cmd.run(agent="codex", fix=True) == 0

    assert (child / ".codex" / "hooks.json").is_file()
    assert not (container / ".codex").exists()


def test_claude_init_delegates_to_agent_init(tmp_path: Path, monkeypatch):
    root = _project(tmp_path)
    monkeypatch.chdir(root)

    assert claude_cmd.run_init() == 0

    settings = _read_json(root / ".claude" / "settings.json")
    assert settings["hooks"]["SessionStart"][0]["hooks"][0]["command"] == "braid claude-session-start"
    assert settings["mcpServers"] == {"braid": {"command": "braid", "args": ["mcp-serve"]}}


def test_cli_agent_init_json(tmp_path: Path, monkeypatch, capsys):
    root = _project(tmp_path)
    monkeypatch.chdir(root)

    assert cli_main(["agent-init", "--agent", "cursor", "--fix", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["agents"][0]["agent"] == "cursor"
    assert (root / ".cursor" / "rules" / "main.mdc").is_symlink()
