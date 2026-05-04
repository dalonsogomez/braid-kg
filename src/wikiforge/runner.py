"""Wrapper alrededor de cognee.add/cognify/search con el env del stack ADR 0005+0006 ya aplicado.

Importa cognee de forma diferida para no pagar el coste de import si el comando no lo necesita.
"""
from __future__ import annotations

import asyncio
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


async def cognify(dataset: str) -> None:
    _ensure_env()
    import cognee  # noqa: PLC0415
    await cognee.cognify(datasets=[dataset])


async def search(query: str, dataset: str, search_type: str = "CHUNKS", top_k: int = 10) -> list[Any]:
    _ensure_env()
    import cognee  # noqa: PLC0415
    stype = getattr(cognee.SearchType, search_type)
    return await cognee.search(query_type=stype, query_text=query, datasets=[dataset])


async def prune_all() -> None:
    """Limpia data + system. Destructivo — solo desde `wikiforge index --rebuild`."""
    _ensure_env()
    import cognee  # noqa: PLC0415
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=True)


# Helpers síncronos para ergonomía del CLI

def run_add(inputs: list[str], dataset: str) -> None:
    asyncio.run(add_inputs(inputs, dataset))


def run_cognify(dataset: str) -> None:
    asyncio.run(cognify(dataset))


def run_search(query: str, dataset: str, search_type: str = "CHUNKS", top_k: int = 10) -> list[Any]:
    return asyncio.run(search(query, dataset, search_type=search_type, top_k=top_k))


def run_prune() -> None:
    asyncio.run(prune_all())


def annotate_file(path: Path, root: Path, kind: str) -> str:
    """Añade el header [FILE kind=... path=...] que cognee+LLM mantienen en el grafo."""
    rel = path.relative_to(root)
    return f"[FILE kind={kind} path={rel}]\n" + path.read_text(errors="ignore")
