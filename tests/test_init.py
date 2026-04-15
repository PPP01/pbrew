import os
import tomlkit
from pathlib import Path
from unittest.mock import patch
from click.testing import CliRunner
from pbrew.cli import main


def _invoke(tmp_path, user_input):
    """Ruft `pbrew init` auf mit XDG_CONFIG_HOME in tmp_path."""
    runner = CliRunner()
    with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / "config")}):
        return runner.invoke(main, ["init"], input=user_input)


def test_init_creates_prefix_directories(tmp_path):
    prefix = tmp_path / "mypbrew"
    result = _invoke(tmp_path, str(prefix) + "\n")
    assert result.exit_code == 0, result.output
    for subdir in ("versions", "bin", "etc", "distfiles", "state"):
        assert (prefix / subdir).is_dir(), f"Fehlendes Verzeichnis: {subdir}"


def test_init_writes_global_config(tmp_path):
    prefix = tmp_path / "mypbrew"
    result = _invoke(tmp_path, str(prefix) + "\n")
    assert result.exit_code == 0, result.output
    config_file = tmp_path / "config" / "pbrew" / "config.toml"
    assert config_file.exists(), "config.toml wurde nicht angelegt"
    data = tomlkit.parse(config_file.read_text())
    assert data["core"]["prefix"] == str(prefix)


def test_init_default_prefix_is_dot_pbrew(tmp_path):
    """Enter ohne Eingabe → ~/.pbrew als Standardpräfix."""
    result = _invoke(tmp_path, "\n")
    assert result.exit_code == 0, result.output
    config_file = tmp_path / "config" / "pbrew" / "config.toml"
    data = tomlkit.parse(config_file.read_text())
    assert data["core"]["prefix"].endswith(".pbrew")


def test_init_expands_tilde(tmp_path):
    """Tilde-Notation wird zu absolutem Pfad aufgelöst."""
    result = _invoke(tmp_path, "~/.mypbrew\n")
    assert result.exit_code == 0, result.output
    config_file = tmp_path / "config" / "pbrew" / "config.toml"
    data = tomlkit.parse(config_file.read_text())
    assert not data["core"]["prefix"].startswith("~")


def test_get_prefix_reads_global_config(tmp_path):
    config_home = tmp_path / "config"
    (config_home / "pbrew").mkdir(parents=True)
    doc = tomlkit.document()
    core = tomlkit.table()
    core.add("prefix", str(tmp_path / "custom"))
    doc.add("core", core)
    (config_home / "pbrew" / "config.toml").write_text(tomlkit.dumps(doc))

    with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config_home)}):
        from pbrew.core.paths import get_prefix
        assert get_prefix() == tmp_path / "custom"


def test_get_prefix_env_overrides_config(tmp_path):
    config_home = tmp_path / "config"
    (config_home / "pbrew").mkdir(parents=True)
    doc = tomlkit.document()
    core = tomlkit.table()
    core.add("prefix", str(tmp_path / "config-prefix"))
    doc.add("core", core)
    (config_home / "pbrew" / "config.toml").write_text(tomlkit.dumps(doc))

    with patch.dict(os.environ, {
        "XDG_CONFIG_HOME": str(config_home),
        "PBREW_ROOT": str(tmp_path / "env-prefix"),
    }):
        from pbrew.core.paths import get_prefix
        assert get_prefix() == tmp_path / "env-prefix"
