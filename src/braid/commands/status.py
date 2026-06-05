"""`braid status`: resumen del proyecto activo + perfil global + DuckLake."""
from __future__ import annotations

import json
import sys
from pathlib import Path

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


def _string_path(path: Path | None) -> str | None:
    return str(path) if path is not None else None


def build_status_payload() -> dict:
    ctx = resolve_context()
    decisions = ctx.memory_dir / "decisions"
    n_decisions = len(list(decisions.glob("[0-9]*-*.md"))) if decisions.is_dir() else 0
    return {
        "root": str(ctx.root),
        "dataset_id": ctx.dataset_id,
        "global_profile": ctx.global_profile,
        "state_dir": str(ctx.braid_dir),
        "braid_dir": str(ctx.braid_dir),
        "memory_dir": str(ctx.memory_dir),
        "kg_dir": str(ctx.kg_dir),
        "rag_dir": str(ctx.rag_dir),
        "wiki_dir": str(ctx.wiki_dir),
        "has_config": ctx.has_config,
        "config_path": _string_path(ctx.config_path),
        "has_kg": ctx.has_kg,
        "legacy_layout": ctx.legacy_layout,
        "adr_count": n_decisions,
        "global_profile_dir": str(PROFILE_DIR),
        "global_profile_exists": PROFILE_DIR.is_dir(),
        "ducklake": _ducklake_status(),
    }


def _print_human(payload: dict) -> None:
    if payload["global_profile"]:
        print(f"Perfil global activo: {payload['dataset_id']}")
        print(f"  $HOME:    {payload['root']}")
        print(f"  storage:  {payload['state_dir']}")
        print(f"  kg/:      {'sí' if payload['has_kg'] else 'no'}")
        print(f"  config:   {'sí' if payload['has_config'] else 'no'}")
    else:
        print(f"Proyecto activo: {payload['dataset_id']}")
        print(f"  raíz:     {payload['root']}")
        print(f"  .braid/:  {'sí' if Path(payload['braid_dir']).is_dir() else 'no'}")
        print(f"  kg/:      {'sí' if payload['has_kg'] else 'no'}")
        print(f"  config:   {'sí' if payload['has_config'] else 'no'}")
        if payload["legacy_layout"]:
            print("  legacy:   sí (lectura de migración)")
    print(f"  ADRs:     {payload['adr_count']}")

    dl = payload.get("ducklake")
    if dl:
        print()
        print("DuckLake catalog:")
        print(f"  tablas:   {dl.get('tables', '?')}")
        print(f"  filas:    {dl.get('total_rows', 0)}")
        per_table = dl.get("per_table", {})
        if per_table:
            top_tables = sorted(per_table.items(), key=lambda x: x[1], reverse=True)[:5]
            for name, count in top_tables:
                print(f"    {name}: {count}")

    if not payload["global_profile"]:
        print()
        print(f"Perfil global ({GLOBAL_DATASET_ID}):")
        print(f"  $HOME:    {PROFILE_DIR.parent.parent}")
        print(f"  storage:  {payload['global_profile_dir']}")
        print(f"  existe:   {'sí' if payload['global_profile_exists'] else 'no'}")


def run(as_json: bool = False) -> int:
    payload = build_status_payload()
    if as_json:
        sys.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n")
        return 0
    _print_human(payload)
    return 0
