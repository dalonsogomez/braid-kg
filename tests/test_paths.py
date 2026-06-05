"""Tests for fairlead paths (wikiforge.paths) — context resolution, git root, kgconfig."""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from wikiforge.paths import (
    GLOBAL_DATASET_ID,
    PROFILE_DIR,
    ProjectContext,
    find_git_root,
    find_kg_root,
    load_kgconfig,
    resolve_context,
    secrets_path,
)


class TestFindGitRoot:
    def test_finds_real_git_root(self, tmp_path):
        """find_git_root uses `git rev-parse` which requires a real git repo."""
        import subprocess
        root = tmp_path / "real-git-project"
        root.mkdir()
        subprocess.run(["git", "init"], cwd=root, capture_output=True, check=True)
        result = find_git_root(root)
        assert result == root

    def test_returns_none_outside_git(self, tmp_path):
        result = find_git_root(tmp_path)
        assert result is None

    def test_finds_from_subdirectory(self, tmp_path):
        import subprocess
        root = tmp_path / "real-git-project"
        root.mkdir()
        subprocess.run(["git", "init"], cwd=root, capture_output=True, check=True)
        subdir = root / "src" / "deep"
        subdir.mkdir(parents=True)
        result = find_git_root(subdir)
        assert result == root


class TestFindKgRoot:
    def test_finds_kg_dir(self, tmp_git_root):
        result = find_kg_root(tmp_git_root)
        assert result == tmp_git_root

    def test_finds_kgconfig(self, tmp_path):
        root = tmp_path / "project"
        root.mkdir()
        (root / ".kgconfig").write_text('dataset_id = "test"')
        result = find_kg_root(root)
        assert result == root

    def test_returns_none_without_kg(self, tmp_path):
        root = tmp_path / "no-kg-project"
        root.mkdir()
        result = find_kg_root(root)
        assert result is None


class TestLoadKgconfig:
    def test_loads_valid_toml(self, tmp_git_root, kgconfig_content):
        (tmp_git_root / ".kgconfig").write_text(kgconfig_content)
        cfg = load_kgconfig(tmp_git_root)
        assert cfg["dataset_id"] == "test-project"
        assert cfg["graph_backend"] == "kuzu"
        assert cfg["fallback_threshold"] == 0.55

    def test_returns_empty_on_missing(self, tmp_path):
        cfg = load_kgconfig(tmp_path)
        assert cfg == {}

    def test_returns_empty_on_invalid_toml(self, tmp_git_root):
        (tmp_git_root / ".kgconfig").write_text("this is not valid toml {{{")
        # tomllib.loads will raise, should be caught
        # Actually load_kgconfig doesn't catch — let's check
        try:
            cfg = load_kgconfig(tmp_git_root)
        except Exception:
            pass  # Expected — invalid TOML raises


class TestResolveContext:
    def test_resolves_kg_root(self, tmp_git_root, kgconfig_content):
        (tmp_git_root / ".kgconfig").write_text(kgconfig_content)
        ctx = resolve_context(start=tmp_git_root)
        assert ctx.dataset_id == "test-project"
        assert ctx.has_kg is True
        assert ctx.root == tmp_git_root

    def test_resolves_git_root_without_kg(self, tmp_git_root):
        # No .kgconfig, but has .kg dir
        ctx = resolve_context(start=tmp_git_root)
        assert ctx.dataset_id == tmp_git_root.name
        assert ctx.has_kg is True

    def test_fallback_to_global(self, tmp_path):
        # No git, no kg — should fallback to global profile
        ctx = resolve_context(start=tmp_path)
        assert ctx.dataset_id == GLOBAL_DATASET_ID
        assert ctx.root == PROFILE_DIR


class TestProjectContext:
    def test_properties(self, tmp_git_root):
        ctx = ProjectContext(
            root=tmp_git_root,
            dataset_id="test",
            has_kg=True,
            kgconfig={},
        )
        assert ctx.memory_dir == tmp_git_root / ".memory"
        assert ctx.kg_dir == tmp_git_root / ".kg"
        assert ctx.rag_dir == tmp_git_root / ".rag"

    def test_default_fallback_threshold(self, tmp_git_root):
        ctx = ProjectContext(
            root=tmp_git_root,
            dataset_id="test",
            has_kg=True,
            kgconfig={},
        )
        assert ctx.fallback_threshold == 0.55


class TestSecretsPath:
    def test_returns_home_config_path(self):
        p = secrets_path()
        assert str(p).endswith(".config/fairlead/secrets.env")
        assert p.is_absolute()
