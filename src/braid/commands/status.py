"""`braid status`: resumen del proyecto activo + perfil global + DuckLake."""
from __future__ import annotations

from ..paths import GLOBAL_DATASET_ID, PROFILE_DIR, resolve_context


def _ducklake_status() -> dict | None:
    """Get DuckLake catalog summary if available."""
    try:
        from ..ducklake import BraidCatalog
    except ImportError:
        return None
    try:
        with BraidCatalog() as cat:
            return cat.get_catalog_summary()
    except Exception:
        return None


def run() -> int:
    ctx = resolve_context()
    print(f"Proyecto activo: {ctx.dataset_id}")
    print(f"  raíz:     {ctx.root}")
    print(f"  .braid/:  {'sí' if ctx.braid_dir.is_dir() else 'no'}")
    print(f"  kg/:      {'sí' if ctx.has_kg else 'no'}")
    print(f"  config:   {'sí' if ctx.has_config else 'no'}")
    if ctx.legacy_layout:
        print("  legacy:   sí (lectura de migración)")
    decisions = ctx.memory_dir / "decisions"
    n_decisions = len(list(decisions.glob("[0-9]*-*.md"))) if decisions.is_dir() else 0
    print(f"  ADRs:     {n_decisions}")

    # DuckLake status
    dl = _ducklake_status()
    if dl:
        print()
        print(f"DuckLake catalog:")
        print(f"  tablas:   {dl.get('tables', '?')}")
        print(f"  filas:    {dl.get('total_rows', 0)}")
        per_table = dl.get("per_table", {})
        if per_table:
            top_tables = sorted(per_table.items(), key=lambda x: x[1], reverse=True)[:5]
            for name, count in top_tables:
                print(f"    {name}: {count}")

    print()
    print(f"Perfil global ({GLOBAL_DATASET_ID}):")
    print(f"  raíz:     {PROFILE_DIR}")
    print(f"  existe:   {'sí' if PROFILE_DIR.is_dir() else 'no'}")
    return 0
