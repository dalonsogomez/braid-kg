"""Project and profile path resolution for Braid.

Canonical project state lives under .braid/. The old scattered layout
(.kg/, .rag/, .memory/ and .kgconfig) is read only as a legacy migration
source; new writes go through this module and target .braid/*.
"""
from __future__ import annotations

import os
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path

BRAID_DIRNAME = ".braid"
CONFIG_FILENAME = "config.toml"
LEGACY_CONFIG_FILENAME = ".kgconfig"

BRAID_HOME = Path.home() / ".braid"
PROFILE_DIR = BRAID_HOME / "profile"
GLOBAL_DATASET_ID = "_global_profile"


@dataclass(frozen=True)
class ProjectContext:
    """Minimal active-project information used by commands and MCP tools."""

    root: Path
    dataset_id: str
    has_kg: bool
    kgconfig: dict
    fallback_threshold: float = 0.55
    config_path: Path | None = None
    legacy_layout: bool = False

    @property
    def braid_dir(self) -> Path:
        return self.root / BRAID_DIRNAME

    @property
    def memory_dir(self) -> Path:
        return self.braid_dir / "memory"

    @property
    def kg_dir(self) -> Path:
        return self.braid_dir / "kg"

    @property
    def rag_dir(self) -> Path:
        return self.braid_dir / "rag"

    @property
    def wiki_dir(self) -> Path:
        return self.braid_dir / "wiki"

    @property
    def has_config(self) -> bool:
        return bool(self.config_path and self.config_path.is_file())


def project_state_dir(root: Path) -> Path:
    return root / BRAID_DIRNAME


def config_path(root: Path) -> Path:
    return project_state_dir(root) / CONFIG_FILENAME


def legacy_config_path(root: Path) -> Path:
    return root / LEGACY_CONFIG_FILENAME


def find_git_root(start: Path | None = None) -> Path | None:
    """Return the containing git root for start or None outside git."""

    start = (start or Path.cwd()).resolve()
    try:
        out = subprocess.check_output(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return Path(out)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def find_braid_root(start: Path | None = None) -> Path | None:
    """Walk upward looking for canonical Braid state or the legacy layout."""

    cur = (start or Path.cwd()).resolve()
    while cur != cur.parent:
        if config_path(cur).is_file() or project_state_dir(cur).is_dir():
            return cur
        if legacy_config_path(cur).is_file() or (cur / ".kg").is_dir():
            return cur
        cur = cur.parent
    return None


def find_kg_root(start: Path | None = None) -> Path | None:
    """Compatibility alias for older callers."""

    return find_braid_root(start)


def load_kgconfig(root: Path) -> dict:
    """Load canonical .braid/config.toml or legacy .kgconfig."""

    for cfg in (config_path(root), legacy_config_path(root)):
        if cfg.is_file():
            return tomllib.loads(cfg.read_text())
    return {}


def _context_from_root(
    root: Path, cfg: dict, cfg_path: Path | None, legacy_layout: bool
) -> ProjectContext:
    braid_kg = project_state_dir(root) / "kg"
    legacy_kg = root / ".kg"
    has_kg = braid_kg.is_dir() or (legacy_layout and legacy_kg.is_dir())
    return ProjectContext(
        root=root,
        dataset_id=cfg.get("dataset_id") or root.name,
        has_kg=has_kg,
        kgconfig=cfg,
        fallback_threshold=float(cfg.get("fallback_threshold", 0.55)),
        config_path=cfg_path,
        legacy_layout=legacy_layout,
    )


def resolve_context(start: Path | None = None) -> ProjectContext:
    """Resolve context in order: cwd, git root, Braid config, global profile."""

    start = (start or Path.cwd()).resolve()
    root = find_braid_root(start)
    if root is not None:
        canonical = config_path(root)
        legacy = legacy_config_path(root)
        if canonical.is_file():
            return _context_from_root(root, load_kgconfig(root), canonical, legacy_layout=False)
        cfg = load_kgconfig(root)
        cfg_path = legacy if legacy.is_file() else None
        return _context_from_root(root, cfg, cfg_path, legacy_layout=True)

    git_root = find_git_root(start)
    if git_root is not None:
        return ProjectContext(
            root=git_root,
            dataset_id=git_root.name,
            has_kg=False,
            kgconfig={},
            config_path=None,
            legacy_layout=False,
        )

    profile_config = PROFILE_DIR / CONFIG_FILENAME
    return ProjectContext(
        root=PROFILE_DIR,
        dataset_id=GLOBAL_DATASET_ID,
        has_kg=(PROFILE_DIR / "kg").is_dir(),
        kgconfig={},
        config_path=profile_config if profile_config.is_file() else None,
        legacy_layout=False,
    )


def secrets_path() -> Path:
    return Path.home() / ".config" / "braid" / "secrets.env"


def load_secrets_into_env() -> None:
    """Load ~/.config/braid/secrets.env into os.environ without overrides."""

    p = secrets_path()
    if not p.is_file():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())
