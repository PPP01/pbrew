"""Tests für pbrew use, switch, unswitch mit ENV-Variable-Architektur."""
import json
import os
from pathlib import Path
from unittest.mock import patch
from click.testing import CliRunner
from pbrew.cli import main


def _make_prefix(tmp_path: Path, family: str, versions: list[str], active: str) -> Path:
    prefix = tmp_path / "pbrew"
    state_dir = prefix / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    for v in versions:
        vdir = prefix / "versions" / v
        (vdir / "bin").mkdir(parents=True, exist_ok=True)
        (vdir / "bin" / "php").write_text("#!/bin/bash\n")
        (vdir / "bin" / "php").chmod(0o755)

    installed = {v: {"config_name": "default"} for v in versions}
    (state_dir / f"{family}.json").write_text(json.dumps({
        "active": active,
        "installed": installed,
    }))
    (prefix / "bin").mkdir(parents=True, exist_ok=True)
    return prefix


def _invoke(prefix, args):
    runner = CliRunner()
    with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(prefix.parent / "config")}):
        return runner.invoke(main, ["--prefix", str(prefix)] + args)


# ---------------------------------------------------------------------------
# pbrew use
# ---------------------------------------------------------------------------

def test_use_family_emits_pbrew_path(tmp_path):
    """pbrew use 8.4 gibt PBREW_PATH für die aktive Version aus."""
    prefix = _make_prefix(tmp_path, "8.4", ["8.4.19"], "8.4.19")
    result = _invoke(prefix, ["use", "8.4"])
    assert result.exit_code == 0, result.output
    assert "PBREW_PATH" in result.output
    assert "8.4.19" in result.output
    assert "PBREW_ACTIVE" in result.output


def test_use_family_pbrew_path_points_to_version_bin(tmp_path):
    """PBREW_PATH zeigt auf versions/<version>/bin."""
    prefix = _make_prefix(tmp_path, "8.4", ["8.4.19"], "8.4.19")
    result = _invoke(prefix, ["use", "8.4"])
    assert "versions/8.4.19/bin" in result.output


def test_use_pinned_emits_pbrew_path(tmp_path):
    """pbrew use 8.4.19 gibt PBREW_PATH für exakt diese Version aus."""
    prefix = _make_prefix(tmp_path, "8.4", ["8.4.19", "8.4.20"], "8.4.20")
    result = _invoke(prefix, ["use", "8.4.19"])
    assert result.exit_code == 0, result.output
    assert "versions/8.4.19/bin" in result.output
    assert 'PBREW_ACTIVE="8.4.19"' in result.output


def test_use_no_path_manipulation(tmp_path):
    """pbrew use darf KEIN export PATH= oder hash -r ausgeben."""
    prefix = _make_prefix(tmp_path, "8.4", ["8.4.19"], "8.4.19")
    result = _invoke(prefix, ["use", "8.4"])
    assert "export PATH=" not in result.output
    assert "hash -r" not in result.output


def test_use_not_installed_fails(tmp_path):
    prefix = _make_prefix(tmp_path, "8.4", ["8.4.19"], "8.4.19")
    result = _invoke(prefix, ["use", "8.4.99"])
    assert result.exit_code != 0


def test_use_family_not_installed_fails(tmp_path):
    prefix = _make_prefix(tmp_path, "8.4", ["8.4.19"], "8.4.19")
    result = _invoke(prefix, ["use", "8.3"])  # 8.3 nicht installiert
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# pbrew switch
# ---------------------------------------------------------------------------

def test_switch_emits_pbrew_path(tmp_path):
    """pbrew switch gibt PBREW_PATH + PBREW_ACTIVE aus."""
    prefix = _make_prefix(tmp_path, "8.4", ["8.4.19", "8.4.20"], "8.4.20")
    with patch("pbrew.cli.use.write_naked_wrappers"), \
         patch("pbrew.cli.use.write_versioned_wrappers"), \
         patch("pbrew.core.wrappers.write_phpd_wrapper"):
        result = _invoke(prefix, ["switch", "8.4.19"])
    assert result.exit_code == 0, result.output
    assert "PBREW_PATH" in result.output
    assert "PBREW_ACTIVE" in result.output


def test_switch_pinned_writes_switch_file(tmp_path):
    """pbrew switch 8.4.19 schreibt .switch-Datei."""
    prefix = _make_prefix(tmp_path, "8.4", ["8.4.19", "8.4.20"], "8.4.20")
    with patch("pbrew.cli.use.write_naked_wrappers"), \
         patch("pbrew.cli.use.write_versioned_wrappers"), \
         patch("pbrew.core.wrappers.write_phpd_wrapper"):
        result = _invoke(prefix, ["switch", "8.4.19"])
    assert result.exit_code == 0, result.output
    switch_file = prefix / ".switch"
    assert switch_file.exists(), ".switch nicht angelegt"
    content = switch_file.read_text()
    assert "PBREW_PATH" in content
    assert "8.4.19" in content


def test_switch_switch_file_is_sourceable(tmp_path):
    """.switch-Datei enthält export-Statements."""
    prefix = _make_prefix(tmp_path, "8.4", ["8.4.19"], "8.4.19")
    with patch("pbrew.cli.use.write_naked_wrappers"), \
         patch("pbrew.cli.use.write_versioned_wrappers"), \
         patch("pbrew.core.wrappers.write_phpd_wrapper"):
        _invoke(prefix, ["switch", "8.4.19"])
    content = (prefix / ".switch").read_text()
    assert content.startswith("export ")


def test_switch_pinned_updates_state(tmp_path):
    """pbrew switch 8.4.19 setzt 8.4.19 als active in state."""
    prefix = _make_prefix(tmp_path, "8.4", ["8.4.19", "8.4.20"], "8.4.20")
    with patch("pbrew.cli.use.write_naked_wrappers"), \
         patch("pbrew.cli.use.write_versioned_wrappers"), \
         patch("pbrew.core.wrappers.write_phpd_wrapper"):
        result = _invoke(prefix, ["switch", "8.4.19"])
    assert result.exit_code == 0, result.output
    state = json.loads((prefix / "state" / "8.4.json").read_text())
    assert state["active"] == "8.4.19"


def test_switch_not_installed_fails(tmp_path):
    prefix = _make_prefix(tmp_path, "8.4", ["8.4.19"], "8.4.19")
    result = _invoke(prefix, ["switch", "8.4.99"])
    assert result.exit_code != 0


def test_switch_family_uses_active_version(tmp_path):
    """pbrew switch 8.4 nutzt die aktive Patch-Version aus dem State."""
    prefix = _make_prefix(tmp_path, "8.4", ["8.4.19", "8.4.20"], "8.4.20")
    with patch("pbrew.cli.use.write_naked_wrappers"), \
         patch("pbrew.cli.use.write_versioned_wrappers"), \
         patch("pbrew.core.wrappers.write_phpd_wrapper"):
        result = _invoke(prefix, ["switch", "8.4"])
    assert result.exit_code == 0, result.output
    assert "8.4.20" in result.output  # aktive Version im Output


def test_switch_family_writes_switch_file(tmp_path):
    """pbrew switch 8.4 (Family) schreibt ebenfalls .switch-Datei."""
    prefix = _make_prefix(tmp_path, "8.4", ["8.4.19", "8.4.20"], "8.4.20")
    with patch("pbrew.cli.use.write_naked_wrappers"), \
         patch("pbrew.cli.use.write_versioned_wrappers"), \
         patch("pbrew.core.wrappers.write_phpd_wrapper"):
        result = _invoke(prefix, ["switch", "8.4"])
    assert result.exit_code == 0, result.output
    switch_file = prefix / ".switch"
    assert switch_file.exists(), ".switch nicht angelegt"
    assert "8.4.20" in switch_file.read_text()


# ---------------------------------------------------------------------------
# pbrew unswitch
# ---------------------------------------------------------------------------

def test_unswitch_emits_unset(tmp_path):
    """pbrew unswitch gibt unset PBREW_PATH PBREW_ACTIVE aus."""
    prefix = _make_prefix(tmp_path, "8.4", ["8.4.19"], "8.4.19")
    result = _invoke(prefix, ["unswitch"])
    assert result.exit_code == 0, result.output
    assert "unset PBREW_PATH PBREW_ACTIVE" in result.output


def test_unswitch_deletes_switch_file(tmp_path):
    """pbrew unswitch löscht .switch wenn vorhanden."""
    prefix = _make_prefix(tmp_path, "8.4", ["8.4.19"], "8.4.19")
    switch_file = prefix / ".switch"
    switch_file.write_text('export PBREW_PATH="/some/path"\n')
    result = _invoke(prefix, ["unswitch"])
    assert result.exit_code == 0, result.output
    assert not switch_file.exists()


def test_unswitch_without_switch_file_succeeds(tmp_path):
    """pbrew unswitch läuft ohne .switch-Datei fehlerfrei durch."""
    prefix = _make_prefix(tmp_path, "8.4", ["8.4.19"], "8.4.19")
    result = _invoke(prefix, ["unswitch"])
    assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# fish .switch.fish
# ---------------------------------------------------------------------------

def test_switch_writes_switch_fish_file(tmp_path):
    """.switch.fish wird mit fish-kompatibler set -x Syntax geschrieben."""
    prefix = _make_prefix(tmp_path, "8.4", ["8.4.19"], "8.4.19")
    with patch("pbrew.cli.use.write_naked_wrappers"), \
         patch("pbrew.cli.use.write_versioned_wrappers"), \
         patch("pbrew.core.wrappers.write_phpd_wrapper"):
        result = _invoke(prefix, ["switch", "8.4.19"])
    assert result.exit_code == 0, result.output
    switch_fish_file = prefix / ".switch.fish"
    assert switch_fish_file.exists(), ".switch.fish nicht angelegt"
    content = switch_fish_file.read_text()
    assert "set -x PBREW_PATH" in content
    assert "set -x PBREW_ACTIVE" in content
    assert "8.4.19" in content
    # Kein Bash-export-Syntax
    assert "export " not in content


def test_unswitch_deletes_switch_fish_file(tmp_path):
    """pbrew unswitch löscht .switch.fish wenn vorhanden."""
    prefix = _make_prefix(tmp_path, "8.4", ["8.4.19"], "8.4.19")
    switch_fish_file = prefix / ".switch.fish"
    switch_fish_file.write_text('set -x PBREW_PATH "/some/path"\n')
    result = _invoke(prefix, ["unswitch"])
    assert result.exit_code == 0, result.output
    assert not switch_fish_file.exists()
