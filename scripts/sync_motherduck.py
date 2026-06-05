#!/usr/bin/env python3
"""Sync Braid DuckLake catalog to MotherDuck cloud.

Usage:
    python scripts/sync_motherduck.py [--direction push|pull] [--tables all|table1,table2]

Environment:
    MOTHERDUCK_TOKEN  — API token from https://app.motherduck.com/ → Settings → Access Tokens
                        Or set in ~/.config/braid/secrets.env

Sync tables:
    project_memory, global_memory, adrs, kg_nodes, kg_edges,
    agents, system_metadata, eval_runs
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path
from datetime import datetime, timezone

# ── Config ──────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parents[1]
DUCKLAKE_CATALOG = f"ducklake:duckdb:{REPO_ROOT / '.braid' / 'kg' / 'braid_ducklake'}"
MOTHERDUCK_DB = "md:my_db"
MOTHERDUCK_SCHEMA = "braid"
SECRETS_PATH = Path.home() / ".config/braid/secrets.env"

SYNC_TABLES = [
    "session_memory",
    "project_memory",
    "global_memory",
    "kg_nodes",
    "kg_edges",
    "rag_chunks",
    "rag_search_cache",
    "adrs",
    "conversations",
    "conversation_turns",
    "eval_runs",
    "eval_answers",
    "ingested_files",
    "sync_log",
    "agents",
    "system_metadata",
]


# ── Helpers ─────────────────────────────────────────────────────────────


def _load_token() -> str:
    """Load MotherDuck token from env or secrets file."""
    token = os.environ.get("MOTHERDUCK_TOKEN", "")
    if token:
        return token

    if SECRETS_PATH.exists():
        for line in SECRETS_PATH.read_text().splitlines():
            line = line.strip()
            if line.startswith("MOTHERDUCK_TOKEN="):
                token = line.split("=", 1)[1].strip().strip('"').strip("'")
                if token:
                    return token

    print("ERROR: MOTHERDUCK_TOKEN not found.", file=sys.stderr)
    print("Set it in ~/.config/braid/secrets.env or as env var.", file=sys.stderr)
    sys.exit(1)


def _get_duckdb_con(token: str):
    """Get a DuckDB connection with both catalogs attached."""
    import duckdb

    con = duckdb.connect()
    con.execute("LOAD ducklake")
    con.execute("LOAD motherduck")
    con.execute(f"SET motherduck_token='{token}'")
    # Attach DuckLake first (supports aliases)
    con.execute(f"ATTACH '{DUCKLAKE_CATALOG}' AS local")
    # MotherDuck auto-attaches 'my_db' when you set the token
    # No need to ATTACH it explicitly — it's already available
    return con


# ── Push (local → cloud) ────────────────────────────────────────────────


def push_tables(con, tables: list[str]) -> dict[str, int]:
    """Push local DuckLake tables to MotherDuck cloud.

    Strategy: export to parquet → import into MotherDuck.
    Uses DELETE + INSERT to avoid duplicates.
    """
    results = {}
    with tempfile.TemporaryDirectory(prefix="braid_sync_") as tmpdir:
        for table in tables:
            parquet_path = Path(tmpdir) / f"{table}.parquet"
            print(f"  Exporting {table}...", end=" ", flush=True)

            # Export from local DuckLake
            try:
                con.execute(
                    f"COPY (SELECT * FROM local.{table}) "
                    f"TO '{parquet_path}' (FORMAT PARQUET)"
                )
            except Exception as e:
                print(f"SKIP (export error: {e})")
                results[table] = -1
                continue

            # Clear and import into MotherDuck
            try:
                con.execute(f"USE my_db.{MOTHERDUCK_SCHEMA}")
                con.execute(f"DELETE FROM {table}")
                row_count = con.execute(
                    f"SELECT COUNT(*) FROM read_parquet('{parquet_path}')"
                ).fetchone()[0]

                if row_count > 0:
                    con.execute(
                        f"INSERT INTO {table} SELECT * FROM read_parquet('{parquet_path}')"
                    )

                results[table] = row_count
                print(f"OK ({row_count} rows)")
            except Exception as e:
                print(f"SKIP (import error: {e})")
                results[table] = -1

    return results


# ── Pull (cloud → local) ────────────────────────────────────────────────


def pull_tables(con, tables: list[str]) -> dict[str, int]:
    """Pull MotherDuck cloud tables into local DuckLake.

    Strategy: export from MotherDuck → import into DuckLake.
    Uses DELETE + INSERT to avoid duplicates.
    """
    results = {}
    with tempfile.TemporaryDirectory(prefix="braid_sync_") as tmpdir:
        for table in tables:
            parquet_path = Path(tmpdir) / f"{table}.parquet"
            print(f"  Pulling {table}...", end=" ", flush=True)

            # Export from MotherDuck
            try:
                con.execute(f"USE my_db.{MOTHERDUCK_SCHEMA}")
                con.execute(
                    f"COPY (SELECT * FROM {table}) "
                    f"TO '{parquet_path}' (FORMAT PARQUET)"
                )
            except Exception as e:
                print(f"SKIP (export error: {e})")
                results[table] = -1
                continue

            # Clear and import into local DuckLake
            try:
                con.execute("USE local")
                con.execute(f"DELETE FROM {table}")
                row_count = con.execute(
                    f"SELECT COUNT(*) FROM read_parquet('{parquet_path}')"
                ).fetchone()[0]

                if row_count > 0:
                    con.execute(
                        f"INSERT INTO {table} SELECT * FROM read_parquet('{parquet_path}')"
                    )

                results[table] = row_count
                print(f"OK ({row_count} rows)")
            except Exception as e:
                print(f"SKIP (import error: {e})")
                results[table] = -1

    return results


# ── Main ─────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Sync Braid DuckLake ↔ MotherDuck")
    parser.add_argument(
        "--direction",
        choices=["push", "pull"],
        default="push",
        help="push=local→cloud, pull=cloud→local (default: push)",
    )
    parser.add_argument(
        "--tables",
        default="all",
        help="Comma-separated table names or 'all' (default: all)",
    )
    args = parser.parse_args()

    tables = SYNC_TABLES if args.tables == "all" else args.tables.split(",")
    token = _load_token()

    print(f"Braid DuckLake ↔ MotherDuck Sync")
    print(f"Direction: {args.direction}")
    print(f"Tables: {', '.join(tables)}")
    print()

    con = _get_duckdb_con(token)

    try:
        if args.direction == "push":
            results = push_tables(con, tables)
        else:
            results = pull_tables(con, tables)

        # Log sync
        now = datetime.now(timezone.utc).isoformat()
        synced = sum(1 for v in results.values() if v >= 0)
        total_rows = sum(v for v in results.values() if v >= 0)

        print(f"\nSync complete: {synced}/{len(tables)} tables, {total_rows} total rows")

        # Update system_metadata
        try:
            con.execute("USE local")
            con.execute(
                f"INSERT INTO system_metadata (key, value, description, updated_at) "
                f"VALUES ('last_{args.direction}_sync', '{now}', "
                f"'Last {args.direction} sync to MotherDuck', now()) "
                f"ON CONFLICT (key) DO UPDATE SET value='{now}', updated_at=now()"
            )
        except Exception:
            pass  # DuckLake doesn't support ON CONFLICT

    finally:
        con.close()


if __name__ == "__main__":
    main()
