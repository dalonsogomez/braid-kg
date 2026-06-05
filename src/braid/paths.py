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

PROJECT_MARKER_FILES = (
    ".git",
    "pyproject.toml",
    "package.json",
    "requirements.txt",
    "setup.py",
    "setup.cfg",
    "Dockerfile",
    "docker-compose.yml",
    "go.mod",
    "Cargo.toml",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "README.md",
)
PROJECT_MARKER_GLOBS = (
    "*.sln",
    "*.csproj",
    "*.fsproj",
    "*.xcodeproj",
    "*.xcworkspace",
)


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
    state_dir: Path | None = None
    global_profile: bool = False

    @property
    def braid_dir(self) -> Path:
        return self.state_dir or (self.root / BRAID_DIRNAME)

    @property
    def memory_dir(self) -> Path:
        if self.global_profile:
            return self.braid_dir
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


def _has_marker_file(root: Path, markers: tuple[str, ...]) -> bool:
    for marker in markers:
        if (root / marker).exists():
            return True
    return False


def _has_marker_glob(root: Path) -> bool:
    return any(next(root.glob(pattern), None) is not None for pattern in PROJECT_MARKER_GLOBS)


def has_project_marker(root: Path) -> bool:
    """Return True when root looks like a concrete project boundary."""

    return _has_marker_file(root, PROJECT_MARKER_FILES) or _has_marker_glob(root)


def _load_profile_config() -> dict:
    profile_config = PROFILE_DIR / CONFIG_FILENAME
    if profile_config.is_file():
        return tomllib.loads(profile_config.read_text())
    return {}


def find_project_root(start: Path | None = None) -> Path | None:
    """Walk upward looking for the nearest concrete project boundary."""

    cur = (start or Path.cwd()).resolve()
    if cur.is_file():
        cur = cur.parent
    while cur != cur.parent:
        if has_project_marker(cur):
            return cur
        cur = cur.parent
    return None


def _has_braid_state(root: Path) -> bool:
    if root == BRAID_HOME.parent:
        return False
    return config_path(root).is_file() or project_state_dir(root).is_dir()


def _has_legacy_state(root: Path) -> bool:
    if root == BRAID_HOME.parent:
        return False
    return legacy_config_path(root).is_file() or (root / ".kg").is_dir()


def find_braid_root(start: Path | None = None) -> Path | None:
    """Walk upward looking for Braid state within the nearest project boundary."""

    cur = (start or Path.cwd()).resolve()
    if cur.is_file():
        cur = cur.parent
    boundary = find_project_root(cur)
    while cur != cur.parent:
        if _has_braid_state(cur) or _has_legacy_state(cur):
            return cur
        if boundary is not None and cur == boundary:
            return None
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
    """Resolve context in order: Braid state, project boundary, git root, global profile."""

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

    project_root = find_project_root(start)
    if project_root is not None:
        return ProjectContext(
            root=project_root,
            dataset_id=project_root.name,
            has_kg=False,
            kgconfig={},
            config_path=None,
            legacy_layout=False,
        )

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
    cfg = _load_profile_config()
    return ProjectContext(
        root=BRAID_HOME.parent,
        dataset_id=cfg.get("dataset_id") or GLOBAL_DATASET_ID,
        has_kg=(PROFILE_DIR / "kg").is_dir(),
        kgconfig=cfg,
        config_path=profile_config if profile_config.is_file() else None,
        legacy_layout=False,
        state_dir=PROFILE_DIR,
        global_profile=True,
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
