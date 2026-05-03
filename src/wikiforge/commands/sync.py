"""`wikiforge sync`: alias semántico de `index` para reescaneo tras git pull."""
from __future__ import annotations

from . import index as index_cmd


def run() -> int:
    print("[wikiforge sync] reindexando (incremental)...")
    return index_cmd.run(rebuild=False)
