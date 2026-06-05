"""DuckLake integration for Braid — persistent catalog-based storage.

Provides a DuckDB-backed DuckLake catalog for structured memory, KG, RAG,
ADR tracking, and FTS search. Complements the existing Cognee/Kuzu/LanceDB
stack (AGENTS.md sec. 3) with SQL-queryable, ACID-transactional storage.

Architecture:
    - DuckLake catalog: ``ducklake:duckdb:braid`` (Parquet data files)
    - FTS companion DB: ``.braid/kg/braid_fts.duckdb`` (BM25 full-text search)
    - 16 tables across 10 domains (see SCHEMA_DOMAINS below)

DuckLake constraints (as of v0.1.1):
    - No sequences (use app-managed INTEGER IDs)
    - No PRIMARY KEY / UNIQUE constraints
    - No fixed-size FLOAT[N] arrays (use FLOAT[])
    - JSON, VARCHAR[], TIMESTAMP, DEFAULT all work

Usage:
    from braid.ducklake import BraidCatalog

    with BraidCatalog() as cat:
        # Memory operations
        cat.store_project_memory("Braid", "decision", "key", "value")
        results = cat.search_project_memory("stack")

        # ADR operations
        cat.store_adr("0013", "New Decision", "Active", "ctx", "dec")
        adrs = cat.search_adrs("Ollama")

        # KG operations
        cat.store_kg_node("node-1", "Function", "my_func", "Braid")
        edges = cat.get_node_edges("node-1")

        # FTS search (BM25)
        hits = cat.fts_search("project_memory_fts", "stack")
"""

from __future__ import annotations

import json
import hashlib
import subprocess
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

import duckdb

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DUCKLAKE_ALIAS = "braid"

FTS_TABLES = {
    "project_memory_fts",
    "global_memory_fts",
    "adrs_fts",
    "kg_nodes_fts",
    "rag_chunks_fts",
}


@dataclass(frozen=True)
class HybridSearchResult:
    """Structured result bundle for local/global retrieval."""

    query: str
    project_slug: str
    fts: list[dict[str, Any]]
    vector: list[dict[str, Any]]
    graph: dict[str, Any]
    global_prompts: list[dict[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "project_slug": self.project_slug,
            "sources": {
                "fts": self.fts,
                "vector": self.vector,
                "graph": self.graph,
                "global_prompts": self.global_prompts,
            },
        }


def _default_catalog_path() -> str:
    """Resolve the DuckLake catalog path from the project root.

    Uses resolve_context() to find the project root, then constructs
    the path to .braid/kg/braid_ducklake. Falls back to the current
    working directory if no project context is found.
    """
    try:
        from .paths import resolve_context
        ctx = resolve_context()
        return f"ducklake:duckdb:{ctx.kg_dir / 'braid_ducklake'}"
    except Exception:
        root = Path.cwd()
    return f"ducklake:duckdb:{root / '.braid' / 'kg' / 'braid_ducklake'}"


def _default_fts_path() -> Path:
    """Resolve the FTS companion DB path from the project root."""
    try:
        from .paths import resolve_context
        ctx = resolve_context()
        return ctx.kg_dir / "braid_fts.duckdb"
    except Exception:
        root = Path.cwd()
    return root / ".braid" / "kg" / "braid_fts.duckdb"


def _default_lancedb_path() -> Path:
    """Resolve the default embedded LanceDB path from the project root."""
    try:
        from .paths import resolve_context
        ctx = resolve_context()
        return ctx.rag_dir / "lancedb"
    except Exception:
        root = Path.cwd()
    return root / ".braid" / "rag" / "lancedb"


def _utc_naive(dt: datetime) -> datetime:
    """DuckDB TIMESTAMP columns are timezone-naive; normalize to UTC."""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


# Legacy constants for backward compatibility (used by tests and direct imports)
DUCKLAKE_CATALOG = _default_catalog_path()
FTS_DB_PATH = _default_fts_path()

SCHEMA_DOMAINS = [
    "session_memory", "project_memory", "global_memory",  # 3-level memory
    "kg_nodes", "kg_edges",                               # Knowledge graph
    "rag_chunks", "rag_search_cache",                      # RAG index
    "adrs",                                                # Architecture decisions
    "conversations", "conversation_turns",                  # Conversation tracking
    "eval_runs", "eval_answers",                            # Evaluation
    "ingested_files",                                       # Code ingesta
    "sync_log",                                            # Replication
    "agents",                                              # Agent registry
    "system_metadata",                                     # System config
]


# ---------------------------------------------------------------------------
# ID generation (app-managed, no sequences in DuckLake)
# ---------------------------------------------------------------------------

_next_id: dict[str, int] = {}


def _next_id_for(table: str, con: duckdb.DuckDBPyConnection) -> int:
    """Generate a monotonically increasing ID for a DuckLake table.

    Queries the current max id and increments. Not thread-safe across
    processes, but safe for single-agent sequential access.
    """
    if table not in _next_id:
        try:
            result = con.execute(
                f'SELECT COALESCE(MAX(id), 0) FROM {DUCKLAKE_ALIAS}.{table}'
            ).fetchone()
            _next_id[table] = (result[0] if result else 0) + 1
        except Exception:
            _next_id[table] = 1
    else:
        _next_id[table] += 1
    return _next_id[table]


# ---------------------------------------------------------------------------
# BraidCatalog
# ---------------------------------------------------------------------------

class BraidCatalog:
    """High-level interface to the Braid DuckLake catalog.

    Opens a DuckDB connection, loads required extensions, and attaches
    the DuckLake catalog. Supports context manager for clean teardown.

    Example::

        with BraidCatalog() as cat:
            cat.store_project_memory("Braid", "decision", "key", "val")
            rows = cat.search_project_memory("stack")
    """

    def __init__(
        self,
        catalog: str = DUCKLAKE_CATALOG,
        alias: str = DUCKLAKE_ALIAS,
        fts_path: Path | str | None = None,
        lancedb_path: Path | str | None = None,
        lancedb_table: str = "rag_chunks",
    ) -> None:
        self.catalog = catalog
        self.alias = alias
        self.fts_path = Path(fts_path) if fts_path else FTS_DB_PATH
        self.lancedb_path = Path(lancedb_path) if lancedb_path else _default_lancedb_path()
        self.lancedb_table = lancedb_table
        self._con: duckdb.DuckDBPyConnection | None = None
        self._fts_con: duckdb.DuckDBPyConnection | None = None
        self._git_cache: dict[str, Any] = {}

    # -- Context manager ---------------------------------------------------

    def __enter__(self) -> BraidCatalog:
        self.open()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # -- Connection management ---------------------------------------------

    def open(self) -> None:
        """Open DuckDB connection, load extensions, attach catalog."""
        self._con = duckdb.connect()
        con = self._con
        # Load only the extensions we need for DuckLake operations
        # Loading too many extensions (spatial, aws, iceberg, delta) changes
        # the catalog context and breaks DuckLake table resolution
        for ext in ("ducklake", "json", "fts"):
            try:
                con.execute(f"LOAD {ext}")
            except Exception:
                pass  # Extension might not be available
        # Attach DuckLake catalog
        con.execute(f"ATTACH '{self.catalog}' AS {self.alias}")
        # Set catalog context
        con.execute(f"USE {self.alias}")
        # Attach FTS companion DB if it exists
        if self.fts_path.exists():
            self._fts_con = duckdb.connect(str(self.fts_path))
            self._fts_con.execute("LOAD fts")

    def close(self) -> None:
        """Close all connections."""
        if self._con:
            self._con.close()
            self._con = None
        if self._fts_con:
            self._fts_con.close()
            self._fts_con = None

    @property
    def con(self) -> duckdb.DuckDBPyConnection:
        if self._con is None:
            raise RuntimeError("Catalog not open. Use 'with BraidCatalog() as cat:' or call .open()")
        return self._con

    @property
    def fts_con(self) -> duckdb.DuckDBPyConnection | None:
        return self._fts_con

    # -- Utility -----------------------------------------------------------

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _ensure_catalog_context(self) -> None:
        """Ensure we're in the DuckLake catalog context."""
        self.con.execute(f"USE {self.alias}")

    def _q(self, sql: str) -> list[tuple[Any, ...]]:
        """Execute a query and return all rows. Uses catalog context."""
        self._ensure_catalog_context()
        return self.con.execute(sql).fetchall()

    def _x(self, sql: str) -> None:
        """Execute a statement (no return). Uses catalog context."""
        self._ensure_catalog_context()
        self.con.execute(sql)

    def _query(self, sql: str, params: Sequence[Any] | None = None) -> list[tuple[Any, ...]]:
        """Execute a parameterized query and return all rows."""
        self._ensure_catalog_context()
        return self.con.execute(sql, list(params or [])).fetchall()

    def _execute(self, sql: str, params: Sequence[Any] | None = None) -> None:
        """Execute a parameterized statement."""
        self._ensure_catalog_context()
        self.con.execute(sql, list(params or []))

    def _table_columns(self, table: str) -> set[str]:
        rows = self._query(
            "SELECT column_name FROM duckdb_columns() WHERE table_name = ?",
            [table],
        )
        return {str(r[0]) for r in rows}

    def _git_root(self) -> Path | None:
        if "root" in self._git_cache:
            return self._git_cache["root"]
        try:
            from .paths import resolve_context
            root = resolve_context().root
            if (root / ".git").exists():
                self._git_cache["root"] = root
                return root
        except Exception:
            pass
        self._git_cache["root"] = None
        return None

    def _git_output(self, args: list[str]) -> str | None:
        root = self._git_root()
        if root is None:
            return None
        try:
            return subprocess.check_output(
                ["git", "-C", str(root), *args],
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

    def _current_commit_sha(self) -> str | None:
        if "head_sha" not in self._git_cache:
            self._git_cache["head_sha"] = self._git_output(["rev-parse", "HEAD"])
        return self._git_cache["head_sha"]

    def _commit_timestamp(self, commit_sha: str | None) -> datetime | None:
        if not commit_sha:
            return None
        cache_key = f"commit_ts:{commit_sha}"
        if cache_key in self._git_cache:
            return self._git_cache[cache_key]
        raw = self._git_output(["show", "-s", "--format=%cI", commit_sha])
        if raw is None:
            self._git_cache[cache_key] = None
            return None
        try:
            ts = _utc_naive(datetime.fromisoformat(raw.replace("Z", "+00:00")))
        except ValueError:
            ts = None
        self._git_cache[cache_key] = ts
        return ts

    def _version_context(
        self,
        valid_from: datetime | None = None,
        commit_sha: str | None = None,
    ) -> tuple[datetime, str | None]:
        resolved_sha = commit_sha if commit_sha is not None else self._current_commit_sha()
        resolved_from = valid_from or self._commit_timestamp(resolved_sha) or self._now()
        return _utc_naive(resolved_from), resolved_sha

    def ensure_versioned_graph_schema(self) -> None:
        """Add temporal graph columns required for versioned memory.

        DuckLake supports ALTER TABLE, so this is safe to run repeatedly on
        existing catalogs. Existing rows are backfilled from created_at when
        available and otherwise from the current UTC timestamp.
        """
        for table in ("kg_nodes", "kg_edges"):
            columns = self._table_columns(table)
            for col_name, col_type in (
                ("valid_from", "TIMESTAMP"),
                ("valid_to", "TIMESTAMP"),
                ("commit_sha", "VARCHAR"),
            ):
                if col_name not in columns:
                    self._execute(f"ALTER TABLE {self.alias}.{table} ADD COLUMN {col_name} {col_type}")
                    columns.add(col_name)

            if "valid_from" in columns:
                if "created_at" in columns:
                    try:
                        self._execute(
                            f"UPDATE {self.alias}.{table} "
                            "SET valid_from = created_at WHERE valid_from IS NULL AND created_at IS NOT NULL"
                        )
                    except Exception:
                        pass
                try:
                    self._execute(
                        f"UPDATE {self.alias}.{table} SET valid_from = ? WHERE valid_from IS NULL",
                        [_utc_naive(self._now())],
                    )
                except Exception:
                    pass

    def _version_filter(
        self,
        table: str,
        alias: str,
        as_of_commit: str | None = None,
        as_of: datetime | None = None,
        active_only: bool = True,
    ) -> tuple[str, list[Any]]:
        columns = self._table_columns(table)
        if "valid_from" not in columns or "valid_to" not in columns:
            return "", []

        if as_of_commit:
            commit_ts = self._commit_timestamp(as_of_commit)
            if commit_ts is None:
                if "commit_sha" in columns:
                    return f" AND {alias}.commit_sha = ?", [as_of_commit]
                return "", []
            as_of = commit_ts

        if as_of is not None:
            ts = _utc_naive(as_of)
            return (
                f" AND ({alias}.valid_from IS NULL OR {alias}.valid_from <= ?) "
                f"AND ({alias}.valid_to IS NULL OR {alias}.valid_to > ?)",
                [ts, ts],
            )

        if active_only:
            return f" AND {alias}.valid_to IS NULL", []
        return "", []

    # ======================================================================
    # 1. MEMORY OPERATIONS (3-level model)
    # ======================================================================

    # -- Session Memory (Level 0) ------------------------------------------

    def store_session_memory(
        self,
        session_id: str,
        memory_type: str,
        key: str,
        value: str,
        agent_id: str = "default",
        project_slug: str | None = None,
        metadata: dict | None = None,
    ) -> int:
        """Store a session-level memory entry."""
        _id = _next_id_for("session_memory", self.con)
        meta_json = json.dumps(metadata) if metadata else "NULL"
        self._x(
            f"INSERT INTO {self.alias}.session_memory "
            f"(id, session_id, agent_id, project_slug, memory_type, key, value, metadata_json) "
            f"VALUES ({_id}, '{session_id}', '{agent_id}', "
            f"{'NULL' if project_slug is None else f"'{project_slug}'"}, "
            f"'{memory_type}', '{key}', '{value}', {meta_json})"
        )
        return _id

    def search_session_memory(
        self,
        query: str,
        session_id: str | None = None,
        agent_id: str | None = None,
        project_slug: str | None = None,
    ) -> list[dict]:
        """Search session-level memory by text query."""
        where = []
        if session_id:
            where.append(f"session_id = '{session_id}'")
        if agent_id:
            where.append(f"agent_id = '{agent_id}'")
        if project_slug:
            where.append(f"project_slug = '{project_slug}'")
        where.append(f"(key LIKE '%{query}%' OR value LIKE '%{query}%')")
        where_clause = " AND ".join(where)
        rows = self._q(
            f"SELECT id, session_id, agent_id, project_slug, memory_type, key, value, promoted "
            f"FROM {self.alias}.session_memory WHERE {where_clause} ORDER BY created_at DESC"
        )
        return [
            {"id": r[0], "session_id": r[1], "agent_id": r[2], "project": r[3],
             "type": r[4], "key": r[5], "value": r[6], "promoted": r[7]}
            for r in rows
        ]

    def promote_session_to_project(
        self, session_id: str, memory_type: str, key: str, value: str,
        project_slug: str, adr_id: str | None = None, tags: list[str] | None = None,
        confidence: float = 1.0,
    ) -> int:
        """Promote a session memory to project level (AGENTS.md sec. 4.2 — explicit only)."""
        _id = _next_id_for("project_memory", self.con)
        tags_sql = str(tags) if tags else "NULL"
        self._x(
            f"INSERT INTO {self.alias}.project_memory "
            f"(id, project_slug, memory_type, key, value, adr_id, tags, confidence) "
            f"VALUES ({_id}, '{project_slug}', '{memory_type}', '{key}', '{value}', "
            f"{'NULL' if adr_id is None else f"'{adr_id}'"}, {tags_sql}, {confidence})"
        )
        # Mark session memory as promoted
        self._x(
            f"UPDATE {self.alias}.session_memory SET promoted = true, promoted_at = now() "
            f"WHERE session_id = '{session_id}' AND key = '{key}'"
        )
        return _id

    # -- Project Memory (Level 1) ------------------------------------------

    def store_project_memory(
        self,
        project_slug: str,
        memory_type: str,
        key: str,
        value: str,
        source_path: str | None = None,
        adr_id: str | None = None,
        tags: list[str] | None = None,
        confidence: float = 1.0,
        metadata: dict | None = None,
    ) -> int:
        """Store a project-level memory entry."""
        _id = _next_id_for("project_memory", self.con)
        meta_json = json.dumps(metadata, ensure_ascii=False) if metadata else None
        self._execute(
            f"INSERT INTO {self.alias}.project_memory "
            f"(id, project_slug, memory_type, key, value, source_path, adr_id, tags, confidence, metadata_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [_id, project_slug, memory_type, key, value, source_path, adr_id, tags, confidence, meta_json],
        )
        return _id

    def search_project_memory(
        self, query: str, project_slug: str | None = None, memory_type: str | None = None,
    ) -> list[dict]:
        """Search project memory using SQL LIKE (DuckLake doesn't support FTS directly)."""
        where = []
        if project_slug:
            where.append(f"project_slug = '{project_slug}'")
        if memory_type:
            where.append(f"memory_type = '{memory_type}'")
        where.append(f"(key LIKE '%{query}%' OR value LIKE '%{query}%')")
        where_clause = " AND ".join(where)
        rows = self._q(
            f"SELECT id, project_slug, memory_type, key, value, adr_id, confidence "
            f"FROM {self.alias}.project_memory WHERE {where_clause} ORDER BY confidence DESC"
        )
        return [
            {"id": r[0], "project": r[1], "type": r[2], "key": r[3], "value": r[4], "adr": r[5], "confidence": r[6]}
            for r in rows
        ]

    def promote_project_to_global(
        self, project_slug: str, key: str, value: str,
        memory_type: str, tags: list[str] | None = None,
    ) -> int:
        """Promote a project memory to global level (AGENTS.md sec. 4.2 — explicit only)."""
        _id = _next_id_for("global_memory", self.con)
        tags_sql = str(tags) if tags else "NULL"
        self._x(
            f"INSERT INTO {self.alias}.global_memory "
            f"(id, memory_type, key, value, tags) "
            f"VALUES ({_id}, '{memory_type}', '{key}', '{value}', {tags_sql})"
        )
        self._x(
            f"UPDATE {self.alias}.project_memory SET promoted = true, promoted_at = now() "
            f"WHERE project_slug = '{project_slug}' AND key = '{key}'"
        )
        return _id

    # -- Global Memory (Level 2) -------------------------------------------

    def store_global_memory(
        self,
        memory_type: str,
        key: str,
        value: str,
        tags: list[str] | None = None,
        applies_to: list[str] | None = None,
    ) -> int:
        """Store a global-level memory entry."""
        _id = _next_id_for("global_memory", self.con)
        tags_sql = str(tags) if tags else "NULL"
        applies_sql = str(applies_to) if applies_to else "NULL"
        self._x(
            f"INSERT INTO {self.alias}.global_memory "
            f"(id, memory_type, key, value, tags, applies_to) "
            f"VALUES ({_id}, '{memory_type}', '{key}', '{value}', {tags_sql}, {applies_sql})"
        )
        return _id

    def search_global_memory(self, query: str, memory_type: str | None = None) -> list[dict]:
        """Search global memory."""
        where = [f"(key LIKE '%{query}%' OR value LIKE '%{query}%')"]
        if memory_type:
            where.append(f"memory_type = '{memory_type}'")
        where_clause = " AND ".join(where)
        rows = self._q(
            f"SELECT id, memory_type, key, value, tags FROM {self.alias}.global_memory "
            f"WHERE {where_clause}"
        )
        return [
            {"id": r[0], "type": r[1], "key": r[2], "value": r[3], "tags": r[4]}
            for r in rows
        ]

    # ======================================================================
    # 2. KNOWLEDGE GRAPH OPERATIONS
    # ======================================================================

    def store_kg_node(
        self,
        node_id: str,
        node_type: str,
        name: str,
        project_slug: str,
        description: str | None = None,
        source_path: str | None = None,
        line_number: int | None = None,
        language: str | None = None,
        metadata: dict | None = None,
        valid_from: datetime | None = None,
        valid_to: datetime | None = None,
        commit_sha: str | None = None,
    ) -> int:
        """Store a knowledge graph node."""
        self.ensure_versioned_graph_schema()
        resolved_from, resolved_sha = self._version_context(valid_from, commit_sha)
        resolved_to = _utc_naive(valid_to) if valid_to else None

        if resolved_sha is not None:
            self._execute(
                f"UPDATE {self.alias}.kg_nodes SET valid_to = ? "
                "WHERE node_id = ? AND project_slug = ? AND valid_to IS NULL "
                "AND (commit_sha IS NULL OR commit_sha <> ?)",
                [resolved_from, node_id, project_slug, resolved_sha],
            )

        _id = _next_id_for("kg_nodes", self.con)
        meta_json = json.dumps(metadata, ensure_ascii=False) if metadata else None
        self._execute(
            f"INSERT INTO {self.alias}.kg_nodes "
            "(id, node_id, node_type, name, description, project_slug, source_path, line_number, "
            "language, metadata_json, valid_from, valid_to, commit_sha) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                _id,
                node_id,
                node_type,
                name,
                description,
                project_slug,
                source_path,
                line_number,
                language,
                meta_json,
                resolved_from,
                resolved_to,
                resolved_sha,
            ],
        )
        return _id

    def store_kg_edge(
        self,
        edge_type: str,
        source_node_id: str,
        target_node_id: str,
        project_slug: str,
        weight: float = 1.0,
        metadata: dict | None = None,
        valid_from: datetime | None = None,
        valid_to: datetime | None = None,
        commit_sha: str | None = None,
    ) -> int:
        """Store a knowledge graph edge."""
        self.ensure_versioned_graph_schema()
        resolved_from, resolved_sha = self._version_context(valid_from, commit_sha)
        resolved_to = _utc_naive(valid_to) if valid_to else None

        if resolved_sha is not None:
            self._execute(
                f"UPDATE {self.alias}.kg_edges SET valid_to = ? "
                "WHERE edge_type = ? AND source_node_id = ? AND target_node_id = ? "
                "AND project_slug = ? AND valid_to IS NULL "
                "AND (commit_sha IS NULL OR commit_sha <> ?)",
                [resolved_from, edge_type, source_node_id, target_node_id, project_slug, resolved_sha],
            )

        _id = _next_id_for("kg_edges", self.con)
        meta_json = json.dumps(metadata, ensure_ascii=False) if metadata else None
        self._execute(
            f"INSERT INTO {self.alias}.kg_edges "
            "(id, edge_type, source_node_id, target_node_id, project_slug, weight, metadata_json, "
            "valid_from, valid_to, commit_sha) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                _id,
                edge_type,
                source_node_id,
                target_node_id,
                project_slug,
                weight,
                meta_json,
                resolved_from,
                resolved_to,
                resolved_sha,
            ],
        )
        return _id

    def get_node_edges(
        self,
        node_id: str,
        project_slug: str | None = None,
        as_of_commit: str | None = None,
        as_of: datetime | None = None,
        include_historical: bool = False,
    ) -> list[dict]:
        """Get all edges connected to a node (both incoming and outgoing)."""
        self.ensure_versioned_graph_schema()
        where = ["(source_node_id = ? OR target_node_id = ?)"]
        params: list[Any] = [node_id, node_id]
        if project_slug:
            where.append("project_slug = ?")
            params.append(project_slug)
        version_sql, version_params = self._version_filter(
            "kg_edges",
            "kg_edges",
            as_of_commit=as_of_commit,
            as_of=as_of,
            active_only=not include_historical,
        )
        where_clause = " AND ".join(where)
        rows = self._query(
            f"SELECT edge_type, source_node_id, target_node_id, weight, valid_from, valid_to, commit_sha "
            f"FROM {self.alias}.kg_edges WHERE {where_clause}{version_sql}",
            [*params, *version_params],
        )
        return [
            {
                "type": r[0],
                "source": r[1],
                "target": r[2],
                "weight": r[3],
                "valid_from": r[4],
                "valid_to": r[5],
                "commit_sha": r[6],
            }
            for r in rows
        ]

    def get_subgraph(
        self,
        node_id: str,
        depth: int = 1,
        project_slug: str | None = None,
        as_of_commit: str | None = None,
        as_of: datetime | None = None,
        include_historical: bool = False,
    ) -> dict:
        """Get a subgraph starting from a node, up to the requested depth."""
        visited_nodes: set[str] = set()
        visited_edges: list[dict] = []
        current_frontier = {node_id}

        for _ in range(depth):
            next_frontier: set[str] = set()
            for nid in current_frontier:
                if nid in visited_nodes:
                    continue
                visited_nodes.add(nid)
                edges = self.get_node_edges(
                    nid,
                    project_slug,
                    as_of_commit=as_of_commit,
                    as_of=as_of,
                    include_historical=include_historical,
                )
                for e in edges:
                    visited_edges.append(e)
                    if e["source"] not in visited_nodes:
                        next_frontier.add(e["source"])
                    if e["target"] not in visited_nodes:
                        next_frontier.add(e["target"])
            current_frontier = next_frontier
            if not current_frontier:
                break

        # Fetch node details
        nodes = []
        if visited_nodes:
            ids_list = ", ".join("?" for _ in visited_nodes)
            rows = self._query(
                f"SELECT node_id, node_type, name, description, source_path "
                f"FROM {self.alias}.kg_nodes WHERE node_id IN ({ids_list})",
                list(visited_nodes),
            )
            nodes = [
                {"id": r[0], "type": r[1], "name": r[2], "desc": r[3], "path": r[4]}
                for r in rows
            ]

        return {"nodes": nodes, "edges": visited_edges}

    def graph_impact_search(
        self,
        query: str,
        project_slug: str | None = None,
        depth: int = 1,
        direction: str = "both",
        limit: int = 25,
        as_of_commit: str | None = None,
        as_of: datetime | None = None,
    ) -> dict[str, Any]:
        """Find local dependency context using DuckDB joins over graph tables."""
        self.ensure_versioned_graph_schema()
        project_slug = project_slug or self._default_project_slug()
        depth = max(1, min(depth, 3))
        direction = direction if direction in {"upstream", "downstream", "both"} else "both"

        like = f"%{query.lower()}%"
        node_version_sql, node_version_params = self._version_filter(
            "kg_nodes",
            "n",
            as_of_commit=as_of_commit,
            as_of=as_of,
        )
        seed_rows = self._query(
            f"""
            SELECT n.node_id, n.node_type, n.name, n.source_path, n.description
            FROM {self.alias}.kg_nodes n
            WHERE n.project_slug = ?
              AND (
                lower(n.node_id) LIKE ?
                OR lower(n.name) LIKE ?
                OR lower(COALESCE(n.source_path, '')) LIKE ?
                OR lower(COALESCE(n.description, '')) LIKE ?
              )
              {node_version_sql}
            LIMIT ?
            """,
            [project_slug, like, like, like, like, *node_version_params, limit],
        )
        seeds = [
            {
                "id": r[0],
                "type": r[1],
                "name": r[2],
                "path": r[3],
                "description": r[4],
            }
            for r in seed_rows
        ]
        frontier = {str(s["id"]) for s in seeds}
        edges: list[dict[str, Any]] = []
        nodes: dict[str, dict[str, Any]] = {str(s["id"]): s for s in seeds}
        seen_edges: set[tuple[str, str, str]] = set()

        for _ in range(depth):
            if not frontier or len(edges) >= limit:
                break
            placeholders = ", ".join("?" for _ in frontier)
            frontier_values = list(frontier)
            if direction == "downstream":
                edge_predicate = f"e.source_node_id IN ({placeholders})"
                edge_params = frontier_values
            elif direction == "upstream":
                edge_predicate = f"e.target_node_id IN ({placeholders})"
                edge_params = frontier_values
            else:
                edge_predicate = f"(e.source_node_id IN ({placeholders}) OR e.target_node_id IN ({placeholders}))"
                edge_params = [*frontier_values, *frontier_values]

            edge_version_sql, edge_version_params = self._version_filter(
                "kg_edges",
                "e",
                as_of_commit=as_of_commit,
                as_of=as_of,
            )
            rows = self._query(
                f"""
                SELECT
                    e.edge_type,
                    e.source_node_id,
                    e.target_node_id,
                    e.weight,
                    e.valid_from,
                    e.valid_to,
                    e.commit_sha,
                    src.node_type AS source_type,
                    src.name AS source_name,
                    src.source_path AS source_path,
                    dst.node_type AS target_type,
                    dst.name AS target_name,
                    dst.source_path AS target_path
                FROM {self.alias}.kg_edges e
                LEFT JOIN {self.alias}.kg_nodes src
                    ON src.node_id = e.source_node_id AND src.project_slug = e.project_slug
                LEFT JOIN {self.alias}.kg_nodes dst
                    ON dst.node_id = e.target_node_id AND dst.project_slug = e.project_slug
                WHERE e.project_slug = ?
                  AND {edge_predicate}
                  {edge_version_sql}
                LIMIT ?
                """,
                [project_slug, *edge_params, *edge_version_params, limit - len(edges)],
            )

            next_frontier: set[str] = set()
            for r in rows:
                edge_key = (str(r[0]), str(r[1]), str(r[2]))
                if edge_key in seen_edges:
                    continue
                seen_edges.add(edge_key)
                edge = {
                    "type": r[0],
                    "source": r[1],
                    "target": r[2],
                    "weight": r[3],
                    "valid_from": r[4],
                    "valid_to": r[5],
                    "commit_sha": r[6],
                    "source_name": r[8],
                    "source_path": r[9],
                    "target_name": r[11],
                    "target_path": r[12],
                }
                edges.append(edge)
                nodes[str(r[1])] = {
                    "id": r[1],
                    "type": r[7],
                    "name": r[8],
                    "path": r[9],
                }
                nodes[str(r[2])] = {
                    "id": r[2],
                    "type": r[10],
                    "name": r[11],
                    "path": r[12],
                }
                if str(r[1]) not in frontier:
                    next_frontier.add(str(r[1]))
                if str(r[2]) not in frontier:
                    next_frontier.add(str(r[2]))
            frontier = next_frontier

        return {
            "query": query,
            "project_slug": project_slug,
            "direction": direction,
            "depth": depth,
            "seeds": seeds,
            "nodes": list(nodes.values()),
            "edges": edges,
        }

    def close_stale_graph_records(
        self,
        project_slug: str,
        active_node_ids: Sequence[str] | None = None,
        active_edges: Sequence[tuple[str, str, str]] | None = None,
        commit_sha: str | None = None,
        valid_to: datetime | None = None,
    ) -> dict[str, int]:
        """Expire active graph facts that were not observed in the latest index pass."""
        self.ensure_versioned_graph_schema()
        resolved_to, resolved_sha = self._version_context(valid_to, commit_sha)
        counts = {"nodes_closed": 0, "edges_closed": 0}

        if active_node_ids is not None:
            node_ids = list(active_node_ids)
            if node_ids:
                placeholders = ", ".join("?" for _ in node_ids)
                params: list[Any] = [resolved_to, project_slug, *node_ids]
                cursor = self.con.execute(
                    f"""
                    UPDATE {self.alias}.kg_nodes
                    SET valid_to = ?
                    WHERE project_slug = ?
                      AND valid_to IS NULL
                      AND node_id NOT IN ({placeholders})
                    """,
                    params,
                )
            else:
                cursor = self.con.execute(
                    f"""
                    UPDATE {self.alias}.kg_nodes
                    SET valid_to = ?
                    WHERE project_slug = ? AND valid_to IS NULL
                    """,
                    [resolved_to, project_slug],
                )
            counts["nodes_closed"] = max(cursor.rowcount, 0)

        if active_edges is not None:
            keep = set(active_edges)
            active_rows = self._query(
                f"""
                SELECT edge_type, source_node_id, target_node_id
                FROM {self.alias}.kg_edges
                WHERE project_slug = ? AND valid_to IS NULL
                """,
                [project_slug],
            )
            for edge_type, source_node_id, target_node_id in active_rows:
                edge_key = (str(edge_type), str(source_node_id), str(target_node_id))
                if edge_key in keep:
                    continue
                cursor = self.con.execute(
                    f"""
                    UPDATE {self.alias}.kg_edges
                    SET valid_to = ?
                    WHERE project_slug = ?
                      AND edge_type = ?
                      AND source_node_id = ?
                      AND target_node_id = ?
                      AND valid_to IS NULL
                    """,
                    [resolved_to, project_slug, edge_type, source_node_id, target_node_id],
                )
                counts["edges_closed"] += max(cursor.rowcount, 0)

        self._git_cache["head_sha"] = resolved_sha
        return counts

    def _default_project_slug(self) -> str:
        try:
            from .paths import resolve_context
            return resolve_context().dataset_id
        except Exception:
            return "Braid"

    # ======================================================================
    # 2b. HYBRID LOCAL/GLOBAL RETRIEVAL
    # ======================================================================

    def vector_search(
        self,
        query: str,
        query_embedding: Sequence[float] | None = None,
        embedding_fn: Callable[[str], Sequence[float]] | None = None,
        limit: int = 5,
        table_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search embedded LanceDB vectors when a query embedding is available."""
        if query_embedding is None and embedding_fn is not None:
            query_embedding = embedding_fn(query)
        if query_embedding is None:
            return []

        try:
            import lancedb
        except Exception:
            return []

        if not self.lancedb_path.exists():
            return []

        try:
            db = lancedb.connect(str(self.lancedb_path))
            if hasattr(db, "list_tables"):
                table_listing = db.list_tables()
                names = set(getattr(table_listing, "tables", table_listing))
            else:
                names = set(db.table_names())
            selected_table = table_name or self.lancedb_table
            if selected_table not in names:
                fallback = next((name for name in ("rag_chunks", "chunks", "documents") if name in names), None)
                if fallback is None:
                    return []
                selected_table = fallback
            table = db.open_table(selected_table)
            rows = table.search(list(query_embedding)).limit(limit).to_list()
        except Exception:
            return []

        hits: list[dict[str, Any]] = []
        for row in rows:
            text = row.get("content") or row.get("text") or row.get("chunk") or ""
            hits.append(
                {
                    "source": f"lancedb:{selected_table}",
                    "text": text,
                    "score": row.get("_distance"),
                    "source_path": row.get("source_path") or row.get("path"),
                    "chunk_id": row.get("chunk_id") or row.get("id"),
                    "metadata": {k: v for k, v in row.items() if k not in {"vector", "content", "text", "chunk"}},
                }
            )
        return hits

    def build_global_rag_prompts(
        self,
        query: str | None = None,
        project_slug: str | None = None,
        max_chars: int = 12000,
        max_batches: int = 8,
    ) -> list[dict[str, Any]]:
        """Aggregate repo context into bounded prompt batches for Global RAG."""
        project_slug = project_slug or self._default_project_slug()
        docs: list[dict[str, Any]] = []

        try:
            rows = self._query(
                f"""
                SELECT
                    COALESCE(source_path, '<unknown>') AS source_path,
                    COALESCE(chunk_type, 'chunk') AS chunk_type,
                    COUNT(*) AS chunk_count,
                    string_agg(content, '\n\n' ORDER BY COALESCE(chunk_index, 0)) AS body
                FROM {self.alias}.rag_chunks
                WHERE project_slug = ?
                GROUP BY source_path, chunk_type
                ORDER BY source_path
                """,
                [project_slug],
            )
            docs.extend(
                {
                    "source_path": r[0],
                    "kind": r[1],
                    "count": r[2],
                    "body": r[3] or "",
                }
                for r in rows
            )
        except Exception:
            pass

        if not docs:
            try:
                rows = self._query(
                    f"""
                    SELECT
                        COALESCE(source_path, '<kg>') AS source_path,
                        'kg_nodes' AS chunk_type,
                        COUNT(*) AS node_count,
                        string_agg(node_type || ': ' || name, '\n' ORDER BY name) AS body
                    FROM {self.alias}.kg_nodes
                    WHERE project_slug = ?
                    GROUP BY source_path
                    ORDER BY source_path
                    """,
                    [project_slug],
                )
                docs.extend(
                    {
                        "source_path": r[0],
                        "kind": r[1],
                        "count": r[2],
                        "body": r[3] or "",
                    }
                    for r in rows
                )
            except Exception:
                pass

        batches: list[dict[str, Any]] = []
        current_blocks: list[str] = []
        current_paths: list[str] = []
        current_size = 0
        header = (
            f"Global RAG repository summary batch for project {project_slug}.\n"
            f"User query: {query or '(repo-wide synthesis)'}\n"
            "Summarize architecture, important dependencies, and decisions from these local sources.\n\n"
        )

        def flush() -> None:
            nonlocal current_blocks, current_paths, current_size
            if not current_blocks or len(batches) >= max_batches:
                current_blocks = []
                current_paths = []
                current_size = 0
                return
            prompt = header + "\n\n".join(current_blocks)
            batches.append(
                {
                    "batch_id": len(batches) + 1,
                    "prompt": prompt,
                    "source_paths": current_paths,
                    "char_count": len(prompt),
                }
            )
            current_blocks = []
            current_paths = []
            current_size = 0

        body_budget = max(1000, max_chars - len(header))
        for doc in docs:
            if len(batches) >= max_batches:
                break
            body = str(doc["body"])
            block_prefix = f"### {doc['source_path']} ({doc['kind']}, {doc['count']} items)\n"
            remaining = body
            while remaining and len(batches) < max_batches:
                available = max(1, body_budget - len(block_prefix))
                piece, remaining = remaining[:available], remaining[available:]
                block = block_prefix + piece
                if current_blocks and current_size + len(block) > body_budget:
                    flush()
                current_blocks.append(block)
                current_paths.append(str(doc["source_path"]))
                current_size += len(block)
                if remaining:
                    flush()
        flush()
        return batches

    def hybrid_search(
        self,
        query: str,
        project_slug: str | None = None,
        top_k: int = 5,
        query_embedding: Sequence[float] | None = None,
        embedding_fn: Callable[[str], Sequence[float]] | None = None,
        graph_depth: int = 1,
        as_of_commit: str | None = None,
        include_global_prompts: bool = True,
        global_prompt_chars: int = 12000,
    ) -> HybridSearchResult:
        """Run BM25, LanceDB semantic search, graph impact search, and Global RAG batching."""
        project_slug = project_slug or self._default_project_slug()

        fts_hits: list[dict[str, Any]] = []
        if self.fts_con is not None:
            for table in ("rag_chunks_fts", "kg_nodes_fts", "adrs_fts", "project_memory_fts"):
                for hit in self.fts_search(table, query, limit=top_k):
                    if "error" in hit:
                        continue
                    fts_hits.append(self._normalize_fts_hit(table, hit))
        fts_hits.sort(key=lambda h: float(h.get("score") or 0), reverse=True)

        vector_hits = self.vector_search(
            query,
            query_embedding=query_embedding,
            embedding_fn=embedding_fn,
            limit=top_k,
        )
        try:
            graph = self.graph_impact_search(
                query,
                project_slug=project_slug,
                depth=graph_depth,
                limit=top_k * 3,
                as_of_commit=as_of_commit,
            )
        except Exception as e:
            graph = {"query": query, "project_slug": project_slug, "nodes": [], "edges": [], "error": str(e)}
        try:
            prompts = (
                self.build_global_rag_prompts(
                    query=query,
                    project_slug=project_slug,
                    max_chars=global_prompt_chars,
                    max_batches=top_k,
                )
                if include_global_prompts
                else []
            )
        except Exception:
            prompts = []

        return HybridSearchResult(
            query=query,
            project_slug=project_slug,
            fts=fts_hits[:top_k],
            vector=vector_hits[:top_k],
            graph=graph,
            global_prompts=prompts,
        )

    def _normalize_fts_hit(self, table: str, hit: dict[str, Any]) -> dict[str, Any]:
        text = (
            hit.get("content")
            or hit.get("value")
            or hit.get("decision")
            or hit.get("description")
            or hit.get("title")
            or hit.get("name")
            or ""
        )
        return {
            "source": f"ducklake:{table}",
            "text": str(text),
            "score": hit.get("score"),
            "source_path": hit.get("source_path") or hit.get("file_path"),
            "id": hit.get("id") or hit.get("chunk_id") or hit.get("node_id") or hit.get("adr_id"),
            "raw": hit,
        }

    # ======================================================================
    # 3. ADR OPERATIONS
    # ======================================================================

    def store_adr(
        self,
        adr_id: str,
        title: str,
        status: str,
        context: str,
        decision: str,
        consequences: str | None = None,
        superseded_by: str | None = None,
        tags: list[str] | None = None,
        project_slug: str = "Braid",
        file_path: str | None = None,
    ) -> int:
        """Store an Architecture Decision Record."""
        _id = _next_id_for("adrs", self.con)
        tags_sql = str(tags) if tags else "NULL"
        self._x(
            f"INSERT INTO {self.alias}.adrs "
            f"(id, adr_id, title, status, superseded_by, context, decision, consequences, tags, project_slug, file_path) "
            f"VALUES ({_id}, '{adr_id}', '{title}', '{status}', "
            f"{'NULL' if superseded_by is None else f"'{superseded_by}'"}, "
            f"'{context}', '{decision}', "
            f"{'NULL' if consequences is None else f"'{consequences}'"}, "
            f"{tags_sql}, '{project_slug}', "
            f"{'NULL' if file_path is None else f"'{file_path}'"})"
        )
        return _id

    def search_adrs(self, query: str, project_slug: str | None = None) -> list[dict]:
        """Search ADRs by text content."""
        where = [f"(title LIKE '%{query}%' OR context LIKE '%{query}%' OR decision LIKE '%{query}%')"]
        if project_slug:
            where.append(f"project_slug = '{project_slug}'")
        where_clause = " AND ".join(where)
        rows = self._q(
            f"SELECT adr_id, title, status, decision FROM {self.alias}.adrs "
            f"WHERE {where_clause} ORDER BY adr_id"
        )
        return [
            {"adr_id": r[0], "title": r[1], "status": r[2], "decision": r[3]}
            for r in rows
        ]

    def get_active_adrs(self, project_slug: str = "Braid") -> list[dict]:
        """Get all active ADRs for a project."""
        rows = self._q(
            f"SELECT adr_id, title, status, decision FROM {self.alias}.adrs "
            f"WHERE project_slug = '{project_slug}' AND status = 'Active' ORDER BY adr_id"
        )
        return [
            {"adr_id": r[0], "title": r[1], "status": r[2], "decision": r[3]}
            for r in rows
        ]

    # ======================================================================
    # 4. RAG OPERATIONS
    # ======================================================================

    def store_rag_chunk(
        self,
        chunk_id: str,
        project_slug: str,
        dataset_id: str,
        content: str,
        source_path: str | None = None,
        chunk_index: int | None = None,
        chunk_type: str = "code",
    ) -> int:
        """Store a RAG chunk."""
        _id = _next_id_for("rag_chunks", self.con)
        self._execute(
            f"INSERT INTO {self.alias}.rag_chunks "
            f"(id, chunk_id, project_slug, dataset_id, content, source_path, chunk_index, chunk_type) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [_id, chunk_id, project_slug, dataset_id, content, source_path, chunk_index, chunk_type],
        )
        return _id

    def cache_search_result(
        self,
        query_hash: str,
        query_text: str,
        project_slug: str,
        results: list,
        search_type: str = "CHUNKS",
        top_k: int = 5,
    ) -> int:
        """Cache a search result for fast recall."""
        _id = _next_id_for("rag_search_cache", self.con)
        results_json = json.dumps(results)
        self._x(
            f"INSERT INTO {self.alias}.rag_search_cache "
            f"(id, query_hash, query_text, project_slug, search_type, top_k, results_json) "
            f"VALUES ({_id}, '{query_hash}', '{query_text}', '{project_slug}', "
            f"'{search_type}', {top_k}, '{results_json}')"
        )
        return _id

    def get_cached_search(self, query_hash: str, project_slug: str) -> list | None:
        """Retrieve a cached search result."""
        rows = self._q(
            f"SELECT results_json FROM {self.alias}.rag_search_cache "
            f"WHERE query_hash = '{query_hash}' AND project_slug = '{project_slug}' "
            f"ORDER BY last_used_at DESC LIMIT 1"
        )
        if rows:
            # Update hit count and last_used_at
            self._x(
                f"UPDATE {self.alias}.rag_search_cache "
                f"SET hit_count = hit_count + 1, last_used_at = now() "
                f"WHERE query_hash = '{query_hash}' AND project_slug = '{project_slug}'"
            )
            return json.loads(rows[0][0])
        return None

    # ======================================================================
    # 5. CONVERSATION TRACKING
    # ======================================================================

    def store_conversation(
        self,
        conversation_id: str,
        agent_id: str,
        project_slug: str | None = None,
        session_type: str = "development",
        model_used: str | None = None,
        tool_used: str | None = None,
        summary: str | None = None,
    ) -> int:
        """Store a conversation record."""
        _id = _next_id_for("conversations", self.con)
        self._x(
            f"INSERT INTO {self.alias}.conversations "
            f"(id, conversation_id, agent_id, project_slug, session_type, model_used, tool_used, summary) "
            f"VALUES ({_id}, '{conversation_id}', '{agent_id}', "
            f"{'NULL' if project_slug is None else f"'{project_slug}'"}, "
            f"'{session_type}', "
            f"{'NULL' if model_used is None else f"'{model_used}'"}, "
            f"{'NULL' if tool_used is None else f"'{tool_used}'"}, "
            f"{'NULL' if summary is None else f"'{summary}'"})"
        )
        return _id

    def store_conversation_turn(
        self,
        conversation_id: str,
        turn_number: int,
        role: str,
        content: str,
        tokens_used: int = 0,
        latency_ms: int | None = None,
    ) -> int:
        """Store a conversation turn."""
        _id = _next_id_for("conversation_turns", self.con)
        self._x(
            f"INSERT INTO {self.alias}.conversation_turns "
            f"(id, conversation_id, turn_number, role, content, tokens_used, latency_ms) "
            f"VALUES ({_id}, '{conversation_id}', {turn_number}, '{role}', "
            f"'{content}', {tokens_used}, "
            f"{'NULL' if latency_ms is None else str(latency_ms)})"
        )
        return _id

    # ======================================================================
    # 5b. MEMORY GARBAGE COLLECTION
    # ======================================================================

    def find_compaction_candidates(
        self,
        project_slug: str | None = None,
        min_turns: int = 1,
        limit: int = 5,
        session_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Find old conversation records that can be compacted into project memory."""
        project_slug = project_slug or self._default_project_slug()
        where = ["c.project_slug = ?"]
        params: list[Any] = [project_slug]
        if session_type:
            where.append("c.session_type = ?")
            params.append(session_type)
        if "metadata_json" in self._table_columns("conversations"):
            where.append("(c.metadata_json IS NULL OR CAST(c.metadata_json AS VARCHAR) NOT LIKE '%\"compacted_into\"%')")

        rows = self._query(
            f"""
            SELECT
                c.conversation_id,
                c.session_type,
                c.summary,
                c.start_time,
                COUNT(t.id) AS turn_count,
                COALESCE(SUM(t.tokens_used), 0) AS tokens_used
            FROM {self.alias}.conversations c
            LEFT JOIN {self.alias}.conversation_turns t
                ON t.conversation_id = c.conversation_id
            WHERE {" AND ".join(where)}
            GROUP BY c.conversation_id, c.session_type, c.summary, c.start_time
            HAVING COUNT(t.id) >= ?
            ORDER BY c.start_time ASC NULLS LAST, c.conversation_id
            LIMIT ?
            """,
            [*params, min_turns, limit],
        )
        return [
            {
                "conversation_id": r[0],
                "session_type": r[1],
                "summary": r[2],
                "start_time": r[3],
                "turn_count": r[4],
                "tokens_used": r[5],
            }
            for r in rows
        ]

    def compact_memory(
        self,
        project_slug: str | None = None,
        conversation_ids: list[str] | None = None,
        min_conversations: int = 5,
        min_turns: int = 1,
        max_source_chars: int = 12000,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Compact redundant conversation history into one indexed project memory entry."""
        project_slug = project_slug or self._default_project_slug()
        if conversation_ids is None:
            candidates = self.find_compaction_candidates(
                project_slug=project_slug,
                min_turns=min_turns,
                limit=min_conversations,
            )
            conversation_ids = [str(c["conversation_id"]) for c in candidates]
        else:
            candidates = [{"conversation_id": cid} for cid in conversation_ids]

        if len(conversation_ids) < min_conversations:
            return {
                "compacted": False,
                "reason": "not_enough_candidates",
                "candidate_count": len(conversation_ids),
                "required": min_conversations,
            }

        placeholders = ", ".join("?" for _ in conversation_ids)
        rows = self._query(
            f"""
            SELECT
                t.conversation_id,
                t.turn_number,
                t.role,
                t.content
            FROM {self.alias}.conversation_turns t
            WHERE t.conversation_id IN ({placeholders})
            ORDER BY t.conversation_id, t.turn_number
            """,
            conversation_ids,
        )
        source_text = "\n".join(
            f"[{r[0]} #{r[1]} {r[2]}] {str(r[3]).strip()}" for r in rows
        )[:max_source_chars]
        digest = hashlib.sha1("|".join(conversation_ids).encode("utf-8")).hexdigest()[:12]
        summary = self._build_compaction_summary(project_slug, conversation_ids, source_text)
        key = f"memory-gc-{digest}"
        metadata = {
            "source": "automatic_memory_gc",
            "conversation_ids": conversation_ids,
            "source_turn_count": len(rows),
            "strategy": "extractive_conversation_compaction",
        }

        if dry_run:
            return {
                "compacted": False,
                "dry_run": True,
                "key": key,
                "summary": summary,
                "conversation_ids": conversation_ids,
                "candidates": candidates,
            }

        memory_id = self.store_project_memory(
            project_slug,
            "compacted_decision",
            key,
            summary,
            tags=["memory-gc", "compacted"],
            confidence=0.72,
            metadata=metadata,
        )
        chunk_id = f"memory-gc:{digest}"
        try:
            self.store_rag_chunk(
                chunk_id,
                project_slug,
                project_slug,
                summary,
                source_path=f".braid/memory/compacted/{key}",
                chunk_type="memory_compaction",
            )
        except Exception:
            pass

        compacted_meta = json.dumps(
            {"compacted_into": key, "project_memory_id": memory_id},
            ensure_ascii=False,
        )
        self._execute(
            f"UPDATE {self.alias}.conversations SET metadata_json = ? "
            f"WHERE conversation_id IN ({placeholders})",
            [compacted_meta, *conversation_ids],
        )
        return {
            "compacted": True,
            "project_memory_id": memory_id,
            "key": key,
            "conversation_ids": conversation_ids,
            "source_turn_count": len(rows),
            "summary": summary,
        }

    def _build_compaction_summary(
        self,
        project_slug: str,
        conversation_ids: list[str],
        source_text: str,
    ) -> str:
        excerpts: list[str] = []
        for line in source_text.splitlines():
            content = line.strip()
            if not content:
                continue
            lowered = content.lower()
            if any(term in lowered for term in ("decision", "decid", "adr", "fix", "bug", "migration", "schema")):
                excerpts.append(content[:500])
            if len(excerpts) >= 8:
                break
        if not excerpts:
            excerpts = [line.strip()[:500] for line in source_text.splitlines() if line.strip()][:5]

        evidence = "\n".join(f"- {item}" for item in excerpts)
        return (
            f"Compacted memory for project {project_slug}.\n\n"
            f"Source conversations: {', '.join(conversation_ids)}.\n"
            "Consolidated decision/context extracted from older debugging turns:\n"
            f"{evidence or '- No usable evidence found.'}\n\n"
            "Use this compacted record instead of replaying the original conversation turns unless exact transcript detail is required."
        )

    # ======================================================================
    # 6. EVAL OPERATIONS
    # ======================================================================

    def store_eval_run(
        self,
        run_id: str,
        project_slug: str,
        total_questions: int,
        total_score: float,
        recall_at_1: float | None = None,
        recall_at_k: float | None = None,
        rerank_used: bool = False,
        search_type: str = "CHUNKS",
        model_used: str | None = None,
    ) -> int:
        """Store an eval run result."""
        _id = _next_id_for("eval_runs", self.con)
        self._x(
            f"INSERT INTO {self.alias}.eval_runs "
            f"(id, run_id, project_slug, total_questions, total_score, recall_at_1, recall_at_k, "
            f"rerank_used, search_type, model_used) "
            f"VALUES ({_id}, '{run_id}', '{project_slug}', {total_questions}, {total_score}, "
            f"{'NULL' if recall_at_1 is None else str(recall_at_1)}, "
            f"{'NULL' if recall_at_k is None else str(recall_at_k)}, "
            f"{rerank_used}, '{search_type}', "
            f"{'NULL' if model_used is None else f"'{model_used}'"})"
        )
        return _id

    # ======================================================================
    # 7. INGESTA TRACKING
    # ======================================================================

    def store_ingested_file(
        self,
        project_slug: str,
        file_path: str,
        file_hash: str,
        file_size: int,
        language: str | None = None,
        kind: str = "code",
        last_modified: datetime | None = None,
        chunk_count: int = 0,
        dataset_id: str | None = None,
    ) -> int:
        """Track an ingested file."""
        _id = _next_id_for("ingested_files", self.con)
        ts = str(last_modified) if last_modified else "now()"
        self._x(
            f"INSERT INTO {self.alias}.ingested_files "
            f"(id, project_slug, file_path, file_hash, file_size, language, kind, last_modified, chunk_count, dataset_id) "
            f"VALUES ({_id}, '{project_slug}', '{file_path}', '{file_hash}', {file_size}, "
            f"{'NULL' if language is None else f"'{language}'"}, '{kind}', {ts}, {chunk_count}, "
            f"{'NULL' if dataset_id is None else f"'{dataset_id}'"})"
        )
        return _id

    def is_file_ingested(self, file_path: str, project_slug: str, file_hash: str) -> bool:
        """Check if a file has already been ingested with this hash."""
        rows = self._q(
            f"SELECT COUNT(*) FROM {self.alias}.ingested_files "
            f"WHERE file_path = '{file_path}' AND project_slug = '{project_slug}' AND file_hash = '{file_hash}'"
        )
        return rows[0][0] > 0

    # ======================================================================
    # 8. AGENT REGISTRY
    # ======================================================================

    def register_agent(
        self,
        agent_id: str,
        agent_name: str,
        agent_type: str | None = None,
        description: str | None = None,
        capabilities: list[str] | None = None,
        project_slugs: list[str] | None = None,
    ) -> int:
        """Register an agent in the catalog."""
        _id = _next_id_for("agents", self.con)
        caps_sql = str(capabilities) if capabilities else "NULL"
        projs_sql = str(project_slugs) if project_slugs else "NULL"
        self._x(
            f"INSERT INTO {self.alias}.agents "
            f"(id, agent_id, agent_name, agent_type, description, capabilities, project_slugs, last_active_at) "
            f"VALUES ({_id}, '{agent_id}', '{agent_name}', "
            f"{'NULL' if agent_type is None else f"'{agent_type}'"}, "
            f"{'NULL' if description is None else f"'{description}'"}, "
            f"{caps_sql}, {projs_sql}, now())"
        )
        return _id

    def update_agent_activity(self, agent_id: str) -> None:
        """Update agent's last_active_at timestamp."""
        self._x(
            f"UPDATE {self.alias}.agents SET last_active_at = now() WHERE agent_id = '{agent_id}'"
        )

    # ======================================================================
    # 9. FTS SEARCH (BM25 via companion DuckDB)
    # ======================================================================

    def fts_search(self, table: str, query: str, limit: int = 10) -> list[dict]:
        """Search using BM25 full-text search on the companion FTS database.

        Available FTS tables:
            - project_memory_fts (key, value)
            - global_memory_fts (key, value)
            - adrs_fts (title, context, decision, consequences)
            - kg_nodes_fts (name, description)
            - rag_chunks_fts (content)
        """
        if not self._fts_con:
            raise RuntimeError("FTS companion database not available. Ensure .braid/kg/braid_fts.duckdb exists.")
        if table not in FTS_TABLES:
            raise ValueError(f"Unsupported FTS table: {table}")

        try:
            safe_query = query.replace("'", "''")
            rows = self._fts_con.execute(
                f"SELECT *, fts_main_{table}.match_bm25(id, '{safe_query}') AS score "
                f"FROM {table} WHERE fts_main_{table}.match_bm25(id, '{safe_query}') "
                f"ORDER BY score DESC LIMIT {limit}"
            ).fetchall()
            cols = [d[0] for d in self._fts_con.description]
            return [dict(zip(cols, r)) for r in rows]
        except Exception as e:
            return [{"error": str(e)}]

    def refresh_fts_index(self) -> None:
        """Refresh the FTS companion database from DuckLake data.

        Recreates the mirrored tables and FTS indexes. Call after
        significant data changes in DuckLake.
        """
        if not self._fts_con:
            self._fts_con = duckdb.connect(str(self.fts_path))
            self._fts_con.execute("LOAD fts")

        fts = self._fts_con

        # Drop and recreate mirrored tables
        for table in ("project_memory_fts", "global_memory_fts", "adrs_fts", "kg_nodes_fts", "rag_chunks_fts"):
            try:
                fts.execute(f"DROP TABLE IF EXISTS {table}")
            except Exception:
                pass

        # Mirror from DuckLake
        fts.execute(
            f"CREATE TABLE project_memory_fts AS "
            f"SELECT id, key, value, project_slug, memory_type, adr_id "
            f"FROM {self.alias}.project_memory"
        )
        fts.execute(
            f"CREATE TABLE global_memory_fts AS "
            f"SELECT id, key, value, memory_type "
            f"FROM {self.alias}.global_memory"
        )
        fts.execute(
            f"CREATE TABLE adrs_fts AS "
            f"SELECT id, adr_id, title, status, context, decision, consequences, project_slug "
            f"FROM {self.alias}.adrs"
        )
        fts.execute(
            f"CREATE TABLE kg_nodes_fts AS "
            f"SELECT id, name, description, node_type, source_path, language "
            f"FROM {self.alias}.kg_nodes"
        )
        fts.execute(
            f"CREATE TABLE rag_chunks_fts AS "
            f"SELECT id, content, source_path, chunk_type, project_slug "
            f"FROM {self.alias}.rag_chunks"
        )

        # Create FTS indexes
        fts.execute("PRAGMA create_fts_index('project_memory_fts', 'id', 'key', 'value')")
        fts.execute("PRAGMA create_fts_index('global_memory_fts', 'id', 'key', 'value')")
        fts.execute("PRAGMA create_fts_index('adrs_fts', 'id', 'title', 'context', 'decision', 'consequences')")
        fts.execute("PRAGMA create_fts_index('kg_nodes_fts', 'id', 'name', 'description')")
        fts.execute("PRAGMA create_fts_index('rag_chunks_fts', 'id', 'content')")

    # ======================================================================
    # 10. SYSTEM METADATA
    # ======================================================================

    def get_metadata(self, key: str) -> str | None:
        """Get a system metadata value."""
        rows = self._q(
            f"SELECT value FROM {self.alias}.system_metadata WHERE key = '{key}'"
        )
        return rows[0][0] if rows else None

    def set_metadata(self, key: str, value: str, description: str | None = None) -> None:
        """Set a system metadata value (upsert)."""
        existing = self._q(
            f"SELECT COUNT(*) FROM {self.alias}.system_metadata WHERE key = '{key}'"
        )
        desc_sql = "NULL" if description is None else f"'{description}'"
        if existing[0][0] > 0:
            self._x(
                f"UPDATE {self.alias}.system_metadata SET value = '{value}', "
                f"description = {desc_sql}, "
                f"updated_at = now() WHERE key = '{key}'"
            )
        else:
            self._x(
                f"INSERT INTO {self.alias}.system_metadata (key, value, description) "
                f"VALUES ('{key}', '{value}', {desc_sql})"
            )

    # ======================================================================
    # 11. SYNC LOG
    # ======================================================================

    def log_sync(
        self,
        source: str,
        target: str,
        sync_type: str,
        tables_synced: list[str] | None = None,
        rows_synced: int = 0,
        status: str = "started",
        error_message: str | None = None,
    ) -> int:
        """Log a sync operation."""
        _id = _next_id_for("sync_log", self.con)
        tables_sql = str(tables_synced) if tables_synced else "NULL"
        err_sql = "NULL" if error_message is None else f"'{error_message}'"
        self._x(
            f"INSERT INTO {self.alias}.sync_log "
            f"(id, source, target, sync_type, tables_synced, rows_synced, status, error_message) "
            f"VALUES ({_id}, '{source}', '{target}', '{sync_type}', {tables_sql}, "
            f"{rows_synced}, '{status}', {err_sql})"
        )
        return _id

    # ======================================================================
    # 12. CATALOG INFO
    # ======================================================================

    def get_tables(self) -> list[str]:
        """List all tables in the catalog."""
        # SHOW TABLES works in DuckLake after USE <catalog>
        self._x(f"USE {self.alias}")
        rows = self._q("SELECT table_name FROM duckdb_tables() WHERE table_name NOT LIKE 'ducklake_%' AND table_name NOT LIKE '__ducklake_%' ORDER BY table_name")
        return [r[0] for r in rows]

    def get_table_count(self, table: str) -> int:
        """Get row count for a table."""
        rows = self._q(f"SELECT COUNT(*) FROM {self.alias}.{table}")
        return rows[0][0] if rows else 0

    def get_catalog_summary(self) -> dict:
        """Get a summary of the entire catalog."""
        tables = self.get_tables()
        counts = {t: self.get_table_count(t) for t in tables}
        return {
            "catalog": self.catalog,
            "tables": len(tables),
            "total_rows": sum(counts.values()),
            "per_table": counts,
            "schema_version": self.get_metadata("schema_version"),
            "created_at": self.get_metadata("created_at"),
        }


# ---------------------------------------------------------------------------
# Convenience: one-shot queries without context manager
# ---------------------------------------------------------------------------

@contextmanager
def open_catalog(**kwargs: Any):
    """Context manager shortcut for BraidCatalog."""
    cat = BraidCatalog(**kwargs)
    cat.open()
    try:
        yield cat
    finally:
        cat.close()


def quick_search(query: str, table: str = "project_memory_fts", limit: int = 5) -> list[dict]:
    """Quick BM25 search without managing connections."""
    with open_catalog() as cat:
        return cat.fts_search(table, query, limit)
