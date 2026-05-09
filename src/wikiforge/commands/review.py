"""``wikiforge review`` — lanza los 3 modelos de ZenMux en paralelo y consolida resultados.

Uso:
    wikiforge review "<diff o descripción del cambio>"
    wikiforge review --system-prompt "Eres revisor experto" "<código a revisar>"
    wikiforge review --models opus-4-7-think,gpt-5-3-codex "<código>"
"""
from __future__ import annotations

import sys
from typing import Any

from ..zenmux import MODEL_SLUGS, resolve_slug, review_in_parallel

DEFAULT_SYSTEM_PROMPT = (
    "Eres un revisor de código experto. Analiza el cambio proporcionado "
    "y busca bugs de correctness, seguridad, rendimiento y calidad. "
    "Devuelve un análisis estructurado con: severidad (P0/P1/P2/P3), "
    "archivo y línea, descripción del problema, y sugerencia de fix."
)


def run(
    prompt: str,
    system_prompt: str | None = None,
    models: list[str] | None = None,
    temperature: float = 0.0,
    max_tokens: int = 4096,
) -> int:
    if models is None:
        models = MODEL_SLUGS[:]
    else:
        models = [resolve_slug(m) for m in models]

    sp = system_prompt or DEFAULT_SYSTEM_PROMPT

    print("[wikiforge review] modelos:", ", ".join(models))
    print()

    results = review_in_parallel(
        system_prompt=sp,
        user_prompt=prompt,
        models=models,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    errors = 0
    for r in results:
        label = r.model.removeprefix("anthropic/").removeprefix("openai/").removeprefix("google/")
        if r.error:
            print(f"  ✗ {label:30s} ERROR en {r.latency_ms:>7.0f} ms: {r.error}")
            errors += 1
        else:
            preview = r.content[:120].replace("\n", " ").strip() if r.content else ""
            print(
                f"  ✓ {label:30s}"
                f" {r.latency_ms:>7.0f} ms"
                f" {r.finish_reason or '':>10s}"
                f" {r.usage.get('prompt_tokens', 0):>6d}→{r.usage.get('completion_tokens', 0):<6d}"
            )
            print(f"    {preview}…")
            print()

    if errors == len(results):
        print("[wikiforge review] TODOS los modelos fallaron — revisa tu ZENMUX_API_KEY y red.")
        return 1

    if errors > 0:
        print(f"[wikiforge review] {errors}/{len(results)} modelos fallaron — parcial.")

    return 0


if __name__ == "__main__":
    # stub test directo
    sys.exit(run(prompt="revisa este código: `x = 1/0`"))
