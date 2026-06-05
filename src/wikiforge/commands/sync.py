"""`fairlead sync`: alias semántico de `index` para reescaneo tras git pull / cambios.

ADR 0009: incremental real — si nada cambió desde el último index, exit 0
inmediato (<1s) sin tocar el LLM.
"""
from __future__ import annotations

from . import index as index_cmd


def run() -> int:
    print("[fairlead sync] reindexando (incremental por mtime)...")
    return index_cmd.run(rebuild=False)
