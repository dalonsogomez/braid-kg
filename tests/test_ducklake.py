"""Tests for BraidCatalog CRUD operations against an isolated DuckLake catalog."""
from __future__ import annotations

import pytest

from braid import ducklake as ducklake_mod
from braid.ducklake import BraidCatalog, open_catalog


@pytest.fixture(autouse=True)
def isolated_ducklake_catalog(ducklake_test_catalog, monkeypatch):
    """Redirect default BraidCatalog instances to a temp catalog."""
    temp_catalog, temp_fts_path, temp_lancedb_path = ducklake_test_catalog
    original_init = BraidCatalog.__init__

    def patched_init(
        self,
        catalog: str = ducklake_mod.DUCKLAKE_CATALOG,
        alias: str = ducklake_mod.DUCKLAKE_ALIAS,
        fts_path=None,
        lancedb_path=None,
        lancedb_table: str = "rag_chunks",
    ) -> None:
        if catalog == ducklake_mod.DUCKLAKE_CATALOG:
            catalog = temp_catalog
        if fts_path is None:
            fts_path = temp_fts_path
        if lancedb_path is None:
            lancedb_path = temp_lancedb_path
        original_init(
            self,
            catalog=catalog,
            alias=alias,
            fts_path=fts_path,
            lancedb_path=lancedb_path,
            lancedb_table=lancedb_table,
        )

    monkeypatch.setattr(BraidCatalog, "__init__", patched_init)


# ---------------------------------------------------------------------------
# Session Memory (Level 0)
# ---------------------------------------------------------------------------

class TestSessionMemory:
    def test_store_and_search(self):
        with BraidCatalog() as cat:
            sid = cat.store_session_memory(
                "test-session-1", "observation", "test_key", "test value for search",
                project_slug="Braid",
            )
            assert isinstance(sid, int)
            assert sid > 0

            results = cat.search_session_memory("test_key", session_id="test-session-1")
            assert len(results) >= 1
            assert any(r["key"] == "test_key" for r in results)

    def test_search_by_project(self):
        with BraidCatalog() as cat:
            cat.store_session_memory(
                "test-session-2", "note", "project_search_key", "value",
                project_slug="Braid",
            )
            results = cat.search_session_memory("project_search_key", project_slug="Braid")
            assert len(results) >= 1

    def test_search_empty_result(self):
        with BraidCatalog() as cat:
            results = cat.search_session_memory("nonexistent_key_xyz_12345")
            assert results == []


# ---------------------------------------------------------------------------
# Project Memory (Level 1)
# ---------------------------------------------------------------------------

class TestProjectMemory:
    def test_store_and_search(self):
        with BraidCatalog() as cat:
            sid = cat.store_project_memory(
                "Braid", "decision", "test_proj_key", "test project value",
                confidence=0.9,
            )
            assert isinstance(sid, int)
            assert sid > 0

            results = cat.search_project_memory("test_proj_key", project_slug="Braid")
            assert len(results) >= 1
            assert any(r["key"] == "test_proj_key" for r in results)

    def test_search_by_type(self):
        with BraidCatalog() as cat:
            cat.store_project_memory(
                "Braid", "convention", "test_type_key", "typed value",
            )
            results = cat.search_project_memory(
                "test_type_key", project_slug="Braid", memory_type="convention",
            )
            assert len(results) >= 1


# ---------------------------------------------------------------------------
# Global Memory (Level 2)
# ---------------------------------------------------------------------------

class TestGlobalMemory:
    def test_store_and_search(self):
        with BraidCatalog() as cat:
            sid = cat.store_global_memory(
                "preference", "test_global_key", "test global value",
                tags=["test"],
            )
            assert isinstance(sid, int)
            assert sid > 0

            results = cat.search_global_memory("test_global_key")
            assert len(results) >= 1


# ---------------------------------------------------------------------------
# Promotion
# ---------------------------------------------------------------------------

class TestPromotion:
    def test_session_to_project(self):
        with BraidCatalog() as cat:
            # Store session memory
            cat.store_session_memory(
                "promo-test-session", "finding", "promo_key", "promo value",
                project_slug="Braid",
            )
            # Promote
            pid = cat.promote_session_to_project(
                "promo-test-session", "finding", "promo_key", "promoted value",
                project_slug="Braid",
            )
            assert isinstance(pid, int)

            # Verify project memory exists
            results = cat.search_project_memory("promo_key", project_slug="Braid")
            assert any(r["key"] == "promo_key" for r in results)

    def test_project_to_global(self):
        with BraidCatalog() as cat:
            pid = cat.promote_project_to_global(
                "Braid", "global_promo_key", "global promoted value",
                memory_type="preference",
            )
            assert isinstance(pid, int)

            results = cat.search_global_memory("global_promo_key")
            assert len(results) >= 1


# ---------------------------------------------------------------------------
# Knowledge Graph
# ---------------------------------------------------------------------------

class TestKnowledgeGraph:
    def test_store_node_and_get_edges(self):
        with BraidCatalog() as cat:
            cat.store_kg_node("test-node-1", "Function", "test_func", "Braid")
            cat.store_kg_node("test-node-2", "Module", "test_mod", "Braid")
            # store_kg_edge signature: (edge_type, source_node_id, target_node_id, project_slug)
            cat.store_kg_edge("CONTAINS", "test-node-1", "test-node-2", "Braid")

            edges = cat.get_node_edges("test-node-1")
            assert len(edges) >= 1
            assert any(e["target"] == "test-node-2" for e in edges)

    def test_subgraph(self):
        with BraidCatalog() as cat:
            cat.store_kg_node("sg-node-1", "Function", "sg_func", "Braid")
            sub = cat.get_subgraph("sg-node-1", depth=1, project_slug="Braid")
            assert "nodes" in sub
            assert "edges" in sub


# ---------------------------------------------------------------------------
# ADRs
# ---------------------------------------------------------------------------

class TestADRs:
    def test_store_and_search(self):
        with BraidCatalog() as cat:
            cat.store_adr("9999", "Test ADR", "Active", "test context", "test decision")
            results = cat.search_adrs("Test ADR")
            assert len(results) >= 1

    def test_get_active_adrs(self):
        with BraidCatalog() as cat:
            cat.store_adr("9998", "Active Test ADR", "Active", "ctx", "decision")
            active = cat.get_active_adrs()
            assert isinstance(active, list)
            assert any(a["adr_id"] == "9998" for a in active)


# ---------------------------------------------------------------------------
# FTS (BM25)
# ---------------------------------------------------------------------------

class TestFTS:
    def test_fts_search(self):
        with BraidCatalog() as cat:
            if cat.fts_con is None:
                pytest.skip("FTS companion DB not available")
            hits = cat.fts_search("adrs_fts", "Ollama")
            # May return 0 if no data, but should not error
            assert isinstance(hits, list)


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

class TestMetadata:
    def test_set_and_get(self):
        with BraidCatalog() as cat:
            cat.set_metadata("test_meta_key", "test_meta_value")
            val = cat.get_metadata("test_meta_key")
            assert val == "test_meta_value"

    def test_get_nonexistent(self):
        with BraidCatalog() as cat:
            val = cat.get_metadata("nonexistent_key_xyz_12345")
            assert val is None


# ---------------------------------------------------------------------------
# Catalog summary
# ---------------------------------------------------------------------------

class TestCatalogSummary:
    def test_summary(self):
        with BraidCatalog() as cat:
            summary = cat.get_catalog_summary()
            assert "tables" in summary
            assert "total_rows" in summary
            assert "per_table" in summary
            assert summary["tables"] == 16


# ---------------------------------------------------------------------------
# open_catalog context manager
# ---------------------------------------------------------------------------

class TestOpenCatalog:
    def test_open_catalog(self):
        with open_catalog() as cat:
            summary = cat.get_catalog_summary()
            assert summary["tables"] == 16
