"""braid patterns: read-only operational playbook for Braid."""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from typing import Any

from . import doctor as doctor_cmd


@dataclass(frozen=True)
class OperationalPattern:
    id: str
    title: str
    summary: str
    commands: list[str]
    status: str
    evidence: dict[str, Any] = field(default_factory=dict)


def _check_by_name(doctor_payload: dict[str, Any], name: str) -> dict[str, Any] | None:
    for check in doctor_payload.get("checks", []):
        if check.get("name") == name:
            return check
    return None


def _status_from_check(check: dict[str, Any] | None) -> str:
    if check is None:
        return "unknown"
    severity = check.get("severity")
    if severity == "info":
        return "ok"
    if severity == "error":
        return "error"
    return "warning"


def build_patterns_payload() -> dict[str, Any]:
    """Build a read-only pattern playbook payload."""

    doctor_payload = doctor_cmd.build_doctor_payload(fix=False)
    context = _check_by_name(doctor_payload, "context")
    agents = _check_by_name(doctor_payload, "agents")
    ducklake = _check_by_name(doctor_payload, "ducklake")
    warnings = [
        {
            "name": check.get("name"),
            "severity": check.get("severity"),
            "message": check.get("message"),
        }
        for check in doctor_payload.get("checks", [])
        if check.get("severity") != "info"
    ]

    patterns = [
        OperationalPattern(
            id="boundary",
            title="Nearest project boundary wins",
            summary="Resolve the active project before reading or writing memory.",
            commands=["braid status --json", "braid doctor"],
            status=_status_from_check(context),
            evidence={
                "root": doctor_payload.get("root"),
                "dataset_id": doctor_payload.get("dataset_id"),
                "context": (context or {}).get("message"),
            },
        ),
        OperationalPattern(
            id="diagnose",
            title="Diagnose before changing state",
            summary="Use doctor for health checks; this command explains the operating model.",
            commands=["braid doctor", "braid doctor --json", "braid doctor --fix"],
            status="ok" if doctor_payload.get("ok") else "warning",
            evidence={
                "doctor_ok": doctor_payload.get("ok"),
                "warnings": warnings,
            },
        ),
        OperationalPattern(
            id="activate",
            title="Repair managed agent drift explicitly",
            summary="Agent integration is managed with agent-init, preserving unrelated config.",
            commands=["braid agent-init --check --json", "braid agent-init --fix"],
            status=_status_from_check(agents),
            evidence={
                "agents": (agents or {}).get("message"),
                "details": (agents or {}).get("details", {}),
            },
        ),
        OperationalPattern(
            id="isolate",
            title="Keep runtime validation isolated",
            summary="DuckLake, FTS, and LanceDB validation should use temporary catalogs.",
            commands=["PYTHONPATH=src .venv/bin/python -m pytest -q"],
            status=_status_from_check(ducklake),
            evidence={
                "policy": "Tests use temporary DuckLake/FTS/LanceDB fixtures, not the live .braid/kg catalog.",
                "ducklake": (ducklake or {}).get("message"),
            },
        ),
        OperationalPattern(
            id="evaluate",
            title="Gate retrieval changes with evals",
            summary="Change KG/RAG behavior only after measurable braid eval evidence.",
            commands=["braid eval --no-save", "braid eval"],
            status="ok",
            evidence={
                "policy": "Retrieval, reranking, and KG/RAG changes require eval evidence before architecture changes.",
            },
        ),
    ]

    return {
        "root": doctor_payload.get("root"),
        "dataset_id": doctor_payload.get("dataset_id"),
        "doctor_ok": doctor_payload.get("ok"),
        "patterns": [asdict(pattern) for pattern in patterns],
    }


def _print_human(payload: dict[str, Any]) -> None:
    doctor_state = "ok" if payload.get("doctor_ok") else "warnings"
    print(
        f"[braid patterns] root={payload['root']} "
        f"dataset={payload['dataset_id']} doctor={doctor_state}"
    )
    for pattern in payload["patterns"]:
        marker = "x" if pattern["status"] == "error" else "!" if pattern["status"] == "warning" else "."
        print(f"  {marker} {pattern['id']}: {pattern['title']}")
        print(f"      {pattern['summary']}")
        if pattern["commands"]:
            print(f"      commands: {', '.join(pattern['commands'])}")
        evidence = pattern.get("evidence") or {}
        if evidence:
            summary = evidence.get("context") or evidence.get("agents") or evidence.get("ducklake") or evidence.get("policy")
            if summary:
                print(f"      evidence: {summary}")


def run(as_json: bool = False) -> int:
    payload = build_patterns_payload()
    if as_json:
        sys.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n")
    else:
        _print_human(payload)
    return 0
