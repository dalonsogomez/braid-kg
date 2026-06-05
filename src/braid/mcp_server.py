"""Braid MCP Server — exposes Braid capabilities as MCP tools.

AGENTS.md sec. 2.1: "MCP-first como protocolo único de consumo."

This server provides 5 tools:
- braid_search: Search DuckLake FTS + Cognee with context resolution
- braid_memory: Read/write 3-level memory (session/project/global)
- braid_adrs: Query active ADRs
- braid_status: Project status summary
- braid_kg: Knowledge graph subgraph traversal

Run with:
    braid mcp-serve
    # or directly:
    python -m braid.mcp_server
"""
from __future__ import annotations

import json
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .paths import resolve_context

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS: list[Tool] = [
    Tool(
        name="braid_search",
        description=(
            "Search Braid for information about the active project. "
            "Combines DuckLake FTS (BM25) and Cognee vector search. "
            "Resolves project context automatically (cwd -> git root -> .braid/config.toml -> global)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "search_type": {
                    "type": "string",
                    "enum": ["CHUNKS", "SUMMARIES", "GRAPH_COMPLETION", "RAG_COMPLETION", "INSIGHTS"],
                    "default": "CHUNKS",
                    "description": "Cognee search type",
                },
                "top_k": {"type": "integer", "default": 5, "description": "Max results per source"},
                "use_global": {"type": "boolean", "default": False, "description": "Search global profile instead of project"},
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="braid_memory",
        description=(
            "Read or write Braid 3-level memory. "
            "Levels: session (volatile), project (persistent, linked to git root), "
            "global (cross-project fallback). "
            "Promotion is always manual (AGENTS.md sec. 4.2 golden rule)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["read", "write", "search"],
                    "default": "search",
                    "description": "Action: read (by key), write (store), search (by query)",
                },
                "level": {
                    "type": "string",
                    "enum": ["session", "project", "global"],
                    "default": "project",
                    "description": "Memory level",
                },
                "key": {"type": "string", "description": "Memory key (for read/write)"},
                "value": {"type": "string", "description": "Memory value (for write)"},
                "query": {"type": "string", "description": "Search query (for search action)"},
                "memory_type": {"type": "string", "default": "note", "description": "Memory type (decision, convention, observation, note)"},
                "session_id": {"type": "string", "description": "Session ID (for session level)"},
            },
            "required": ["action"],
        },
    ),
    Tool(
        name="braid_adrs",
        description=(
            "Query Architecture Decision Records (ADRs) for the active project. "
            "Returns active ADRs or searches by keyword."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "search"],
                    "default": "list",
                    "description": "List all active ADRs or search by keyword",
                },
                "query": {"type": "string", "description": "Search keyword (for search action)"},
            },
            "required": [],
        },
    ),
    Tool(
        name="braid_status",
        description=(
            "Get Braid status for the active project: "
            "project info, DuckLake catalog summary, memory levels, ADR count."
        ),
        inputSchema={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
    Tool(
        name="braid_kg",
        description=(
            "Query the Knowledge Graph subgraph for a given node. "
            "Returns connected nodes and edges up to the specified depth."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "node_id": {"type": "string", "description": "Starting node ID"},
                "depth": {"type": "integer", "default": 1, "description": "Traversal depth (1-3)"},
                "project_slug": {"type": "string", "description": "Project slug (defaults to active project)"},
            },
            "required": ["node_id"],
        },
    ),
]


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

async def _handle_search(arguments: dict[str, Any]) -> list[TextContent]:
    query = arguments["query"]
    search_type = arguments.get("search_type", "CHUNKS")
    top_k = arguments.get("top_k", 5)
    use_global = arguments.get("use_global", False)

    ctx = resolve_context()
    dataset = "_global_profile" if use_global else ctx.dataset_id

    results: dict[str, Any] = {"query": query, "project": ctx.dataset_id, "sources": {}}

    # 1. Cognee vector search
    try:
        from .runner import run_search
        cognee_res = run_search(query, dataset, search_type=search_type, top_k=top_k)
        if cognee_res:
            results["sources"]["cognee"] = [
                {"text": (item.get("text", "") if isinstance(item, dict) else str(item))[:500]}
                for item in cognee_res[:top_k]
            ]
    except Exception as e:
        results["sources"]["cognee_error"] = str(e)

    # 2. DuckLake FTS
    try:
        from .ducklake import BraidCatalog
        with BraidCatalog() as cat:
            hybrid = cat.hybrid_search(query, project_slug=ctx.dataset_id, top_k=top_k).as_dict()
            for batch in hybrid["sources"].get("global_prompts", []):
                prompt = batch.pop("prompt", "")
                batch["prompt_preview"] = prompt[:500]
            results["sources"]["ducklake_hybrid"] = hybrid["sources"]
            if cat.fts_con:
                fts_hits: list[dict] = []
                for idx in ("adrs_fts", "project_memory_fts", "kg_nodes_fts"):
                    try:
                        hits = cat.fts_search(idx, query)
                        for h in hits[:top_k]:
                            fts_hits.append({
                                "index": idx,
                                "text": str(h.get("text", ""))[:500] if isinstance(h, dict) else str(h)[:500],
                            })
                    except Exception:
                        continue
                if fts_hits:
                    results["sources"]["ducklake_fts"] = fts_hits[:top_k]
    except Exception as e:
        results["sources"]["ducklake_fts_error"] = str(e)

    # 3. DuckLake memory
    try:
        from .ducklake import BraidCatalog
        with BraidCatalog() as cat:
            proj = cat.search_project_memory(query, project_slug=ctx.dataset_id)
            if proj:
                results["sources"]["project_memory"] = [
                    {"type": r.get("type", r.get("memory_type", "?")), "key": r.get("key", "?"), "value": str(r.get("value", ""))[:300]}
                    for r in proj[:top_k]
                ]
    except Exception as e:
        results["sources"]["memory_error"] = str(e)

    return [TextContent(type="text", text=json.dumps(results, indent=2, ensure_ascii=False))]


async def _handle_memory(arguments: dict[str, Any]) -> list[TextContent]:
    action = arguments.get("action", "search")
    level = arguments.get("level", "project")
    key = arguments.get("key", "")
    value = arguments.get("value", "")
    query = arguments.get("query", key)
    memory_type = arguments.get("memory_type", "note")
    session_id = arguments.get("session_id", "mcp-session")

    ctx = resolve_context()

    try:
        from .ducklake import BraidCatalog
    except ImportError:
        return [TextContent(type="text", text=json.dumps({"error": "DuckLake not available"}))]

    result: dict[str, Any] = {"action": action, "level": level}

    with BraidCatalog() as cat:
        if action == "write":
            if level == "session":
                sid = cat.store_session_memory(session_id, memory_type, key, value, project_slug=ctx.dataset_id)
            elif level == "project":
                sid = cat.store_project_memory(ctx.dataset_id, memory_type, key, value)
            else:
                sid = cat.store_global_memory(memory_type, key, value)
            result["stored"] = True
            result["id"] = sid

        elif action == "read":
            if level == "session":
                rows = cat.search_session_memory(key, session_id=session_id)
            elif level == "project":
                rows = cat.search_project_memory(key, project_slug=ctx.dataset_id)
            else:
                rows = cat.search_global_memory(key)
            result["results"] = rows[:10]

        elif action == "search":
            if level == "session":
                rows = cat.search_session_memory(query, session_id=session_id)
            elif level == "project":
                rows = cat.search_project_memory(query, project_slug=ctx.dataset_id)
            else:
                rows = cat.search_global_memory(query)
            result["results"] = rows[:10]

    return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False, default=str))]


async def _handle_adrs(arguments: dict[str, Any]) -> list[TextContent]:
    action = arguments.get("action", "list")
    query = arguments.get("query", "")

    try:
        from .ducklake import BraidCatalog
    except ImportError:
        return [TextContent(type="text", text=json.dumps({"error": "DuckLake not available"}))]

    with BraidCatalog() as cat:
        if action == "search" and query:
            rows = cat.search_adrs(query)
        else:
            rows = cat.get_active_adrs()

    return [TextContent(type="text", text=json.dumps(rows, indent=2, ensure_ascii=False, default=str))]


async def _handle_status(arguments: dict[str, Any]) -> list[TextContent]:
    ctx = resolve_context()

    result: dict[str, Any] = {
        "project": {
            "dataset_id": ctx.dataset_id,
            "root": str(ctx.root),
            "has_kg": ctx.has_kg,
            "has_config": ctx.has_config,
            "state_dir": str(ctx.braid_dir),
            "legacy_layout": ctx.legacy_layout,
        },
    }

    # DuckLake
    try:
        from .ducklake import BraidCatalog
        with BraidCatalog() as cat:
            result["ducklake"] = cat.get_catalog_summary()
    except Exception as e:
        result["ducklake_error"] = str(e)

    # ADR count
    decisions = ctx.memory_dir / "decisions"
    result["project"]["adr_count"] = (
        len(list(decisions.glob("[0-9]*-*.md"))) if decisions.is_dir() else 0
    )

    return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False, default=str))]


async def _handle_kg(arguments: dict[str, Any]) -> list[TextContent]:
    node_id = arguments["node_id"]
    depth = min(arguments.get("depth", 1), 3)
    project_slug = arguments.get("project_slug") or resolve_context().dataset_id

    try:
        from .ducklake import BraidCatalog
    except ImportError:
        return [TextContent(type="text", text=json.dumps({"error": "DuckLake not available"}))]

    with BraidCatalog() as cat:
        subgraph = cat.get_subgraph(node_id, depth=depth, project_slug=project_slug)

    return [TextContent(type="text", text=json.dumps(subgraph, indent=2, ensure_ascii=False, default=str))]


# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------

app = Server("braid")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    handlers = {
        "braid_search": _handle_search,
        "braid_memory": _handle_memory,
        "braid_adrs": _handle_adrs,
        "braid_status": _handle_status,
        "braid_kg": _handle_kg,
    }
    handler = handlers.get(name)
    if handler is None:
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]
    try:
        return await handler(arguments)
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": f"{type(e).__name__}: {e}"}))]


async def main() -> None:
    """Run the MCP server over stdio."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
