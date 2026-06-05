"""Demo de criterio de salida Fase 1: cognify mini + promote-decision + recall.

Reset cognee_system corrupto + cognify de 3 archivos (AGENTS.md, Plan 0002, ADR 0006)
para demo end-to-end del flujo "promote-decision -> recall via braid ask".
"""
from __future__ import annotations

import asyncio
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from braid.config import apply_stack_env
from braid.paths import load_secrets_into_env
from braid.runner import annotate_file


REPO = Path(__file__).resolve().parents[1]
DATASET = "Braid"
COGNEE_SYSTEM = REPO / ".venv/lib/python3.13/site-packages/cognee/.cognee_system"


KEY_FILES = [
    REPO / "AGENTS.md",
    REPO / ".braid" / "memory" / "plans" / "0002-fase-1-bootstrap.md",
    REPO / ".braid" / "memory" / "decisions" / "0006-env-litellm-colon-dodge.md",
    REPO / ".braid" / "memory" / "MEMORY.md",
]


async def main() -> int:
    load_secrets_into_env()
    apply_stack_env()

    if COGNEE_SYSTEM.exists():
        print(f"[demo] removing corrupt {COGNEE_SYSTEM}...")
        shutil.rmtree(COGNEE_SYSTEM)

    import cognee  # noqa: PLC0415

    print("[demo] prune (defensivo)...")
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=True)

    inputs = []
    for p in KEY_FILES:
        if not p.is_file():
            print(f"[demo] skip missing {p}")
            continue
        kind = "doc" if p.suffix == ".md" else "code"
        inputs.append(annotate_file(p, REPO, kind))
        print(f"[demo]  + {p.relative_to(REPO)}")

    print(f"[demo] adding {len(inputs)} docs to dataset {DATASET}...")
    await cognee.add(inputs, dataset_name=DATASET)
    print("[demo] cognifying...")
    await cognee.cognify(datasets=[DATASET])

    print("\n[demo] sanity search 1: 'What is the current stack?'")
    res = await cognee.search(query_type=cognee.SearchType.CHUNKS, query_text="What is the current stack?", datasets=[DATASET])
    for i, item in enumerate((res or [])[:3], 1):
        text = item.get("text", "") if isinstance(item, dict) else str(item)
        head = text[:200].replace("\n", " ")
        print(f"  [{i}] {head}")

    print("[demo] done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
