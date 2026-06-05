"""`fairlead ask`: consultar el KG/RAG del proyecto activo (o el global con --global).

Combina resultados de Cognee (vector search) y DuckLake FTS (BM25) para
dar respuestas más ricas. Si Cognee no está disponible, DuckLake FTS
actúa como fallback.
"""
from __future__ import annotations

import sys
from typing import Any

from ..paths import GLOBAL_DATASET_ID, resolve_context
from ..runner import run_search


def _short(text: str, n: int = 280) -> str:
    return text[:n].replace("\n", " ") + ("…" if len(text) > n else "")


def _ducklake_fts_search(query: str, project_slug: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Search DuckLake FTS indexes as complement/fallback to Cognee."""
    try:
        from ..ducklake import WikiForgeCatalog
    except ImportError:
        return []

    results: list[dict[str, Any]] = []
    try:
        with WikiForgeCatalog() as cat:
            if cat.fts_con is None:
                return []
            # Search across all FTS indexes
            for index_name in ("adrs_fts", "project_memory_fts", "kg_nodes_fts"):
                try:
                    hits = cat.fts_search(index_name, query)
                    for h in hits:
                        results.append({
                            "source": f"ducklake:{index_name}",
                            "text": str(h.get("text", "")) if isinstance(h, dict) else str(h),
                            "score": float(h.get("score", 0)) if isinstance(h, dict) else 0.0,
                        })
                except Exception:
                    continue
    except Exception:
        return []

    # Deduplicate by text content and sort by score
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for r in results:
        key = r["text"][:100]
        if key not in seen:
            seen.add(key)
            unique.append(r)
    unique.sort(key=lambda x: x["score"], reverse=True)
    return unique[:top_k]


def _ducklake_memory_search(query: str, project_slug: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Search DuckLake structured memory (project + global levels)."""
    try:
        from ..ducklake import WikiForgeCatalog
    except ImportError:
        return []

    results: list[dict[str, Any]] = []
    try:
        with WikiForgeCatalog() as cat:
            # Project memory
            proj = cat.search_project_memory(query, project_slug=project_slug)
            for r in proj:
                results.append({
                    "source": "ducklake:project_memory",
                    "text": f"[{r.get('type', r.get('memory_type', '?'))}] {r.get('key', '?')}: {r.get('value', '')}",
                    "level": "project",
                })
            # Global memory (fallback)
            glob = cat.search_global_memory(query)
            for r in glob:
                results.append({
                    "source": "ducklake:global_memory",
                    "text": f"[{r.get('type', r.get('memory_type', '?'))}] {r.get('key', '?')}: {r.get('value', '')}",
                    "level": "global",
                })
    except Exception:
        return []

    return results[:top_k]


def _ducklake_hybrid_search(query: str, project_slug: str, top_k: int = 5) -> dict[str, Any]:
    """Run the DuckLake hybrid local/global retrieval pipeline."""
    try:
        from ..ducklake import WikiForgeCatalog
    except ImportError:
        return {}

    try:
        with WikiForgeCatalog() as cat:
            return cat.hybrid_search(query, project_slug=project_slug, top_k=top_k).as_dict()
    except Exception:
        return {}


def run(query: str, search_type: str = "CHUNKS", top_k: int = 5, use_global: bool = False) -> int:
    ctx = resolve_context()
    dataset = GLOBAL_DATASET_ID if use_global else ctx.dataset_id
    scope = "global profile" if use_global else f"project '{ctx.dataset_id}' ({ctx.root})"
    print(f"[fairlead ask] {scope} | type={search_type} top_k={top_k}")
    print(f"Q: {query}\n")

    # 1. Cognee vector search (primary)
    cognee_results: list[Any] = []
    try:
        cognee_results = run_search(query, dataset, search_type=search_type, top_k=top_k)
    except Exception as e:
        print(f"[fairlead ask] Cognee no disponible: {type(e).__name__}: {e}", file=sys.stderr)

    # 2. DuckLake hybrid retrieval (BM25 + graph + optional LanceDB + Global RAG batches)
    hybrid_results = _ducklake_hybrid_search(query, ctx.dataset_id, top_k=top_k)
    hybrid_sources = hybrid_results.get("sources", {}) if hybrid_results else {}
    fts_results = hybrid_sources.get("fts") or _ducklake_fts_search(query, ctx.dataset_id, top_k=top_k)
    graph_results = hybrid_sources.get("graph") or {}
    prompt_batches = hybrid_sources.get("global_prompts") or []

    # 3. DuckLake structured memory (3-level)
    mem_results = _ducklake_memory_search(query, ctx.dataset_id, top_k=top_k)

    # Combine and display
    has_any = bool(cognee_results) or bool(fts_results) or bool(mem_results) or bool(graph_results.get("edges")) or bool(prompt_batches)

    if cognee_results:
        print("── Cognee (vector search) ──")
        for i, item in enumerate(cognee_results[:top_k], 1):
            text = item.get("text", "") if isinstance(item, dict) else str(item)
            print(f"  [{i}] {_short(text)}")
        print()

    if fts_results:
        print("── DuckLake FTS (BM25) ──")
        for i, r in enumerate(fts_results, 1):
            print(f"  [{i}] [{r['source']}] {_short(r['text'])}")
        print()

    if mem_results:
        print("── DuckLake Memory (3-level) ──")
        for i, r in enumerate(mem_results, 1):
            level = r.get("level", "?")
            print(f"  [{i}] [{level}] {_short(r['text'])}")
        print()

    if graph_results.get("edges"):
        print("── DuckLake Graph Impact (Local RAG) ──")
        for i, edge in enumerate(graph_results["edges"][:top_k], 1):
            src = edge.get("source_name") or edge.get("source")
            dst = edge.get("target_name") or edge.get("target")
            print(f"  [{i}] {src} --{edge.get('type')}--> {dst}")
        print()

    if prompt_batches:
        print("── DuckLake Global RAG Prompt Batches ──")
        for batch in prompt_batches[:top_k]:
            paths = ", ".join(batch.get("source_paths", [])[:3])
            more = "…" if len(batch.get("source_paths", [])) > 3 else ""
            print(f"  [batch {batch.get('batch_id')}] {batch.get('char_count')} chars | {paths}{more}")
        print()

    if not has_any:
        print("[fairlead ask] no results — quizá necesitas `fairlead index` o cambiar --type.")
        return 0

    return 0
