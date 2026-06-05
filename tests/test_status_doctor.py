"""Tests for status JSON and doctor diagnostics."""
from __future__ import annotations

import json
from pathlib import Path

from braid import paths as paths_module
from braid.commands import doctor as doctor_cmd
from braid.commands import status as status_cmd


def _initialized_project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    (root / ".git").mkdir()
    (root / "AGENTS.md").write_text("# Project\n")
    (root / ".braid" / "config.toml").parent.mkdir(parents=True)
    (root / ".braid" / "config.toml").write_text('dataset_id = "project"\n')
    for rel in [
        ".braid/kg",
        ".braid/rag",
        ".braid/memory/decisions",
        ".braid/memory/plans",
        ".braid/memory/eval/runs",
        ".braid/wiki",
    ]:
        (root / rel).mkdir(parents=True, exist_ok=True)
    claude = {
        "hooks": {
            "SessionStart": [
                {
                    "matcher": "startup|resume|clear|compact",
                    "hooks": [{"type": "command", "command": "braid claude-session-start"}],
                }
            ]
        },
        "mcpServers": {"braid": {"command": "braid", "args": ["mcp-serve"]}},
    }
    codex = {"hooks": claude["hooks"]}
    (root / ".claude").mkdir()
    (root / ".claude" / "settings.json").write_text(json.dumps(claude) + "\n")
    (root / ".codex").mkdir()
    (root / ".codex" / "hooks.json").write_text(json.dumps(codex) + "\n")
    (root / ".cursor" / "rules").mkdir(parents=True)
    (root / ".cursor" / "rules" / "main.mdc").symlink_to("../../AGENTS.md")
    (root / ".github").mkdir()
    (root / ".github" / "copilot-instructions.md").symlink_to("../AGENTS.md")
    return root


def _patch_external_ok(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "home"
    profile = home / ".braid" / "profile"
    cognee = home / ".braid" / "cognee"
    secrets = home / ".config" / "braid" / "secrets.env"
    profile.mkdir(parents=True)
    cognee.mkdir(parents=True)
    secrets.parent.mkdir(parents=True)
    secrets.write_text("OPENROUTER_API_KEY=test\n")

    monkeypatch.setattr(paths_module, "BRAID_HOME", home / ".braid")
    monkeypatch.setattr(paths_module, "PROFILE_DIR", profile)
    monkeypatch.setattr(status_cmd, "PROFILE_DIR", profile)
    monkeypatch.setattr(doctor_cmd.paths_module, "BRAID_HOME", home / ".braid")
    monkeypatch.setattr(doctor_cmd.paths_module, "PROFILE_DIR", profile)
    monkeypatch.setattr(doctor_cmd.paths_module, "secrets_path", lambda: secrets)
    monkeypatch.setattr(doctor_cmd, "_ducklake_summary", lambda: {"tables": 0, "total_rows": 0, "per_table": {}})
    monkeypatch.setattr(
        doctor_cmd,
        "_check_git_remote",
        lambda ctx: doctor_cmd._check("git_remote", "ok", "info", "GitHub remote is configured"),
    )


def test_status_json_project_payload(tmp_path: Path, monkeypatch, capsys):
    root = _initialized_project(tmp_path)
    monkeypatch.chdir(root)
    monkeypatch.setattr(status_cmd, "_ducklake_status", lambda: {"tables": 1, "total_rows": 2})

    assert status_cmd.run(as_json=True) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["root"] == str(root)
    assert payload["dataset_id"] == "project"
    assert payload["global_profile"] is False
    assert payload["state_dir"] == str(root / ".braid")
    assert payload["has_config"] is True
    assert payload["has_kg"] is True
    assert payload["legacy_layout"] is False
    assert payload["adr_count"] == 0
    assert payload["ducklake"]["tables"] == 1


def test_status_json_global_payload(tmp_path: Path, monkeypatch, capsys):
    scratch = tmp_path / "scratch"
    home = tmp_path / "home"
    scratch.mkdir()
    (home / ".braid" / "profile" / "kg").mkdir(parents=True)
    (home / ".braid" / "profile" / "config.toml").write_text('dataset_id = "_global_profile"\n')

    monkeypatch.chdir(scratch)
    monkeypatch.setattr(paths_module, "BRAID_HOME", home / ".braid")
    monkeypatch.setattr(paths_module, "PROFILE_DIR", home / ".braid" / "profile")
    monkeypatch.setattr(status_cmd, "PROFILE_DIR", home / ".braid" / "profile")
    monkeypatch.setattr(status_cmd, "_ducklake_status", lambda: None)

    assert status_cmd.run(as_json=True) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["global_profile"] is True
    assert payload["dataset_id"] == "_global_profile"
    assert payload["state_dir"] == str(home / ".braid" / "profile")
    assert payload["global_profile_exists"] is True


def test_doctor_json_reports_ok_checks(tmp_path: Path, monkeypatch, capsys):
    root = _initialized_project(tmp_path)
    _patch_external_ok(monkeypatch, tmp_path)
    monkeypatch.chdir(root)

    assert doctor_cmd.run(as_json=True) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["mode"] == "check"
    assert {check["name"] for check in payload["checks"]} >= {
        "context",
        "project_state",
        "agents",
        "ducklake",
    }


def test_doctor_fix_repairs_safe_project_and_agent_drift(tmp_path: Path, monkeypatch, capsys):
    root = tmp_path / "project"
    root.mkdir()
    (root / ".git").mkdir()
    (root / "AGENTS.md").write_text("# Project\n")
    (root / ".braid").mkdir()
    (root / ".braid" / "config.toml").write_text('dataset_id = "project"\n')
    _patch_external_ok(monkeypatch, tmp_path)
    monkeypatch.chdir(root)

    assert doctor_cmd.run(as_json=True, fix=True) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["fixed"] is True
    assert (root / ".braid" / "kg").is_dir()
    assert (root / ".codex" / "hooks.json").is_file()
    assert (root / ".cursor" / "rules" / "main.mdc").is_symlink()


def test_doctor_reports_invalid_agent_json(tmp_path: Path, monkeypatch, capsys):
    root = _initialized_project(tmp_path)
    (root / ".codex" / "hooks.json").write_text("{bad json\n")
    _patch_external_ok(monkeypatch, tmp_path)
    monkeypatch.chdir(root)

    assert doctor_cmd.run(as_json=True) == 1

    payload = json.loads(capsys.readouterr().out)
    agents = next(check for check in payload["checks"] if check["name"] == "agents")
    assert agents["severity"] == "error"
    assert "invalid JSON" in agents["message"]
