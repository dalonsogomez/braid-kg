"""Shared fixtures for WikiForge tests."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def tmp_git_root(tmp_path: Path) -> Path:
    """Create a minimal git repo structure for testing."""
    root = tmp_path / "test-project"
    root.mkdir()
    (root / ".git").mkdir()
    (root / "src").mkdir()
    (root / "src" / "main.py").write_text("def hello(): pass\n")
    (root / ".memory").mkdir()
    (root / ".memory" / "decisions").mkdir()
    (root / ".kg").mkdir()
    (root / ".rag").mkdir()
    return root


@pytest.fixture
def kgconfig_content() -> str:
    """Standard .kgconfig TOML content for tests."""
    return """\
dataset_id = "test-project"
graph_backend = "kuzu"
vector_backend = "lancedb"
embedder = "bge-m3"
llm = "kimi-k2.6:cloud"
fallback_threshold = 0.55
priority = ["active_file", "project_graph", "project_vector", "global_profile"]

[memory]
temporal_store = ".memory/sessions"
persistent_store = ".memory/persistent"
promotion_policy = "explicit_only"
"""
