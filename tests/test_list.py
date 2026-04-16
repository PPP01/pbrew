import json
import os
from unittest.mock import patch
from click.testing import CliRunner
from pbrew.cli import main


def _make_prefix(prefix, families: dict):
    """families = {family: {version: config_name or None, ...}, active_version: str}

    Kurzform: {family: [v1, v2]} → erste Version ist aktiv, config_name=None
    """
    state_dir = prefix / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    for family, spec in families.items():
        if isinstance(spec, list):
            versions = spec
            active = versions[0]
            config_map = {v: None for v in versions}
        else:
            versions = list(spec["versions"].keys())
            active = spec["active"]
            config_map = spec["versions"]

        for v in versions:
            vdir = prefix / "versions" / v
            (vdir / "bin").mkdir(parents=True, exist_ok=True)
            (vdir / "bin" / "php").write_text("#!/bin/bash\n")

        installed = {v: ({"config_name": c} if c else {}) for v, c in config_map.items()}
        (state_dir / f"{family}.json").write_text(json.dumps({
            "active": active,
            "installed": installed,
        }))


def _invoke(prefix, tmp_path):
    runner = CliRunner()
    with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / "config")}):
        return runner.invoke(main, ["--prefix", str(prefix), "list"])


# ---------------------------------------------------------------------------
# list zeigt Config-Spalte
# ---------------------------------------------------------------------------

def test_list_shows_config_column(tmp_path):
    _make_prefix(tmp_path, {"8.4": {"versions": {"8.4.22": "dev"}, "active": "8.4.22"}})
    result = _invoke(tmp_path, tmp_path)
    assert result.exit_code == 0, result.output
    assert "Config" in result.output
    assert "dev" in result.output


def test_list_shows_dash_for_legacy_install_without_config(tmp_path):
    """Installs ohne config_name zeigen — in der Config-Spalte."""
    _make_prefix(tmp_path, {"8.3": ["8.3.10"]})
    result = _invoke(tmp_path, tmp_path)
    assert result.exit_code == 0, result.output
    assert "8.3.10" in result.output
    assert "—" in result.output


def test_list_shows_correct_config_per_family(tmp_path):
    """Mehrere Familien mit unterschiedlichen Configs zeigen korrekt an."""
    _make_prefix(tmp_path, {
        "8.4": {"versions": {"8.4.22": "dev"}, "active": "8.4.22"},
        "8.3": {"versions": {"8.3.10": "prod"}, "active": "8.3.10"},
    })
    result = _invoke(tmp_path, tmp_path)
    assert result.exit_code == 0, result.output
    assert "dev" in result.output
    assert "prod" in result.output


# ---------------------------------------------------------------------------
# Alle installierten Versionen einer Family erscheinen
# ---------------------------------------------------------------------------

def test_list_shows_all_versions_in_family(tmp_path):
    """Beide 8.4-Versionen müssen im Output erscheinen."""
    _make_prefix(tmp_path, {
        "8.4": {
            "versions": {"8.4.19": "default", "8.4.20": "default"},
            "active": "8.4.19",
        },
    })
    result = _invoke(tmp_path, tmp_path)
    assert result.exit_code == 0, result.output
    assert "8.4.19" in result.output
    assert "8.4.20" in result.output


def test_list_marks_active_version(tmp_path):
    """Die aktive Version ist mit ▸ markiert."""
    _make_prefix(tmp_path, {
        "8.4": {
            "versions": {"8.4.19": "default", "8.4.20": "default"},
            "active": "8.4.19",
        },
    })
    result = _invoke(tmp_path, tmp_path)
    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    active_line = next(l for l in lines if "8.4.19" in l)
    inactive_line = next(l for l in lines if "8.4.20" in l)
    assert "▸" in active_line
    assert "▸" not in inactive_line


def test_list_shows_family_once_for_multiple_versions(tmp_path):
    """Der Family-Name erscheint nur in der ersten Zeile der Gruppe."""
    _make_prefix(tmp_path, {
        "8.4": {
            "versions": {"8.4.19": "default", "8.4.20": "default"},
            "active": "8.4.19",
        },
    })
    result = _invoke(tmp_path, tmp_path)
    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    # Versionen sind absteigend sortiert: 8.4.20 ist die erste Zeile (Family-Label)
    first_row = next(l for l in lines if "8.4.20" in l)
    second_row = next(l for l in lines if "8.4.19" in l)
    assert first_row.startswith("  8.4 ")
    assert not second_row.startswith("  8.4 ")


def test_list_shows_config_per_version(tmp_path):
    """Jede Version zeigt ihre eigene Config."""
    _make_prefix(tmp_path, {
        "8.4": {
            "versions": {"8.4.19": "production", "8.4.20": "dev"},
            "active": "8.4.19",
        },
    })
    result = _invoke(tmp_path, tmp_path)
    assert result.exit_code == 0, result.output
    assert "production" in result.output
    assert "dev" in result.output
