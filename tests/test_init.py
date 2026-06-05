"""Tests for braid init project-boundary behavior."""
from __future__ import annotations

from pathlib import Path

from braid.commands import init as init_cmd


def test_init_uses_child_project_marker_under_container_git(tmp_path: Path, monkeypatch):
    container = tmp_path / "Developer"
    child = container / "stock-pattern-classifier-orchestrator"
    child.mkdir(parents=True)
    (container / ".git").mkdir()
    (container / ".braid").mkdir()
    (container / ".braid" / "config.toml").write_text('dataset_id = "Developer"')
    (child / "requirements.txt").write_text("pytest\n")

    monkeypatch.chdir(child)
    assert init_cmd.run() == 0

    assert (child / ".braid" / "config.toml").is_file()
    assert 'dataset_id = "stock-pattern-classifier-orchestrator"' in (
        child / ".braid" / "config.toml"
    ).read_text()
    assert (container / ".braid" / "config.toml").read_text() == 'dataset_id = "Developer"'


def test_init_inside_repo_subdir_uses_repo_root(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    subdir = repo / "src" / "package"
    subdir.mkdir(parents=True)
    (repo / ".git").mkdir()

    monkeypatch.chdir(subdir)
    assert init_cmd.run() == 0

    assert (repo / ".braid" / "config.toml").is_file()
    assert not (subdir / ".braid").exists()


def test_init_allows_parent_directory_context(tmp_path: Path, monkeypatch):
    container = tmp_path / "Developer"
    child_a = container / "braid"
    child_b = container / "stock-pattern-classifier-orchestrator"
    child_a.mkdir(parents=True)
    child_b.mkdir(parents=True)
    (container / ".git").mkdir()
    (child_a / "pyproject.toml").write_text('[project]\nname = "braid"\n')
    (child_b / "requirements.txt").write_text("pytest\n")

    monkeypatch.chdir(container)
    assert init_cmd.run() == 0

    assert (container / ".braid" / "config.toml").is_file()
    assert 'dataset_id = "Developer"' in (container / ".braid" / "config.toml").read_text()
