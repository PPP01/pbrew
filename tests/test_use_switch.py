"""Tests für pbrew use und pbrew switch mit Family- und Patch-Version."""
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

    # Bin-Dir mit versioned wrapper anlegen
    bin_dir = prefix / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)

    return prefix


def _invoke(prefix, args):
    runner = CliRunner()
    with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(prefix.parent / "config")}):
        return runner.invoke(main, ["--prefix", str(prefix)] + args)


# ---------------------------------------------------------------------------
# pbrew use: Family-Angabe (bisheriges Verhalten)
# ---------------------------------------------------------------------------

def test_use_family_exports_pbrew_bin(tmp_path):
    prefix = _make_prefix(tmp_path, "8.4", ["8.4.19"], "8.4.19")
    result = _invoke(prefix, ["use", "8.4"])
    assert result.exit_code == 0, result.output
    assert "bin" in result.output
    assert "hash -r" in result.output


# ---------------------------------------------------------------------------
# pbrew use: Gepinnte Patch-Version → direkter Pfad in PATH
# ---------------------------------------------------------------------------

def test_use_pinned_version_exports_version_bin_path(tmp_path):
    """pbrew use 8.4.19 muss versions/8.4.19/bin in PATH exportieren."""
    prefix = _make_prefix(tmp_path, "8.4", ["8.4.19", "8.4.20"], "8.4.20")
    result = _invoke(prefix, ["use", "8.4.19"])
    assert result.exit_code == 0, result.output
    assert "8.4.19" in result.output
    assert "versions" in result.output
    assert "hash -r" in result.output


def test_use_pinned_version_not_installed_fails(tmp_path):
    prefix = _make_prefix(tmp_path, "8.4", ["8.4.19"], "8.4.19")
    result = _invoke(prefix, ["use", "8.4.99"])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# pbrew switch: Gepinnte Patch-Version → Wrapper + State aktualisieren
# ---------------------------------------------------------------------------

def test_switch_pinned_version_updates_state(tmp_path):
    """pbrew switch 8.4.19 setzt 8.4.19 als active in state."""
    prefix = _make_prefix(tmp_path, "8.4", ["8.4.19", "8.4.20"], "8.4.20")
    with patch("pbrew.cli.use.write_naked_wrappers"), \
         patch("pbrew.cli.use.write_versioned_wrappers"):
        result = _invoke(prefix, ["switch", "8.4.19"])
    assert result.exit_code == 0, result.output
    state = json.loads((prefix / "state" / "8.4.json").read_text())
    assert state["active"] == "8.4.19"


def test_switch_pinned_version_not_installed_fails(tmp_path):
    prefix = _make_prefix(tmp_path, "8.4", ["8.4.19"], "8.4.19")
    result = _invoke(prefix, ["switch", "8.4.99"])
    assert result.exit_code != 0


def test_switch_family_uses_active_version(tmp_path):
    """pbrew switch 8.4 nutzt weiterhin state.active."""
    prefix = _make_prefix(tmp_path, "8.4", ["8.4.19", "8.4.20"], "8.4.20")
    with patch("pbrew.cli.use.write_naked_wrappers") as mock_wrap, \
         patch("pbrew.cli.use.write_versioned_wrappers"):
        result = _invoke(prefix, ["switch", "8.4"])
    assert result.exit_code == 0, result.output
    # php-Wrapper wird mit der aktiven Version aufgerufen
    mock_wrap.assert_called_once()
    _, call_args, _ = mock_wrap.mock_calls[0]
    assert "8.4.20" in call_args
