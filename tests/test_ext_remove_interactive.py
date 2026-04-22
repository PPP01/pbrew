import json
import os
import tomlkit
from unittest.mock import patch
from click.testing import CliRunner
from pbrew.cli import main


def _setup(prefix, family="8.4", version="8.4.22"):
    (prefix / "versions" / version / "bin").mkdir(parents=True)
    (prefix / "versions" / version / "bin" / "php").touch()
    s = prefix / "state"
    s.mkdir(parents=True, exist_ok=True)
    (s / f"{family}.json").write_text(json.dumps({"active": version}))
    (s / "global.json").write_text(json.dumps({"default_family": family}))


def _invoke(prefix, tmp_path, *args):
    runner = CliRunner()
    env = {"XDG_CONFIG_HOME": str(tmp_path / "config")}
    with patch.dict(os.environ, env):
        return runner.invoke(main, ["--prefix", str(prefix)] + list(args))


def test_ext_remove_positional_still_works(tmp_path):
    _setup(tmp_path)
    confd = tmp_path / "etc" / "conf.d" / "8.4"
    confd.mkdir(parents=True)
    (confd / "apcu.ini").write_text("extension=apcu.so\n")
    result = _invoke(tmp_path, tmp_path, "ext", "remove", "apcu", "8.4")
    assert result.exit_code == 0, result.output
    assert (confd / "apcu.ini.disabled").exists()


def test_ext_remove_interactive_active_ini(tmp_path):
    _setup(tmp_path)
    confd = tmp_path / "etc" / "conf.d" / "8.4"
    confd.mkdir(parents=True)
    (confd / "apcu.ini").write_text("extension=apcu.so\n")

    with patch("pbrew.cli.ext._query_extensions",
               return_value=({"apcu": ("apcu", "5.1")}, [], [])), \
         patch("pbrew.cli.ext._is_tty", return_value=True), \
         patch("pbrew.cli.ext._prompt_multiselect",
               return_value={"Aktive pbrew-INI": ["apcu"]}):
        result = _invoke(tmp_path, tmp_path, "ext", "remove", "8.4")
    assert result.exit_code == 0, result.output
    assert (confd / "apcu.ini.disabled").exists()


def test_ext_remove_interactive_disabled_ini_deletes_file(tmp_path):
    _setup(tmp_path)
    confd = tmp_path / "etc" / "conf.d" / "8.4"
    confd.mkdir(parents=True)
    (confd / "old.ini.disabled").write_text("x\n")

    with patch("pbrew.cli.ext._query_extensions",
               return_value=({}, [], [])), \
         patch("pbrew.cli.ext._is_tty", return_value=True), \
         patch("pbrew.cli.ext._prompt_multiselect",
               return_value={"Inaktive pbrew-INI": ["old"]}):
        result = _invoke(tmp_path, tmp_path, "ext", "remove", "8.4")
    assert result.exit_code == 0, result.output
    assert not (confd / "old.ini.disabled").exists()


def test_ext_remove_interactive_removes_variant(tmp_path):
    _setup(tmp_path)
    configs = tmp_path / "configs"
    configs.mkdir()
    (configs / "default.toml").write_text(
        '[build]\nvariants=["default", "intl", "opcache"]\n'
    )
    with patch("pbrew.cli.ext._query_extensions",
               return_value=({"intl": ("intl", "74.2")}, [], [])), \
         patch("pbrew.cli.ext._is_tty", return_value=True), \
         patch("pbrew.cli.ext._prompt_multiselect",
               return_value={"Kompiliert (Rebuild)": ["intl"]}), \
         patch("pbrew.cli.ext._prompt_config_choice",
               return_value=configs / "default.toml"):
        result = _invoke(tmp_path, tmp_path, "ext", "remove", "8.4")
    assert result.exit_code == 0, result.output
    data = tomlkit.loads((configs / "default.toml").read_text()).unwrap()
    assert "intl" not in data["build"]["variants"]
    assert "Rebuild" in result.output or "rebuild" in result.output.lower()
