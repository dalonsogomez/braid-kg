"""Tests for the braid patterns operational playbook."""
from __future__ import annotations

import json
from typing import Any

from braid.cli import build_parser, main as cli_main
from braid.commands import patterns as patterns_cmd


def _doctor_payload(ok: bool = True) -> dict[str, Any]:
    ducklake = {
        "name": "ducklake",
        "status": "ok" if ok else "warning",
        "severity": "info" if ok else "warning",
        "message": "DuckLake catalog is accessible" if ok else "DuckLake catalog could not be opened",
        "details": {},
        "fixed": False,
    }
    return {
        "ok": ok,
        "fixed": False,
        "root": "/tmp/project",
        "dataset_id": "project",
        "mode": "check",
        "checks": [
            {
                "name": "context",
                "status": "ok",
                "severity": "info",
                "message": "resolved active project context",
                "details": {"root": "/tmp/project", "dataset_id": "project"},
                "fixed": False,
            },
            {
                "name": "agents",
                "status": "ok",
                "severity": "info",
                "message": "agent integrations are configured",
                "details": {"agents": []},
                "fixed": False,
            },
            ducklake,
        ],
    }


def test_patterns_human_output_lists_all_patterns_and_commands(monkeypatch, capsys):
    monkeypatch.setattr(patterns_cmd.doctor_cmd, "build_doctor_payload", lambda fix=False: _doctor_payload())

    assert patterns_cmd.run(as_json=False) == 0

    out = capsys.readouterr().out
    for pattern_id in ("boundary", "diagnose", "activate", "isolate", "evaluate"):
        assert pattern_id in out
    assert "braid status --json" in out
    assert "braid doctor --json" in out
    assert "braid agent-init --fix" in out
    assert "braid eval --no-save" in out


def test_patterns_json_has_stable_ids(monkeypatch, capsys):
    monkeypatch.setattr(patterns_cmd.doctor_cmd, "build_doctor_payload", lambda fix=False: _doctor_payload())

    assert patterns_cmd.run(as_json=True) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["root"] == "/tmp/project"
    assert payload["dataset_id"] == "project"
    assert payload["doctor_ok"] is True
    assert [item["id"] for item in payload["patterns"]] == [
        "boundary",
        "diagnose",
        "activate",
        "isolate",
        "evaluate",
    ]
    for item in payload["patterns"]:
        assert {"id", "title", "summary", "commands", "status", "evidence"} <= set(item)


def test_patterns_never_calls_doctor_fix(monkeypatch, capsys):
    def fake_doctor_payload(fix: bool = False) -> dict[str, Any]:
        assert fix is False
        return _doctor_payload()

    monkeypatch.setattr(patterns_cmd.doctor_cmd, "build_doctor_payload", fake_doctor_payload)

    assert cli_main(["patterns", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["doctor_ok"] is True


def test_patterns_reports_doctor_warnings_without_failing(monkeypatch, capsys):
    monkeypatch.setattr(patterns_cmd.doctor_cmd, "build_doctor_payload", lambda fix=False: _doctor_payload(ok=False))

    assert cli_main(["patterns", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["doctor_ok"] is False
    by_id = {item["id"]: item for item in payload["patterns"]}
    assert by_id["diagnose"]["status"] == "warning"
    assert by_id["isolate"]["status"] == "warning"
    assert by_id["diagnose"]["evidence"]["warnings"][0]["name"] == "ducklake"


def test_cli_help_includes_patterns_command():
    help_text = build_parser().format_help()
    assert "patterns" in help_text
