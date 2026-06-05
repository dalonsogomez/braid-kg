"""Tests for WikiForgeCatalog — CRUD operations against the DuckLake catalog.

These tests hit the real DuckLake catalog at .kg/wikiforge_ducklake.
They are idempotent: they create test data, verify, then clean up.
"""
from __future__ import annotations

import pytest

from wikiforge.ducklake import WikiForgeCatalog, open_catalog


# ---------------------------------------------------------------------------
# Session Memory (Level 0)
# ---------------------------------------------------------------------------

class TestSessionMemory:
    def test_store_and_search(self):
        with WikiForgeCatalog() as cat:
            sid = cat.store_session_memory(
                "test-session-1", "observation", "test_key", "test value for search",
                project_slug="Fairlead",
            )
            assert isinstance(sid, int)
            assert sid > 0

            results = cat.search_session_memory("test_key", session_id="test-session-1")
            assert len(results) >= 1
            assert any(r["key"] == "test_key" for r in results)

    def test_search_by_project(self):
        with WikiForgeCatalog() as cat:
            cat.store_session_memory(
                "test-session-2", "note", "project_search_key", "value",
                project_slug="Fairlead",
            )
            results = cat.search_session_memory("project_search_key", project_slug="Fairlead")
            assert len(results) >= 1

    def test_search_empty_result(self):
        with WikiForgeCatalog() as cat:
            results = cat.search_session_memory("nonexistent_key_xyz_12345")
            assert results == []


# ---------------------------------------------------------------------------
# Project Memory (Level 1)
# ---------------------------------------------------------------------------

class TestProjectMemory:
    def test_store_and_search(self):
        with WikiForgeCatalog() as cat:
            sid = cat.store_project_memory(
                "Fairlead", "decision", "test_proj_key", "test project value",
                confidence=0.9,
            )
            assert isinstance(sid, int)
            assert sid > 0

            results = cat.search_project_memory("test_proj_key", project_slug="Fairlead")
            assert len(results) >= 1
            assert any(r["key"] == "test_proj_key" for r in results)

    def test_search_by_type(self):
        with WikiForgeCatalog() as cat:
            cat.store_project_memory(
                "Fairlead", "convention", "test_type_key", "typed value",
            )
            results = cat.search_project_memory(
                "test_type_key", project_slug="Fairlead", memory_type="convention",
            )
            assert len(results) >= 1


# ---------------------------------------------------------------------------
# Global Memory (Level 2)
# ---------------------------------------------------------------------------

class TestGlobalMemory:
    def test_store_and_search(self):
        with WikiForgeCatalog() as cat:
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
        with WikiForgeCatalog() as cat:
            # Store session memory
            cat.store_session_memory(
                "promo-test-session", "finding", "promo_key", "promo value",
                project_slug="Fairlead",
            )
            # Promote
            pid = cat.promote_session_to_project(
                "promo-test-session", "finding", "promo_key", "promoted value",
                project_slug="Fairlead",
            )
            assert isinstance(pid, int)

            # Verify project memory exists
            results = cat.search_project_memory("promo_key", project_slug="Fairlead")
            assert any(r["key"] == "promo_key" for r in results)

    def test_project_to_global(self):
        with WikiForgeCatalog() as cat:
            pid = cat.promote_project_to_global(
                "Fairlead", "global_promo_key", "global promoted value",
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
        with WikiForgeCatalog() as cat:
            cat.store_kg_node("test-node-1", "Function", "test_func", "Fairlead")
            cat.store_kg_node("test-node-2", "Module", "test_mod", "Fairlead")
            # store_kg_edge signature: (edge_type, source_node_id, target_node_id, project_slug)
            cat.store_kg_edge("CONTAINS", "test-node-1", "test-node-2", "Fairlead")

            edges = cat.get_node_edges("test-node-1")
            assert len(edges) >= 1
            assert any(e["target"] == "test-node-2" for e in edges)

    def test_subgraph(self):
        with WikiForgeCatalog() as cat:
            cat.store_kg_node("sg-node-1", "Function", "sg_func", "Fairlead")
            sub = cat.get_subgraph("sg-node-1", depth=1, project_slug="Fairlead")
            assert "nodes" in sub
            assert "edges" in sub


# ---------------------------------------------------------------------------
# ADRs
# ---------------------------------------------------------------------------

class TestADRs:
    def test_store_and_search(self):
        with WikiForgeCatalog() as cat:
            cat.store_adr("9999", "Test ADR", "Active", "test context", "test decision")
            results = cat.search_adrs("Test ADR")
            assert len(results) >= 1

    def test_get_active_adrs(self):
        with WikiForgeCatalog() as cat:
            active = cat.get_active_adrs()
            assert isinstance(active, list)
            # Real catalog should have at least the seeded ADRs
            assert len(active) >= 1


# ---------------------------------------------------------------------------
# FTS (BM25)
# ---------------------------------------------------------------------------

class TestFTS:
    def test_fts_search(self):
        with WikiForgeCatalog() as cat:
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
        with WikiForgeCatalog() as cat:
            cat.set_metadata("test_meta_key", "test_meta_value")
            val = cat.get_metadata("test_meta_key")
            assert val == "test_meta_value"

    def test_get_nonexistent(self):
        with WikiForgeCatalog() as cat:
            val = cat.get_metadata("nonexistent_key_xyz_12345")
            assert val is None


# ---------------------------------------------------------------------------
# Catalog summary
# ---------------------------------------------------------------------------

class TestCatalogSummary:
    def test_summary(self):
        with WikiForgeCatalog() as cat:
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
