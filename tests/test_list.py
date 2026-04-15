import json
import os
from unittest.mock import patch
from click.testing import CliRunner
from pbrew.cli import main


def _setup(prefix, family, active_version, config_name=None):
    """Legt einen minimalen installierten State an."""
    vdir = prefix / "versions" / active_version
    (vdir / "bin").mkdir(parents=True)
    (vdir / "bin" / "php").write_text("#!/bin/bash\n")

    state_dir = prefix / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    installed_entry = {}
    if config_name:
        installed_entry["config_name"] = config_name
    (state_dir / f"{family}.json").write_text(json.dumps({
        "active": active_version,
        "installed": {active_version: installed_entry},
    }))


def _invoke(prefix, tmp_path):
    runner = CliRunner()
    with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / "config")}):
        return runner.invoke(main, ["--prefix", str(prefix), "list"])


# ---------------------------------------------------------------------------
# list zeigt Config-Spalte
# ---------------------------------------------------------------------------

def test_list_shows_config_column(tmp_path):
    _setup(tmp_path, "8.4", "8.4.22", config_name="dev")
    result = _invoke(tmp_path, tmp_path)
    assert result.exit_code == 0, result.output
    assert "Config" in result.output
    assert "dev" in result.output


def test_list_shows_dash_for_legacy_install_without_config(tmp_path):
    """Installs ohne config_name zeigen — in der Config-Spalte."""
    _setup(tmp_path, "8.3", "8.3.10")  # kein config_name
    result = _invoke(tmp_path, tmp_path)
    assert result.exit_code == 0, result.output
    assert "8.3.10" in result.output
    assert "—" in result.output


def test_list_shows_correct_config_per_family(tmp_path):
    """Mehrere Familien mit unterschiedlichen Configs zeigen korrekt an."""
    _setup(tmp_path, "8.4", "8.4.22", config_name="dev")
    _setup(tmp_path, "8.3", "8.3.10", config_name="prod")
    result = _invoke(tmp_path, tmp_path)
    assert result.exit_code == 0, result.output
    # Beide Configs müssen im Output erscheinen
    assert "dev" in result.output
    assert "prod" in result.output
