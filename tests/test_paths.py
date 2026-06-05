"""Tests for Braid path and context resolution."""
from __future__ import annotations

from pathlib import Path

import pytest

from braid import paths as paths_module
from braid.paths import (
    GLOBAL_DATASET_ID,
    PROFILE_DIR,
    ProjectContext,
    config_path,
    find_braid_root,
    find_git_root,
    find_project_root,
    find_kg_root,
    load_kgconfig,
    resolve_context,
    secrets_path,
)


class TestFindGitRoot:
    def test_finds_real_git_root(self, tmp_path: Path):
        import subprocess

        root = tmp_path / "real-git-project"
        root.mkdir()
        subprocess.run(["git", "init"], cwd=root, capture_output=True, check=True)
        assert find_git_root(root) == root

    def test_returns_none_outside_git(self, tmp_path: Path):
        assert find_git_root(tmp_path) is None

    def test_finds_from_subdirectory(self, tmp_path: Path):
        import subprocess

        root = tmp_path / "real-git-project"
        root.mkdir()
        subprocess.run(["git", "init"], cwd=root, capture_output=True, check=True)
        subdir = root / "src" / "deep"
        subdir.mkdir(parents=True)
        assert find_git_root(subdir) == root


class TestFindBraidRoot:
    def test_finds_braid_dir(self, tmp_git_root: Path):
        assert find_braid_root(tmp_git_root) == tmp_git_root

    def test_finds_canonical_config(self, tmp_path: Path):
        root = tmp_path / "project"
        (root / ".braid").mkdir(parents=True)
        (root / ".braid" / "config.toml").write_text('dataset_id = "test"')
        assert find_braid_root(root) == root

    def test_finds_legacy_kgconfig(self, tmp_path: Path):
        root = tmp_path / "legacy-project"
        root.mkdir()
        (root / ".kgconfig").write_text('dataset_id = "legacy"')
        assert find_braid_root(root) == root
        assert find_kg_root(root) == root

    def test_returns_none_without_state(self, tmp_path: Path):
        root = tmp_path / "no-braid-project"
        root.mkdir()
        assert find_braid_root(root) is None

    def test_project_marker_blocks_parent_braid_state(self, tmp_path: Path):
        container = tmp_path / "Developer"
        child = container / "stock-pattern-classifier-orchestrator"
        child.mkdir(parents=True)
        (container / ".git").mkdir()
        (container / ".braid").mkdir()
        (container / ".braid" / "config.toml").write_text('dataset_id = "Developer"')
        (child / "requirements.txt").write_text("pytest\n")

        assert find_project_root(child) == child
        assert find_braid_root(child) is None


class TestHierarchicalContexts:
    def test_parent_directory_can_be_context_without_leaking_to_child(self, tmp_path: Path):
        container = tmp_path / "Developer"
        child = container / "stock-pattern-classifier-orchestrator"
        child.mkdir(parents=True)
        (container / ".git").mkdir()
        (container / ".braid").mkdir()
        (container / ".braid" / "config.toml").write_text('dataset_id = "Developer"')
        (child / "requirements.txt").write_text("pytest\n")

        assert find_project_root(container) == container
        assert find_braid_root(container) == container

        parent_ctx = resolve_context(start=container)
        assert parent_ctx.root == container
        assert parent_ctx.dataset_id == "Developer"
        assert parent_ctx.has_config is True

        child_ctx = resolve_context(start=child)
        assert child_ctx.root == child
        assert child_ctx.dataset_id == "stock-pattern-classifier-orchestrator"
        assert child_ctx.has_config is False

    def test_global_braid_home_is_not_project_state(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        fake_home = tmp_path / "home"
        scratch = tmp_path / "scratch"
        scratch.mkdir()
        (fake_home / ".braid" / "profile" / "kg").mkdir(parents=True)
        (fake_home / ".braid" / "profile" / "config.toml").write_text(
            'dataset_id = "_global_profile"\n'
        )
        (fake_home / ".kg").mkdir()

        monkeypatch.setattr(paths_module, "BRAID_HOME", fake_home / ".braid")
        monkeypatch.setattr(paths_module, "PROFILE_DIR", fake_home / ".braid" / "profile")

        ctx = paths_module.resolve_context(start=scratch)
        assert ctx.root == fake_home
        assert ctx.braid_dir == fake_home / ".braid" / "profile"
        assert ctx.memory_dir == fake_home / ".braid" / "profile"
        assert ctx.dataset_id == GLOBAL_DATASET_ID
        assert ctx.has_kg is True
        assert ctx.global_profile is True


class TestLoadKgconfig:
    def test_prefers_canonical_config(self, tmp_git_root: Path, kgconfig_content: str):
        (tmp_git_root / ".kgconfig").write_text('dataset_id = "legacy"')
        config_path(tmp_git_root).write_text(kgconfig_content)
        cfg = load_kgconfig(tmp_git_root)
        assert cfg["dataset_id"] == "test-project"
        assert cfg["graph_backend"] == "kuzu"
        assert cfg["fallback_threshold"] == 0.55

    def test_reads_legacy_config_when_canonical_missing(self, tmp_path: Path):
        root = tmp_path / "legacy"
        root.mkdir()
        (root / ".kgconfig").write_text('dataset_id = "legacy-project"')
        assert load_kgconfig(root)["dataset_id"] == "legacy-project"

    def test_returns_empty_on_missing(self, tmp_path: Path):
        assert load_kgconfig(tmp_path) == {}

    def test_invalid_toml_raises(self, tmp_git_root: Path):
        config_path(tmp_git_root).write_text("this is not valid toml {{{")
        with pytest.raises(Exception):
            load_kgconfig(tmp_git_root)


class TestResolveContext:
    def test_resolves_canonical_braid_root(self, tmp_git_root: Path, kgconfig_content: str):
        config_path(tmp_git_root).write_text(kgconfig_content)
        ctx = resolve_context(start=tmp_git_root)
        assert ctx.dataset_id == "test-project"
        assert ctx.has_kg is True
        assert ctx.root == tmp_git_root
        assert ctx.config_path == config_path(tmp_git_root)
        assert ctx.legacy_layout is False

    def test_resolves_git_root_without_braid_state(self, tmp_path: Path):
        import subprocess

        root = tmp_path / "plain-repo"
        root.mkdir()
        subprocess.run(["git", "init"], cwd=root, capture_output=True, check=True)
        ctx = resolve_context(start=root)
        assert ctx.dataset_id == root.name
        assert ctx.has_kg is False
        assert ctx.has_config is False

    def test_resolves_project_child_not_container_state(self, tmp_path: Path):
        container = tmp_path / "Developer"
        child = container / "stock-pattern-classifier-orchestrator"
        child.mkdir(parents=True)
        (container / ".git").mkdir()
        (container / ".braid").mkdir()
        (container / ".braid" / "config.toml").write_text('dataset_id = "Developer"')
        (child / "Dockerfile").write_text("FROM python:3.13\n")
        (child / "README.md").write_text("# Stock project\n")

        ctx = resolve_context(start=child)
        assert ctx.root == child
        assert ctx.dataset_id == "stock-pattern-classifier-orchestrator"
        assert ctx.has_kg is False
        assert ctx.has_config is False
        assert ctx.legacy_layout is False

    def test_resolves_legacy_layout_for_migration(self, tmp_path: Path):
        root = tmp_path / "legacy"
        root.mkdir()
        (root / ".kg").mkdir()
        (root / ".kgconfig").write_text('dataset_id = "legacy-project"')
        ctx = resolve_context(start=root)
        assert ctx.dataset_id == "legacy-project"
        assert ctx.has_kg is True
        assert ctx.legacy_layout is True

    def test_parent_legacy_layout_does_not_cross_project_marker(self, tmp_path: Path):
        container = tmp_path / "Developer"
        child = container / "project"
        child.mkdir(parents=True)
        (container / ".kg").mkdir()
        (container / ".kgconfig").write_text('dataset_id = "Developer"')
        (child / "pyproject.toml").write_text('[project]\nname = "child"\n')

        ctx = resolve_context(start=child)
        assert ctx.root == child
        assert ctx.dataset_id == "project"
        assert ctx.legacy_layout is False
        assert ctx.has_kg is False

    def test_fallback_to_global(self, tmp_path: Path):
        ctx = resolve_context(start=tmp_path)
        assert ctx.dataset_id == GLOBAL_DATASET_ID
        assert ctx.root == PROFILE_DIR.parent.parent
        assert ctx.braid_dir == PROFILE_DIR
        assert ctx.global_profile is True


class TestProjectContext:
    def test_properties(self, tmp_git_root: Path):
        ctx = ProjectContext(root=tmp_git_root, dataset_id="test", has_kg=True, kgconfig={})
        assert ctx.braid_dir == tmp_git_root / ".braid"
        assert ctx.memory_dir == tmp_git_root / ".braid" / "memory"
        assert ctx.kg_dir == tmp_git_root / ".braid" / "kg"
        assert ctx.rag_dir == tmp_git_root / ".braid" / "rag"
        assert ctx.wiki_dir == tmp_git_root / ".braid" / "wiki"

    def test_default_fallback_threshold(self, tmp_git_root: Path):
        ctx = ProjectContext(root=tmp_git_root, dataset_id="test", has_kg=True, kgconfig={})
        assert ctx.fallback_threshold == 0.55

    def test_global_profile_properties(self, tmp_path: Path):
        profile = tmp_path / ".braid" / "profile"
        ctx = ProjectContext(
            root=tmp_path,
            dataset_id=GLOBAL_DATASET_ID,
            has_kg=True,
            kgconfig={},
            state_dir=profile,
            global_profile=True,
        )
        assert ctx.braid_dir == profile
        assert ctx.memory_dir == profile
        assert ctx.kg_dir == profile / "kg"


class TestSecretsPath:
    def test_returns_home_config_path(self):
        path = secrets_path()
        assert str(path).endswith(".config/braid/secrets.env")
        assert path.is_absolute()
