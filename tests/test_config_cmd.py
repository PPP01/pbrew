import os
import tomlkit
from unittest.mock import patch
from click.testing import CliRunner
from pbrew.cli import main


def _invoke(prefix, tmp_path, *args):
    runner = CliRunner()
    env = {"XDG_CONFIG_HOME": str(tmp_path / "config"), "EDITOR": "true"}
    with patch.dict(os.environ, env):
        return runner.invoke(main, ["--prefix", str(prefix)] + list(args))


# ---------------------------------------------------------------------------
# config show
# ---------------------------------------------------------------------------

def test_config_show_prints_default_cascade(tmp_path):
    result = _invoke(tmp_path, tmp_path, "config", "show", "8.4")
    assert result.exit_code == 0, result.output
    assert "build" in result.output
    assert "variants" in result.output


def test_config_show_with_named_variant(tmp_path):
    cfgs = tmp_path / "configs"
    cfgs.mkdir(parents=True)
    (cfgs / "production.toml").write_text(
        tomlkit.dumps({"build": {"jobs": 4}})
    )
    result = _invoke(tmp_path, tmp_path, "config", "show", "8.4", "--named", "production")
    assert result.exit_code == 0, result.output
    assert "production" in result.output or "4" in result.output


# ---------------------------------------------------------------------------
# config edit
# ---------------------------------------------------------------------------

def test_config_edit_creates_template_when_missing(tmp_path):
    # EDITOR=true beendet sofort, ändert nichts
    result = _invoke(tmp_path, tmp_path, "config", "edit", "8.4")
    assert result.exit_code == 0, result.output
    config_file = tmp_path / "configs" / "8.4.toml"
    assert config_file.exists()
    # Template enthält Basis-Struktur
    data = tomlkit.loads(config_file.read_text())
    assert "build" in data


def test_config_edit_respects_named(tmp_path):
    result = _invoke(tmp_path, tmp_path, "config", "edit", "8.4", "--named", "prod")
    assert result.exit_code == 0, result.output
    config_file = tmp_path / "configs" / "prod.toml"
    assert config_file.exists()


def test_config_edit_does_not_overwrite_existing(tmp_path):
    cfgs = tmp_path / "configs"
    cfgs.mkdir(parents=True)
    config_file = cfgs / "8.4.toml"
    config_file.write_text('custom = "value"\n')
    result = _invoke(tmp_path, tmp_path, "config", "edit", "8.4")
    assert result.exit_code == 0, result.output
    # Custom-Inhalt bleibt erhalten (EDITOR=true schreibt nicht)
    assert 'custom = "value"' in config_file.read_text()
