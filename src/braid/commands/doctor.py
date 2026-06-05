"""`braid doctor`: local diagnostics for Braid installations."""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .. import paths as paths_module
from . import agent as agent_cmd


@dataclass
class DoctorCheck:
    name: str
    status: str
    severity: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    fixed: bool = False

    @property
    def ok(self) -> bool:
        return self.severity == "info"


def _check(
    name: str,
    status: str,
    severity: str,
    message: str,
    details: dict[str, Any] | None = None,
    fixed: bool = False,
) -> DoctorCheck:
    return DoctorCheck(
        name=name,
        status=status,
        severity=severity,
        message=message,
        details=details or {},
        fixed=fixed,
    )


def _required_project_dirs(ctx: paths_module.ProjectContext) -> list[Path]:
    return [
        ctx.braid_dir,
        ctx.kg_dir,
        ctx.rag_dir,
        ctx.memory_dir,
        ctx.memory_dir / "decisions",
        ctx.memory_dir / "plans",
        ctx.memory_dir / "eval",
        ctx.memory_dir / "eval" / "runs",
        ctx.wiki_dir,
    ]


def _check_context() -> tuple[paths_module.ProjectContext, DoctorCheck]:
    ctx = paths_module.resolve_context()
    if ctx.global_profile:
        return ctx, _check(
            "context",
            "ok",
            "info",
            "resolved global profile context",
            {"root": str(ctx.root), "dataset_id": ctx.dataset_id},
        )
    return ctx, _check(
        "context",
        "ok",
        "info",
        "resolved active project context",
        {"root": str(ctx.root), "dataset_id": ctx.dataset_id},
    )


def _check_project_state(ctx: paths_module.ProjectContext, fix: bool) -> DoctorCheck:
    if ctx.global_profile:
        return _check("project_state", "ok", "info", "global profile context; no project state required")
    if not ctx.has_config:
        return _check(
            "project_state",
            "warning",
            "warning",
            "project is not initialized; run `braid init`",
            {"root": str(ctx.root), "config_path": str(paths_module.config_path(ctx.root))},
        )

    missing = [path for path in _required_project_dirs(ctx) if not path.exists()]
    if missing and fix:
        for path in missing:
            path.mkdir(parents=True, exist_ok=True)
        return _check(
            "project_state",
            "ok",
            "info",
            "created missing .braid directories",
            {"created": [str(path) for path in missing]},
            fixed=True,
        )
    if missing:
        return _check(
            "project_state",
            "warning",
            "warning",
            "project config exists but expected .braid directories are missing",
            {"missing": [str(path) for path in missing]},
        )
    return _check("project_state", "ok", "info", "project .braid layout is present")


def _check_global_profile() -> DoctorCheck:
    profile = paths_module.PROFILE_DIR
    if profile.is_dir():
        return _check("global_profile", "ok", "info", "global profile directory exists", {"path": str(profile)})
    return _check(
        "global_profile",
        "warning",
        "warning",
        "global profile directory is missing",
        {"path": str(profile)},
    )


def _check_cognee_backend() -> DoctorCheck:
    backend = paths_module.BRAID_HOME / "cognee"
    if backend.is_dir():
        return _check("cognee_backend", "ok", "info", "shared Cognee backend exists", {"path": str(backend)})
    return _check(
        "cognee_backend",
        "warning",
        "warning",
        "shared Cognee backend directory is missing",
        {"path": str(backend)},
    )


def _check_legacy_drift(ctx: paths_module.ProjectContext) -> DoctorCheck:
    if ctx.global_profile:
        return _check("legacy_drift", "ok", "info", "global profile context; no project legacy scan")
    legacy = [name for name in (".kg", ".rag", ".memory", ".kgconfig") if (ctx.root / name).exists()]
    if legacy:
        return _check(
            "legacy_drift",
            "warning",
            "warning",
            "legacy Braid/WikiForge layout exists in the active project boundary",
            {"paths": [str(ctx.root / name) for name in legacy]},
        )
    return _check("legacy_drift", "ok", "info", "no legacy project-local layout found")


def _check_agents(ctx: paths_module.ProjectContext, fix: bool) -> DoctorCheck:
    root = ctx.root if not ctx.global_profile else Path.cwd().resolve()
    mode: agent_cmd.Mode = "apply" if fix else "check"
    results = [agent_cmd._run_one(name, root, mode) for name in agent_cmd.AGENTS]
    errors = [result for result in results if result.status == "error"]
    drift = [result for result in results if result.drift and result.status != "error"]
    changed = [result for result in results if result.changed]
    details = {"agents": [asdict(result) for result in results]}
    if errors:
        return _check("agents", "error", "error", "agent config contains invalid JSON", details)
    if drift:
        return _check("agents", "warning", "warning", "agent integration drift detected", details)
    if changed:
        return _check("agents", "ok", "info", "agent integration drift fixed", details, fixed=True)
    return _check("agents", "ok", "info", "agent integrations are configured", details)


def _check_secrets() -> DoctorCheck:
    path = paths_module.secrets_path()
    if path.is_file():
        return _check("secrets", "ok", "info", "secrets file exists", {"path": str(path)})
    return _check(
        "secrets",
        "warning",
        "warning",
        "secrets file is missing; cloud features may be unavailable",
        {"path": str(path)},
    )


def _check_git_remote(ctx: paths_module.ProjectContext) -> DoctorCheck:
    root = ctx.root if not ctx.global_profile else paths_module.find_git_root()
    if root is None:
        return _check("git_remote", "warning", "warning", "not inside a git repository")
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "remote", "-v"],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return _check("git_remote", "warning", "warning", "git is not available")
    remotes = proc.stdout.strip().splitlines()
    if not remotes:
        return _check("git_remote", "warning", "warning", "git repository has no remotes", {"root": str(root)})
    github = [line for line in remotes if "github.com" in line]
    if github:
        return _check("git_remote", "ok", "info", "GitHub remote is configured", {"remotes": github})
    return _check(
        "git_remote",
        "warning",
        "warning",
        "git remotes exist, but none point to GitHub",
        {"remotes": remotes},
    )


def _ducklake_summary() -> dict | None:
    try:
        from ..ducklake import BraidCatalog
    except ImportError:
        return None
    with BraidCatalog() as cat:
        return cat.get_catalog_summary()


def _check_ducklake() -> DoctorCheck:
    try:
        summary = _ducklake_summary()
    except ImportError:
        return _check("ducklake", "warning", "warning", "DuckLake dependencies are not installed")
    except Exception as exc:
        return _check(
            "ducklake",
            "warning",
            "warning",
            "DuckLake catalog could not be opened",
            {"error": f"{type(exc).__name__}: {exc}"},
        )
    if summary is None:
        return _check("ducklake", "warning", "warning", "DuckLake dependencies are not installed")
    return _check("ducklake", "ok", "info", "DuckLake catalog is accessible", {"summary": summary})


def build_doctor_payload(fix: bool = False) -> dict:
    ctx, context_check = _check_context()
    checks = [
        context_check,
        _check_project_state(ctx, fix=fix),
        _check_global_profile(),
        _check_cognee_backend(),
        _check_legacy_drift(ctx),
        _check_agents(ctx, fix=fix),
        _check_secrets(),
        _check_git_remote(ctx),
        _check_ducklake(),
    ]
    ok = all(check.ok for check in checks)
    return {
        "ok": ok,
        "fixed": any(check.fixed for check in checks),
        "root": str(ctx.root),
        "dataset_id": ctx.dataset_id,
        "mode": "fix" if fix else "check",
        "checks": [asdict(check) for check in checks],
    }


def _print_human(payload: dict) -> None:
    print(f"[braid doctor] root={payload['root']} dataset={payload['dataset_id']} mode={payload['mode']}")
    for check in payload["checks"]:
        marker = "x" if check["severity"] == "error" else "!" if check["severity"] == "warning" else "."
        suffix = " (fixed)" if check.get("fixed") else ""
        print(f"  {marker} {check['name']}: {check['message']}{suffix}")


def run(as_json: bool = False, fix: bool = False) -> int:
    payload = build_doctor_payload(fix=fix)
    if as_json:
        sys.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n")
    else:
        _print_human(payload)
    return 0 if payload["ok"] else 1
