"""Tests for Braid commands.promote (braid.commands.promote) — ADR numbering, slugify, demote."""
from __future__ import annotations

import pytest
from pathlib import Path

from braid.commands.promote import (
    _slugify,
    _next_adr_number,
    run_promote_decision,
    run_demote,
    run_promote_to_global,
)
from braid.paths import ProjectContext


class TestSlugify:
    def test_simple_text(self):
        assert _slugify("Hello World") == "hello-world"

    def test_special_characters(self):
        assert _slugify("Use Ollama + bge-m3!") == "use-ollama-bge-m3"

    def test_max_length(self):
        result = _slugify("a" * 100, max_len=20)
        assert len(result) <= 20

    def test_empty_string(self):
        assert _slugify("") == "decision"

    def test_underscores_and_dots(self):
        assert _slugify("my_file.py") == "my-file-py"


class TestNextAdrNumber:
    def test_first_adr(self, tmp_git_root):
        decisions_dir = tmp_git_root / ".braid" / "memory" / "decisions"
        assert _next_adr_number(decisions_dir) == "0001"

    def test_increments(self, tmp_git_root):
        decisions_dir = tmp_git_root / ".braid" / "memory" / "decisions"
        (decisions_dir / "0001-first.md").write_text("# ADR 1")
        (decisions_dir / "0002-second.md").write_text("# ADR 2")
        assert _next_adr_number(decisions_dir) == "0003"

    def test_gap_in_numbering(self, tmp_git_root):
        decisions_dir = tmp_git_root / ".braid" / "memory" / "decisions"
        (decisions_dir / "0001-first.md").write_text("# ADR 1")
        (decisions_dir / "0005-fifth.md").write_text("# ADR 5")
        # Should use max + 1, not fill the gap
        assert _next_adr_number(decisions_dir) == "0006"


class TestRunPromoteDecision:
    def test_creates_adr_file(self, tmp_git_root, monkeypatch):
        ctx = ProjectContext(
            root=tmp_git_root,
            dataset_id="test-project",
            has_kg=True,
            kgconfig={},
        )
        # Patch resolve_context in the promote module's namespace
        import braid.commands.promote as promote_mod
        monkeypatch.setattr(promote_mod, "resolve_context", lambda: ctx)

        result = run_promote_decision("Use DuckDB for catalog storage", title="DuckDB Catalog")
        assert result == 0

        decisions_dir = tmp_git_root / ".braid" / "memory" / "decisions"
        files = list(decisions_dir.glob("*.md"))
        assert len(files) >= 1
        content = files[0].read_text()
        assert "DuckDB Catalog" in content
        assert "Use DuckDB for catalog storage" in content

    def test_no_decisions_dir(self, tmp_path, monkeypatch):
        ctx = ProjectContext(
            root=tmp_path,
            dataset_id="test-no-mem",
            has_kg=False,
            kgconfig={},
        )
        import braid.commands.promote as promote_mod
        monkeypatch.setattr(promote_mod, "resolve_context", lambda: ctx)
        # No .braid/memory/decisions dir
        result = run_promote_decision("test")
        assert result == 1


class TestRunDemote:
    def test_demote_moves_file(self, tmp_git_root, monkeypatch):
        ctx = ProjectContext(
            root=tmp_git_root,
            dataset_id="test-project",
            has_kg=True,
            kgconfig={},
        )
        import braid.commands.promote as promote_mod
        monkeypatch.setattr(promote_mod, "resolve_context", lambda: ctx)

        decisions_dir = tmp_git_root / ".braid" / "memory" / "decisions"
        test_adr = decisions_dir / "0042-demote-test.md"
        test_adr.write_text("# ADR 42 — Demote Test")

        result = run_demote("0042")
        assert result == 0
        assert not test_adr.exists()
        demoted = decisions_dir / "_demoted" / "0042-demote-test.md"
        assert demoted.exists()

    def test_demote_not_found(self, tmp_git_root, monkeypatch):
        ctx = ProjectContext(
            root=tmp_git_root,
            dataset_id="test-project",
            has_kg=True,
            kgconfig={},
        )
        import braid.commands.promote as promote_mod
        monkeypatch.setattr(promote_mod, "resolve_context", lambda: ctx)
        result = run_demote("9999")
        assert result == 1
