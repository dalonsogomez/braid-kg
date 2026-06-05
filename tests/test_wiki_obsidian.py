"""Tests for Obsidian vault export from `braid wiki build --obsidian`."""
from __future__ import annotations

from pathlib import Path

import pytest

from braid.cli import build_parser, main as cli_main
from braid.commands import wiki as wiki_cmd


def _project_with_memory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname = \"project\"\n")
    (root / ".braid" / "config.toml").parent.mkdir(parents=True)
    (root / ".braid" / "config.toml").write_text('dataset_id = "Project"\n')
    memory = root / ".braid" / "memory"
    (memory / "decisions").mkdir(parents=True)
    (memory / "plans").mkdir(parents=True)
    (memory / "MEMORY.md").write_text("# Project Memory\n\n- Canonical note.\n")
    (memory / "decisions" / "0001-test-adr.md").write_text("# ADR 0001\n\nDecision.\n")
    (memory / "plans" / "launch.md").write_text("# Launch Plan\n")
    monkeypatch.chdir(root)
    return root


def _skip_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        wiki_cmd,
        "_generate_obsidian_catalog_pages",
        lambda ctx, vault_root: ([], "DuckLake skipped in test"),
    )


def test_obsidian_default_creates_generated_vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root = _project_with_memory(tmp_path, monkeypatch)
    _skip_catalog(monkeypatch)

    assert wiki_cmd.run(obsidian=True) == 0

    vault = root / ".braid" / "wiki" / "obsidian"
    assert (vault / ".obsidian").is_dir()
    assert (vault / "Braid Home.md").is_file()
    assert (vault / "Memory" / "MEMORY.md").read_text().startswith("# Project Memory")
    assert (vault / "ADRs" / "0001-test-adr.md").is_file()
    assert (vault / "Plans" / "launch.md").is_file()
    home = (vault / "Braid Home.md").read_text()
    assert "[[Memory/MEMORY|Project Memory]]" in home
    assert "DuckLake skipped in test" in home


def test_obsidian_output_creates_new_vault_with_obsidian_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _project_with_memory(tmp_path, monkeypatch)
    _skip_catalog(monkeypatch)
    out = tmp_path / "new-vault"

    assert wiki_cmd.run(output_dir=str(out), obsidian=True) == 0

    assert (out / ".obsidian").is_dir()
    assert (out / "Braid Home.md").is_file()
    assert (out / "Memory" / "MEMORY.md").is_file()


def test_obsidian_existing_vault_writes_only_managed_subfolder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _project_with_memory(tmp_path, monkeypatch)
    _skip_catalog(monkeypatch)
    vault = tmp_path / "existing-vault"
    vault.mkdir()
    (vault / "Personal.md").write_text("# Personal\n")

    assert wiki_cmd.run(obsidian=True, vault_dir=str(vault)) == 0

    managed = vault / "Braid" / "Project"
    assert (vault / "Personal.md").read_text() == "# Personal\n"
    assert not (vault / ".obsidian").exists()
    assert (managed / "Braid Home.md").is_file()
    assert (managed / "Memory" / "MEMORY.md").is_file()


def test_obsidian_output_and_vault_are_incompatible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
):
    _project_with_memory(tmp_path, monkeypatch)

    assert wiki_cmd.run(output_dir=str(tmp_path / "out"), obsidian=True, vault_dir=str(tmp_path / "vault")) == 2

    assert "mutually exclusive" in capsys.readouterr().err


def test_obsidian_catalog_failure_does_not_block_human_memory_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root = _project_with_memory(tmp_path, monkeypatch)

    def fail_catalog(ctx, vault_root):
        raise ImportError("ducklake unavailable")

    monkeypatch.setattr(wiki_cmd, "_generate_obsidian_catalog_pages", fail_catalog)

    assert wiki_cmd.run(obsidian=True) == 0

    vault = root / ".braid" / "wiki" / "obsidian"
    assert (vault / "Memory" / "MEMORY.md").is_file()
    assert "ducklake unavailable" in (vault / "Braid Home.md").read_text()


def test_wiki_vault_requires_obsidian(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys):
    _project_with_memory(tmp_path, monkeypatch)

    assert wiki_cmd.run(vault_dir=str(tmp_path / "vault")) == 2

    assert "--vault requires --obsidian" in capsys.readouterr().err


def test_wiki_help_includes_obsidian(capsys):
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args(["wiki", "--help"])

    assert exc.value.code == 0
    assert "--obsidian" in capsys.readouterr().out


def test_cli_rejects_output_and_vault_together(tmp_path: Path):
    with pytest.raises(SystemExit) as exc:
        cli_main(
            [
                "wiki",
                "build",
                "--obsidian",
                "--output",
                str(tmp_path / "out"),
                "--vault",
                str(tmp_path / "vault"),
            ]
        )

    assert exc.value.code == 2
