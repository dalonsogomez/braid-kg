"""Resolución de contexto AGENTS.md sec. 4.3: cwd → git root → .kgconfig → ~/.fairlead/profile/."""
from __future__ import annotations

import os
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path

FAIRLEAD_HOME = Path.home() / ".fairlead"
PROFILE_DIR = FAIRLEAD_HOME / "profile"
GLOBAL_DATASET_ID = "_global_profile"


@dataclass(frozen=True)
class ProjectContext:
    """Información mínima del proyecto activo para que el agente decida qué consultar."""
    root: Path
    dataset_id: str
    has_kg: bool
    kgconfig: dict
    fallback_threshold: float = 0.55

    @property
    def memory_dir(self) -> Path:
        return self.root / ".memory"

    @property
    def kg_dir(self) -> Path:
        return self.root / ".kg"

    @property
    def rag_dir(self) -> Path:
        return self.root / ".rag"


def find_git_root(start: Path | None = None) -> Path | None:
    """Sube desde `start` (o cwd) hasta encontrar la raíz Git. None si no hay repo."""
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


def find_kg_root(start: Path | None = None) -> Path | None:
    """Sube buscando un dir que contenga `.kg/`. None si no hay."""
    cur = (start or Path.cwd()).resolve()
    while cur != cur.parent:
        if (cur / ".kg").is_dir() or (cur / ".kgconfig").is_file():
            return cur
        cur = cur.parent
    return None


def load_kgconfig(root: Path) -> dict:
    """Carga `.kgconfig` (TOML) si existe; vacío si no."""
    cfg = root / ".kgconfig"
    if not cfg.is_file():
        return {}
    return tomllib.loads(cfg.read_text())


def resolve_context(start: Path | None = None) -> ProjectContext:
    """AGENTS.md sec. 4.3: orden estricto cwd → git root → .kgconfig → fallback global.

    Si no hay proyecto activo, devuelve un contexto apuntando al perfil global.
    """
    start = (start or Path.cwd()).resolve()
    kg_root = find_kg_root(start)
    if kg_root is not None:
        cfg = load_kgconfig(kg_root)
        return ProjectContext(
            root=kg_root,
            dataset_id=cfg.get("dataset_id") or kg_root.name,
            has_kg=(kg_root / ".kg").is_dir(),
            kgconfig=cfg,
            fallback_threshold=float(cfg.get("fallback_threshold", 0.55)),
        )
    git_root = find_git_root(start)
    if git_root is not None:
        return ProjectContext(
            root=git_root,
            dataset_id=git_root.name,
            has_kg=False,
            kgconfig={},
        )
    # Fallback: perfil global
    return ProjectContext(
        root=PROFILE_DIR,
        dataset_id=GLOBAL_DATASET_ID,
        has_kg=(PROFILE_DIR / ".kg").is_dir(),
        kgconfig={},
    )


def secrets_path() -> Path:
    return Path.home() / ".config/fairlead/secrets.env"


def load_secrets_into_env() -> None:
    """Carga `~/.config/fairlead/secrets.env` en `os.environ` sin sobreescribir."""
    p = secrets_path()
    if not p.is_file():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())
