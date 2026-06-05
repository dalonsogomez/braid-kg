"""Cliente multi-modelo ZenMux — llama a los 3 modelos en paralelo vía OpenAI-compatible API.

Modelos configurados (slug real de ZenMux):
- ``anthropic/claude-opus-4.7``   — razonamiento profundo (alias: claude-opus-4-7)
- ``openai/gpt-5.3-codex``       — Codex optimizado para código
- ``google/gemini-3.1-pro-preview`` — visión + razonamiento multimodal

Uso:
    from braid.zenmux import review_in_parallel

    results = review_in_parallel(system_prompt, user_prompt)
    for r in results:
        print(f"[{r.model}] {r.content[:100]}...")
"""
from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openai import OpenAI

from .paths import load_secrets_into_env

ZENMUX_BASE_URL = "https://zenmux.ai/api/v1"

MODEL_SLUGS: list[str] = [
    "anthropic/claude-opus-4.7",
    "openai/gpt-5.3-codex",
    "google/gemini-3.1-pro-preview",
]

MODEL_ALIASES: dict[str, str] = {
    "opus-4-7-think": "anthropic/claude-opus-4.7",
    "claude-opus-4-7": "anthropic/claude-opus-4.7",
    "gpt-5-3-codex": "openai/gpt-5.3-codex",
    "gemini-3-1-pro-preview": "google/gemini-3.1-pro-preview",
}


@dataclass
class ModelResult:
    """Resultado estructurado de una llamada a un modelo."""

    model: str
    content: str | None = None
    error: str | None = None
    latency_ms: float = 0.0
    finish_reason: str | None = None
    usage: dict[str, int] = field(default_factory=dict)


def resolve_slug(alias_or_slug: str) -> str:
    """Resuelve un alias corto al slug real de ZenMux."""
    if alias_or_slug in MODEL_ALIASES:
        return MODEL_ALIASES[alias_or_slug]
    if alias_or_slug in MODEL_SLUGS:
        return alias_or_slug
    msg = (
        f"modelo desconocido: {alias_or_slug!r}. "
        f"Usa uno de: {MODEL_SLUGS} o alias: {list(MODEL_ALIASES)}"
    )
    raise ValueError(msg)


def _get_api_key() -> str:
    """Obtiene ZENMUX_API_KEY del entorno o de ``~/.config/braid/secrets.env``."""
    load_secrets_into_env()
    key = os.environ.get("ZENMUX_API_KEY")
    if not key:
        msg = (
            "ZENMUX_API_KEY no encontrada. "
            "Añádela a ~/.config/braid/secrets.env:\n"
            '  ZENMUX_API_KEY="sk-ss-v1-..."'
        )
        raise OSError(msg)
    return key


def build_client(**kwargs: Any) -> OpenAI:
    """Construye un cliente OpenAI apuntando al endpoint de ZenMux."""
    return OpenAI(
        base_url=ZENMUX_BASE_URL,
        api_key=_get_api_key(),
        **kwargs,
    )


def call_model(
    client: OpenAI,
    model: str,
    messages: list[dict],
    temperature: float = 0.0,
    max_tokens: int = 4096,
    **kwargs: Any,
) -> ModelResult:
    """Llama a un modelo de ZenMux y devuelve el resultado estructurado.

    Args:
        client: Cliente OpenAI apuntando a ZenMux.
        model: Slug del modelo (ej. ``anthropic/claude-opus-4.7``).
        messages: Lista de mensajes estilo OpenAI.
        temperature: Temperatura (default 0.0 para code review).
        max_tokens: Máximo de tokens de salida.
        **kwargs: Parámetros extra pasados a ``client.chat.completions.create``.

    Returns:
        ``ModelResult`` con el contenido o el error.
    """
    start = time.perf_counter()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        elapsed = (time.perf_counter() - start) * 1000
        choice = response.choices[0]
        return ModelResult(
            model=model,
            content=choice.message.content,
            finish_reason=choice.finish_reason,
            latency_ms=round(elapsed, 1),
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            },
        )
    except Exception as exc:
        elapsed = (time.perf_counter() - start) * 1000
        return ModelResult(
            model=model,
            error=f"{type(exc).__name__}: {exc}",
            latency_ms=round(elapsed, 1),
        )


def review_in_parallel(
    system_prompt: str,
    user_prompt: str,
    models: list[str] | None = None,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    max_workers: int = 3,
) -> list[ModelResult]:
    """Llama a los 3 modelos en paralelo con el mismo prompt.

    Args:
        system_prompt: Prompt del sistema (instrucciones para el rol).
        user_prompt: Prompt del usuario (el código/cambio a revisar).
        models: Lista de slugs a usar. Default: los 3 modelos canónicos.
        temperature: Temperatura para las llamadas.
        max_tokens: Máximo de tokens de salida por modelo.
        max_workers: Paralelismo máximo (default 3).

    Returns:
        Lista de ``ModelResult``, uno por modelo, en el orden de ``models``.
    """
    if models is None:
        models = MODEL_SLUGS[:]

    client = build_client()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    results: list[ModelResult] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        fut_to_model = {
            pool.submit(call_model, client, m, messages, temperature, max_tokens): m
            for m in models
        }
        for fut in as_completed(fut_to_model):
            results.append(fut.result())

    results.sort(key=lambda r: models.index(r.model) if r.model in models else 999)
    return results
