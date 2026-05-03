"""`wikiforge status`: resumen del proyecto activo + perfil global."""
from __future__ import annotations

from ..paths import GLOBAL_DATASET_ID, PROFILE_DIR, resolve_context


def run() -> int:
    ctx = resolve_context()
    print(f"Proyecto activo: {ctx.dataset_id}")
    print(f"  raíz:     {ctx.root}")
    print(f"  .kg/:     {'sí' if ctx.has_kg else 'no'}")
    print(f"  .kgconfig:{'sí' if (ctx.root / '.kgconfig').is_file() else 'no'}")
    decisions = ctx.memory_dir / "decisions"
    n_decisions = len(list(decisions.glob("[0-9]*-*.md"))) if decisions.is_dir() else 0
    print(f"  ADRs:     {n_decisions}")

    print()
    print(f"Perfil global ({GLOBAL_DATASET_ID}):")
    print(f"  raíz:     {PROFILE_DIR}")
    print(f"  existe:   {'sí' if PROFILE_DIR.is_dir() else 'no'}")
    return 0
