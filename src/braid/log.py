"""Structured JSON logging for Braid.

AGENTS.md sec. 3: "Logs JSON estructurados a stdout."

Usage:
    from braid.log import get_logger
    log = get_logger("braid.ask")
    log.info("search_completed", query="Ollama", results=5, elapsed_ms=120)
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from typing import Any


class JSONLogger:
    """Minimal structured JSON logger.

    Outputs one JSON object per line to stdout. Each line contains:
    - timestamp: ISO 8601 UTC
    - level: INFO, WARN, ERROR
    - logger: dot-separated name (e.g. "braid.ask")
    - event: human-readable event name
    - plus any extra key-value pairs
    """

    def __init__(self, name: str) -> None:
        self.name = name

    def _emit(self, level: str, event: str, **kwargs: Any) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "logger": self.name,
            "event": event,
            **kwargs,
        }
        try:
            line = json.dumps(record, ensure_ascii=False, default=str)
            sys.stdout.write(line + "\n")
            sys.stdout.flush()
        except Exception:
            # Fallback: unstructured
            sys.stdout.write(f"[{level}] {self.name} {event} {kwargs}\n")

    def info(self, event: str, **kwargs: Any) -> None:
        self._emit("INFO", event, **kwargs)

    def warn(self, event: str, **kwargs: Any) -> None:
        self._emit("WARN", event, **kwargs)

    def error(self, event: str, **kwargs: Any) -> None:
        self._emit("ERROR", event, **kwargs)

    def timer(self, event: str) -> _Timer:
        """Context manager that logs elapsed time on exit."""
        return _Timer(self, event)


class _Timer:
    """Timer context manager for measuring elapsed time."""

    def __init__(self, logger: JSONLogger, event: str) -> None:
        self.logger = logger
        self.event = event
        self._start: float = 0.0

    def __enter__(self) -> _Timer:
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc: Any) -> None:
        elapsed_ms = (time.perf_counter() - self._start) * 1000
        self.logger.info(self.event, elapsed_ms=round(elapsed_ms, 1))


def get_logger(name: str) -> JSONLogger:
    """Get a named JSON logger."""
    return JSONLogger(name)
