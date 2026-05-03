"""`wikiforge ask`: consultar el KG/RAG del proyecto activo (o el global con --global)."""
from __future__ import annotations

import sys

from ..paths import GLOBAL_DATASET_ID, resolve_context
from ..runner import run_search


def _short(text: str, n: int = 280) -> str:
    return text[:n].replace("\n", " ") + ("…" if len(text) > n else "")


def run(query: str, search_type: str = "CHUNKS", top_k: int = 5, use_global: bool = False) -> int:
    ctx = resolve_context()
    dataset = GLOBAL_DATASET_ID if use_global else ctx.dataset_id
    scope = "global profile" if use_global else f"project '{ctx.dataset_id}' ({ctx.root})"
    print(f"[wikiforge ask] {scope} | type={search_type} top_k={top_k}")
    print(f"Q: {query}\n")

    try:
        res = run_search(query, dataset, search_type=search_type, top_k=top_k)
    except Exception as e:
        print(f"[wikiforge ask] ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    if not res:
        print("[wikiforge ask] no results — quizá necesitas `wikiforge index` o cambiar --type.")
        return 0

    for i, item in enumerate(res[:top_k], 1):
        text = item.get("text", "") if isinstance(item, dict) else str(item)
        print(f"[{i}] {_short(text)}")
        print()

    return 0
