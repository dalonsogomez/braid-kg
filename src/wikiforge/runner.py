"""Wrapper alrededor de cognee.add/cognify/search con el env del stack ADR 0005+0006 ya aplicado.

Importa cognee de forma diferida para no pagar el coste de import si el comando no lo necesita.

ADR 0012 añade `rerank_via_openrouter` (cloud-only, sin descarga local) que reordena
top-K resultados de cognee.search vía Cohere Rerank 4 Fast en OpenRouter.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

from .config import apply_stack_env
from .paths import load_secrets_into_env


def _patch_ladybug_version_mapping() -> None:
    """Cognee 1.0.5 ships con `ladybug_version_mapping` que solo conoce hasta version_code 39
    (Kuzu 0.11.3). Cuando ladybug 0.15+ escribe el on-disk format, usa codes 40+ que el mapping
    no resuelve y `read_ladybug_storage_version` lanza `ValueError`. Workaround: extender el
    mapping en runtime con los códigos observados de ladybug 0.16.x.

    Cuando Cognee >=1.1 actualice el mapping upstream, este patch puede eliminarse.
    """
    try:
        from cognee.infrastructure.databases.graph.ladybug import ladybug_migrate as _lm  # type: ignore
        _lm.ladybug_version_mapping.setdefault(40, "0.16.0")
        _lm.ladybug_version_mapping.setdefault(41, "0.16.1")
    except ImportError:
        pass  # ladybug no instalado — no debería pasar con cognee 1.0.5+ pero defensivo


def _ensure_env() -> None:
    load_secrets_into_env()
    apply_stack_env()
    _patch_ladybug_version_mapping()


async def add_inputs(inputs: list[str], dataset: str) -> None:
    _ensure_env()
    import cognee  # noqa: PLC0415
    await cognee.add(inputs, dataset_name=dataset)


async def cognify(dataset: str, timeout: float = 120.0) -> None:
    """Wrapper sobre cognee.cognify.

    ADR 0009: Cognee 1.0.5 cuelga en cleanup async tras 'Pipeline run completed'
    (TODO Fase 2 #2 plan 0003). Envolvemos con asyncio.wait_for para que el
    cleanup hang no bloquee al CLI indefinidamente — los datos quedan íntegros
    porque el hang ocurre tras la escritura.
    """
    _ensure_env()
    import cognee  # noqa: PLC0415
    try:
        await asyncio.wait_for(cognee.cognify(datasets=[dataset]), timeout=timeout)
    except asyncio.TimeoutError:
        # Mitigación documentada en ADR 0009. Datos íntegros.
        print(
            f"[fairlead runner] cognify timeout tras {timeout:.0f}s "
            "(cleanup hang upstream cognee 1.0.5) — datos íntegros"
        )


async def search(query: str, dataset: str, search_type: str = "CHUNKS", top_k: int = 10) -> list[Any]:
    _ensure_env()
    import cognee  # noqa: PLC0415
    stype = getattr(cognee.SearchType, search_type)
    return await cognee.search(query_type=stype, query_text=query, datasets=[dataset])


async def prune_all() -> None:
    """Limpia data + system. Destructivo — solo desde `fairlead index --rebuild`."""
    _ensure_env()
    import cognee  # noqa: PLC0415
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=True)


# Helpers síncronos para ergonomía del CLI

def run_add(inputs: list[str], dataset: str) -> None:
    asyncio.run(add_inputs(inputs, dataset))


def run_cognify(dataset: str, timeout: float = 120.0) -> None:
    asyncio.run(cognify(dataset, timeout=timeout))


def run_search(query: str, dataset: str, search_type: str = "CHUNKS", top_k: int = 10) -> list[Any]:
    return asyncio.run(search(query, dataset, search_type=search_type, top_k=top_k))


def run_prune() -> None:
    asyncio.run(prune_all())


def annotate_file(path: Path, root: Path, kind: str) -> str:
    """Añade el header [FILE kind=... path=...] que cognee+LLM mantienen en el grafo."""
    rel = path.relative_to(root)
    return f"[FILE kind={kind} path={rel}]\n" + path.read_text(errors="ignore")


# ---------------------------------------------------------------------------
# ADR 0012 — Reranker cloud vía OpenRouter (Cohere Rerank 4 Fast)
# ---------------------------------------------------------------------------

OPENROUTER_RERANK_URL = "https://openrouter.ai/api/v1/rerank"
DEFAULT_RERANKER_MODEL = "cohere/rerank-4-fast"
RERANK_TIMEOUT_S = 30.0


def _extract_text_for_rerank(item: Any) -> str:
    """Extrae el contenido textual de un item devuelto por cognee.search.

    Defensivo ante dict / objeto con .text / str / lista anidada / None.
    Mismo patrón que `commands.eval._extract_text` pero copiado aquí para
    evitar import circular.
    """
    if item is None:
        return ""
    if isinstance(item, str):
        return item
    if isinstance(item, list):
        return " \n ".join(_extract_text_for_rerank(x) for x in item)
    if isinstance(item, dict):
        for key in ("text", "content", "description", "summary"):
            v = item.get(key)
            if isinstance(v, str):
                return v
        try:
            return json.dumps(item, ensure_ascii=False)
        except (TypeError, ValueError):
            return repr(item)
    for attr in ("text", "content", "description", "summary"):
        v = getattr(item, attr, None)
        if isinstance(v, str):
            return v
    return str(item)


def _get_openrouter_key() -> str | None:
    load_secrets_into_env()
    return os.environ.get("OPENROUTER_API_KEY") or None


def rerank_via_openrouter(
    query: str,
    items: list[Any],
    top_n: int | None = None,
    model: str = DEFAULT_RERANKER_MODEL,
) -> list[Any]:
    """Reordena `items` por relevancia a `query` vía OpenRouter (Cohere Rerank 4 Fast).

    ADR 0012: opt-in. Si `OPENROUTER_API_KEY` no está disponible, devuelve
    `items[:top_n]` (degraded mode con log). Si la llamada HTTP falla, idem.
    """
    if not items:
        return items
    if top_n is None or top_n > len(items):
        top_n = len(items)

    key = _get_openrouter_key()
    if not key:
        print(
            "[fairlead rerank] OPENROUTER_API_KEY ausente — devuelvo top_n sin reordenar "
            "(degraded mode). Añade la key a ~/.config/fairlead/secrets.env para activar.",
            file=sys.stderr,
        )
        return items[:top_n]

    try:
        import httpx  # noqa: PLC0415  — dep optativa, ya está en pyproject por commands/review.py
    except ImportError:
        print(
            "[fairlead rerank] httpx no instalado — devuelvo top_n sin reordenar "
            "(degraded mode). `uv pip install httpx`.",
            file=sys.stderr,
        )
        return items[:top_n]

    documents = [_extract_text_for_rerank(it) for it in items]
    body = {
        "model": model,
        "query": query,
        "documents": documents,
        "top_n": top_n,
    }
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    try:
        response = httpx.post(OPENROUTER_RERANK_URL, headers=headers, json=body, timeout=RERANK_TIMEOUT_S)
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPError as e:
        print(f"[fairlead rerank] HTTP error: {type(e).__name__}: {e} — degraded mode", file=sys.stderr)
        return items[:top_n]
    except (ValueError, KeyError) as e:
        print(f"[fairlead rerank] respuesta inesperada de OpenRouter: {e} — degraded mode", file=sys.stderr)
        return items[:top_n]

    results = data.get("results") or []
    if not results:
        print("[fairlead rerank] respuesta vacía — degraded mode", file=sys.stderr)
        return items[:top_n]

    reordered: list[Any] = []
    for r in results:
        idx = r.get("index")
        if isinstance(idx, int) and 0 <= idx < len(items):
            reordered.append(items[idx])
    return reordered or items[:top_n]


def run_search_with_rerank(
    query: str,
    dataset: str,
    search_type: str = "CHUNKS",
    top_k: int = 10,
    rerank: bool = False,
    rerank_top_n: int | None = None,
) -> list[Any]:
    """Convenience: search + opcional rerank en una sola llamada (síncrona)."""
    items = run_search(query, dataset, search_type=search_type, top_k=top_k)
    if not rerank or not items:
        return items
    n = rerank_top_n or top_k
    return rerank_via_openrouter(query, items, top_n=n)
