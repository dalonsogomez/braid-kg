"""Shared fixtures for Braid tests."""
from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from braid.ducklake import load_duckdb_extension


@pytest.fixture
def tmp_git_root(tmp_path: Path) -> Path:
    """Create a minimal git repo structure for testing."""
    root = tmp_path / "test-project"
    root.mkdir()
    (root / ".git").mkdir()
    (root / "src").mkdir()
    (root / "src" / "main.py").write_text("def hello(): pass\n")
    (root / ".braid" / "memory" / "decisions").mkdir(parents=True)
    (root / ".braid" / "kg").mkdir(parents=True)
    (root / ".braid" / "rag").mkdir(parents=True)
    return root


@pytest.fixture
def kgconfig_content() -> str:
    """Standard Braid config TOML content for tests."""
    return """\
dataset_id = "test-project"
graph_backend = "kuzu"
vector_backend = "lancedb"
embedder = "bge-m3"
llm = "kimi-k2.6:cloud"
fallback_threshold = 0.55
priority = ["active_file", "project_graph", "project_vector", "global_profile"]

[memory]
temporal_store = ".braid/memory/sessions"
persistent_store = ".braid/memory/persistent"
promotion_policy = "explicit_only"
"""


def create_ducklake_test_catalog(tmp_path: Path) -> tuple[str, Path, Path]:
    """Create an isolated DuckLake catalog with the Braid table surface."""
    catalog = f"ducklake:duckdb:{tmp_path / 'catalog'}"
    con = duckdb.connect()
    con.execute("LOAD ducklake")
    con.execute(f"ATTACH '{catalog}' AS braid")
    con.execute("USE braid")

    statements = [
        """
        CREATE TABLE session_memory (
            id INTEGER, session_id VARCHAR, agent_id VARCHAR, project_slug VARCHAR,
            memory_type VARCHAR, key VARCHAR, value VARCHAR, metadata_json JSON,
            created_at TIMESTAMP DEFAULT now(), updated_at TIMESTAMP DEFAULT now(),
            promoted BOOLEAN DEFAULT false, promoted_at TIMESTAMP
        )
        """,
        """
        CREATE TABLE project_memory (
            id INTEGER, project_slug VARCHAR, memory_type VARCHAR, key VARCHAR, value VARCHAR,
            source_path VARCHAR, adr_id VARCHAR, tags VARCHAR[], metadata_json JSON,
            confidence FLOAT, created_at TIMESTAMP DEFAULT now(), updated_at TIMESTAMP DEFAULT now(),
            promoted BOOLEAN DEFAULT false, promoted_at TIMESTAMP
        )
        """,
        """
        CREATE TABLE global_memory (
            id INTEGER, memory_type VARCHAR, key VARCHAR, value VARCHAR, tags VARCHAR[],
            applies_to VARCHAR[], metadata_json JSON, created_at TIMESTAMP DEFAULT now(),
            updated_at TIMESTAMP DEFAULT now()
        )
        """,
        """
        CREATE TABLE kg_nodes (
            id INTEGER, node_id VARCHAR, node_type VARCHAR, name VARCHAR, description VARCHAR,
            project_slug VARCHAR, source_path VARCHAR, line_number INTEGER, language VARCHAR,
            metadata_json JSON, created_at TIMESTAMP DEFAULT now(), updated_at TIMESTAMP DEFAULT now(),
            valid_from TIMESTAMP, valid_to TIMESTAMP, commit_sha VARCHAR
        )
        """,
        """
        CREATE TABLE kg_edges (
            id INTEGER, edge_type VARCHAR, source_node_id VARCHAR, target_node_id VARCHAR,
            project_slug VARCHAR, weight FLOAT, metadata_json JSON, created_at TIMESTAMP DEFAULT now(),
            valid_from TIMESTAMP, valid_to TIMESTAMP, commit_sha VARCHAR
        )
        """,
        """
        CREATE TABLE rag_chunks (
            id INTEGER, chunk_id VARCHAR, project_slug VARCHAR, dataset_id VARCHAR, content VARCHAR,
            source_path VARCHAR, chunk_index INTEGER, chunk_type VARCHAR, embedding_model VARCHAR,
            embedding_dims INTEGER, embedding FLOAT[], metadata_json JSON, created_at TIMESTAMP DEFAULT now(),
            updated_at TIMESTAMP DEFAULT now()
        )
        """,
        """
        CREATE TABLE rag_search_cache (
            id INTEGER, query_hash VARCHAR, query_text VARCHAR, project_slug VARCHAR, search_type VARCHAR,
            top_k INTEGER, results_json VARCHAR, hit_count INTEGER DEFAULT 0,
            last_used_at TIMESTAMP DEFAULT now(), created_at TIMESTAMP DEFAULT now()
        )
        """,
        """
        CREATE TABLE adrs (
            id INTEGER, adr_id VARCHAR, title VARCHAR, status VARCHAR, superseded_by VARCHAR,
            context VARCHAR, decision VARCHAR, consequences VARCHAR, tags VARCHAR[], project_slug VARCHAR,
            file_path VARCHAR, created_at TIMESTAMP DEFAULT now(), updated_at TIMESTAMP DEFAULT now()
        )
        """,
        """
        CREATE TABLE conversations (
            id INTEGER, conversation_id VARCHAR, agent_id VARCHAR, project_slug VARCHAR,
            session_type VARCHAR, model_used VARCHAR, tool_used VARCHAR, start_time TIMESTAMP DEFAULT now(),
            end_time TIMESTAMP, total_tokens INTEGER, summary VARCHAR, metadata_json JSON
        )
        """,
        """
        CREATE TABLE conversation_turns (
            id INTEGER, conversation_id VARCHAR, turn_number INTEGER, role VARCHAR, content VARCHAR,
            tool_calls_json JSON, tokens_used INTEGER, latency_ms INTEGER, created_at TIMESTAMP DEFAULT now()
        )
        """,
        """
        CREATE TABLE eval_runs (
            id INTEGER, run_id VARCHAR, project_slug VARCHAR, total_questions INTEGER, total_score FLOAT,
            recall_at_1 FLOAT, recall_at_k FLOAT, rerank_used BOOLEAN, search_type VARCHAR,
            model_used VARCHAR, metadata_json JSON, created_at TIMESTAMP DEFAULT now()
        )
        """,
        """
        CREATE TABLE eval_answers (
            id INTEGER, run_id VARCHAR, question_id VARCHAR, answer VARCHAR, score FLOAT, metadata_json JSON, created_at TIMESTAMP DEFAULT now()
        )
        """,
        """
        CREATE TABLE ingested_files (
            id INTEGER, project_slug VARCHAR, file_path VARCHAR, file_hash VARCHAR, file_size INTEGER,
            language VARCHAR, kind VARCHAR, last_modified TIMESTAMP, chunk_count INTEGER, dataset_id VARCHAR,
            metadata_json JSON, updated_at TIMESTAMP DEFAULT now()
        )
        """,
        """
        CREATE TABLE sync_log (
            id INTEGER, source VARCHAR, target VARCHAR, sync_type VARCHAR, tables_synced VARCHAR[],
            rows_synced INTEGER, status VARCHAR, error_message VARCHAR, created_at TIMESTAMP DEFAULT now()
        )
        """,
        """
        CREATE TABLE agents (
            id INTEGER, agent_id VARCHAR, agent_name VARCHAR, agent_type VARCHAR, description VARCHAR,
            capabilities VARCHAR[], project_slugs VARCHAR[], last_active_at TIMESTAMP DEFAULT now(),
            created_at TIMESTAMP DEFAULT now()
        )
        """,
        """
        CREATE TABLE system_metadata (
            key VARCHAR, value VARCHAR, description VARCHAR, updated_at TIMESTAMP DEFAULT now()
        )
        """,
    ]
    for statement in statements:
        con.execute(statement)
    con.close()

    fts_path = tmp_path / "fts.duckdb"
    fts = duckdb.connect(str(fts_path))
    assert load_duckdb_extension(fts, "fts", install=True)
    fts.close()

    return catalog, fts_path, tmp_path / "lancedb"


@pytest.fixture
def ducklake_test_catalog(tmp_path: Path) -> tuple[str, Path, Path]:
    """Provide an isolated DuckLake catalog path tuple for tests."""
    return create_ducklake_test_catalog(tmp_path)
