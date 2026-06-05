"""Stack ADR 0005 + ADR 0006: Ollama Cloud kimi-k2.6 + bge-m3 local + Kuzu + LanceDB.

Centraliza los env vars del .env real (sec. 13.2 de AGENTS.md tras ADR 0006) para que el CLI
no duplique la lista en cada comando.

Tras la resolución de ADR 0007 (2026-05-04), también centraliza el storage de Cognee a
`~/.fairlead/cognee/` para que el CLI y el MCP server compartan dataset (no más islas por venv).
"""
from __future__ import annotations

import os
from pathlib import Path

# ADR 0007 resolved: storage centralizado fuera del venv.
FAIRLEAD_COGNEE_ROOT = Path.home() / ".fairlead" / "cognee"


def apply_stack_env() -> None:
    """Aplica las variables del stack vigente. NO sobreescribe lo que ya esté en environ
    (permite override desde shell o tests).

    Cognee Pydantic BaseSettings auto-binds field names to uppercase env vars, así que
    `SYSTEM_ROOT_DIRECTORY`, `DATA_ROOT_DIRECTORY` y `CACHE_ROOT_DIRECTORY` redirigen el
    storage de cognee desde el venv hacia `~/.fairlead/cognee/`.
    """
    # Asegurar que el path centralizado existe antes de setearlo (Cognee falla si no).
    FAIRLEAD_COGNEE_ROOT.mkdir(parents=True, exist_ok=True)

    defaults = {
        # LLM (dodge LiteLLM ':' parser via openai/ + OpenAI-compat endpoint)
        "LLM_PROVIDER": "openai",
        "LLM_MODEL": "openai/kimi-k2.6:cloud",
        "LLM_ENDPOINT": "http://localhost:11434/v1",
        "LLM_API_KEY": "ollama",
        "LLM_RATE_LIMIT_ENABLED": "true",
        "LLM_RATE_LIMIT_REQUESTS": "2",
        "LLM_RATE_LIMIT_INTERVAL": "5",
        # Embeddings (bge-m3 local via /v1/embeddings, dodge OllamaEmbeddingEngine 422)
        "EMBEDDING_PROVIDER": "ollama",
        "EMBEDDING_MODEL": "bge-m3",
        "EMBEDDING_ENDPOINT": "http://localhost:11434/v1/embeddings",
        "EMBEDDING_API_KEY": "ollama",
        "EMBEDDING_DIMENSIONS": "1024",
        "HUGGINGFACE_TOKENIZER": "BAAI/bge-m3",
        # Backends
        "GRAPH_DATABASE_PROVIDER": "kuzu",
        "VECTOR_DB_PROVIDER": "lancedb",
        # Cognee 1.0 ergonomics
        "ENABLE_BACKEND_ACCESS_CONTROL": "false",
        "COGNEE_SKIP_CONNECTION_TEST": "true",
        # ADR 0007 resolved: storage centralizado en ~/.fairlead/cognee/.
        "SYSTEM_ROOT_DIRECTORY": str(FAIRLEAD_COGNEE_ROOT / ".cognee_system"),
        "DATA_ROOT_DIRECTORY": str(FAIRLEAD_COGNEE_ROOT / ".data_storage"),
        "CACHE_ROOT_DIRECTORY": str(FAIRLEAD_COGNEE_ROOT / ".cognee_cache"),
    }
    for k, v in defaults.items():
        os.environ.setdefault(k, v)
