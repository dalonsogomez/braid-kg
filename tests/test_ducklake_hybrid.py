from __future__ import annotations

from datetime import datetime
from pathlib import Path

import duckdb

from braid.ducklake import BraidCatalog


def _catalog(tmp_path: Path) -> tuple[str, Path, Path]:
    catalog = f"ducklake:duckdb:{tmp_path / 'catalog'}"
    con = duckdb.connect()
    con.execute("LOAD ducklake")
    con.execute(f"ATTACH '{catalog}' AS braid")
    con.execute("USE braid")
    con.execute(
        """
        CREATE TABLE kg_nodes (
            id INTEGER,
            node_id VARCHAR,
            node_type VARCHAR,
            name VARCHAR,
            description VARCHAR,
            project_slug VARCHAR,
            source_path VARCHAR,
            line_number INTEGER,
            language VARCHAR,
            metadata_json JSON,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
        """
    )
    con.execute(
        """
        CREATE TABLE kg_edges (
            id INTEGER,
            edge_type VARCHAR,
            source_node_id VARCHAR,
            target_node_id VARCHAR,
            project_slug VARCHAR,
            weight FLOAT,
            metadata_json JSON,
            created_at TIMESTAMP
        )
        """
    )
    con.execute(
        """
        CREATE TABLE rag_chunks (
            id INTEGER,
            chunk_id VARCHAR,
            project_slug VARCHAR,
            dataset_id VARCHAR,
            content VARCHAR,
            source_path VARCHAR,
            chunk_index INTEGER,
            chunk_type VARCHAR,
            embedding_model VARCHAR,
            embedding_dims INTEGER,
            metadata_json JSON,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
        """
    )
    con.execute(
        """
        CREATE TABLE project_memory (
            id INTEGER,
            project_slug VARCHAR,
            memory_type VARCHAR,
            key VARCHAR,
            value VARCHAR,
            source_path VARCHAR,
            adr_id VARCHAR,
            tags VARCHAR[],
            metadata_json JSON,
            confidence FLOAT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP,
            promoted BOOLEAN,
            promoted_at TIMESTAMP
        )
        """
    )
    con.execute(
        """
        CREATE TABLE conversations (
            id INTEGER,
            conversation_id VARCHAR,
            agent_id VARCHAR,
            project_slug VARCHAR,
            session_type VARCHAR,
            model_used VARCHAR,
            tool_used VARCHAR,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            total_tokens INTEGER,
            summary VARCHAR,
            metadata_json JSON
        )
        """
    )
    con.execute(
        """
        CREATE TABLE conversation_turns (
            id INTEGER,
            conversation_id VARCHAR,
            turn_number INTEGER,
            role VARCHAR,
            content VARCHAR,
            tool_calls_json JSON,
            tokens_used INTEGER,
            latency_ms INTEGER,
            created_at TIMESTAMP
        )
        """
    )
    con.close()

    fts_path = tmp_path / "fts.duckdb"
    fts = duckdb.connect(str(fts_path))
    fts.execute("LOAD fts")
    fts.execute(
        """
        CREATE TABLE rag_chunks_fts (
            id INTEGER,
            content VARCHAR,
            source_path VARCHAR,
            chunk_type VARCHAR,
            project_slug VARCHAR
        )
        """
    )
    fts.execute(
        """
        INSERT INTO rag_chunks_fts
        VALUES (1, 'DuckDB catalog opens local parquet files for exact code retrieval', 'src/db.py', 'code', 'Braid')
        """
    )
    fts.execute("PRAGMA create_fts_index('rag_chunks_fts', 'id', 'content')")
    fts.close()

    return catalog, fts_path, tmp_path / "lancedb"


def test_hybrid_search_combines_fts_vector_graph_and_global_prompts(tmp_path: Path) -> None:
    catalog, fts_path, lancedb_path = _catalog(tmp_path)

    import lancedb

    db = lancedb.connect(str(lancedb_path))
    db.create_table(
        "rag_chunks",
        data=[
            {
                "vector": [1.0, 0.0],
                "content": "Semantic DuckDB retrieval through LanceDB",
                "source_path": "src/vector.py",
                "chunk_id": "v1",
            }
        ],
    )

    with BraidCatalog(catalog=catalog, fts_path=fts_path, lancedb_path=lancedb_path) as cat:
        cat.store_rag_chunk(
            "chunk-1",
            "Braid",
            "Braid",
            "DuckDB local global prompt source for the repository",
            source_path="src/db.py",
            chunk_index=0,
        )
        cat.store_kg_node(
            "node-db",
            "Class",
            "DuckDBCatalog",
            "Braid",
            description="DuckDB local retrieval pipeline",
            source_path="src/db.py",
            valid_from=datetime(2026, 1, 1),
            commit_sha="a" * 40,
        )
        cat.store_kg_node(
            "node-vector",
            "Function",
            "vector_search",
            "Braid",
            source_path="src/vector.py",
            valid_from=datetime(2026, 1, 1),
            commit_sha="a" * 40,
        )
        cat.store_kg_edge(
            "CALLS",
            "node-db",
            "node-vector",
            "Braid",
            valid_from=datetime(2026, 1, 1),
            commit_sha="a" * 40,
        )

        result = cat.hybrid_search(
            "DuckDB",
            project_slug="Braid",
            query_embedding=[1.0, 0.0],
            top_k=3,
            global_prompt_chars=1200,
        ).as_dict()

    assert result["sources"]["fts"]
    assert result["sources"]["vector"]
    assert result["sources"]["graph"]["edges"]
    assert result["sources"]["global_prompts"]


def test_versioned_graph_can_query_past_edges_after_compaction(tmp_path: Path) -> None:
    catalog, fts_path, lancedb_path = _catalog(tmp_path)
    t1 = datetime(2026, 1, 1)
    t2 = datetime(2026, 2, 1)

    with BraidCatalog(catalog=catalog, fts_path=fts_path, lancedb_path=lancedb_path) as cat:
        cat.store_kg_node("node-a", "Function", "a", "Braid", valid_from=t1, commit_sha="a" * 40)
        cat.store_kg_node("node-b", "Function", "b", "Braid", valid_from=t1, commit_sha="a" * 40)
        cat.store_kg_edge("CALLS", "node-a", "node-b", "Braid", valid_from=t1, commit_sha="a" * 40)

        assert cat.get_node_edges("node-a", project_slug="Braid", as_of=datetime(2026, 1, 15))

        cat.close_stale_graph_records(
            "Braid",
            active_node_ids=["node-a"],
            active_edges=[],
            valid_to=t2,
            commit_sha="b" * 40,
        )

        assert cat.get_node_edges("node-a", project_slug="Braid") == []
        historical = cat.get_node_edges("node-a", project_slug="Braid", as_of=datetime(2026, 1, 15))

    assert historical[0]["target"] == "node-b"
    assert historical[0]["valid_to"] == t2


def test_compact_memory_collapses_five_conversations_into_project_memory(tmp_path: Path) -> None:
    catalog, fts_path, lancedb_path = _catalog(tmp_path)

    with BraidCatalog(catalog=catalog, fts_path=fts_path, lancedb_path=lancedb_path) as cat:
        for idx in range(5):
            conversation_id = f"debug-{idx}"
            cat.store_conversation(
                conversation_id,
                "codex",
                project_slug="Braid",
                session_type="debugging",
                summary="debugging schema decision",
            )
            cat.store_conversation_turn(
                conversation_id,
                1,
                "assistant",
                f"decision fix schema migration path {idx}",
                tokens_used=10,
            )

        result = cat.compact_memory("Braid", min_conversations=5)
        rows = cat.search_project_memory(result["key"], project_slug="Braid")

    assert result["compacted"] is True
    assert result["source_turn_count"] == 5
    assert rows[0]["type"] == "compacted_decision"
