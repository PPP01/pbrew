import json
import os
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from pbrew.cli import main


def _setup_version(prefix, family="8.4", version="8.4.22"):
    (prefix / "versions" / version / "bin").mkdir(parents=True)
    (prefix / "versions" / version / "bin" / "php").touch()
    state = prefix / "state"
    state.mkdir(parents=True, exist_ok=True)
    (state / f"{family}.json").write_text(json.dumps({"active": version}))
    (state / "global.json").write_text(json.dumps({"default_family": family}))


def _invoke(prefix, tmp_path, *args):
    runner = CliRunner()
    env = {"XDG_CONFIG_HOME": str(tmp_path / "config")}
    with patch.dict(os.environ, env):
        return runner.invoke(main, ["--prefix", str(prefix)] + list(args))


def test_ext_add_requires_tty(tmp_path):
    _setup_version(tmp_path)
    with patch("pbrew.cli.ext._query_extensions", return_value=({}, [], [])), \
         patch("pbrew.cli.ext._is_tty", return_value=False):
        result = _invoke(tmp_path, tmp_path, "ext", "add", "8.4")
    assert result.exit_code != 0
    assert "TTY" in result.output or "interaktiv" in result.output.lower()


def test_ext_add_activates_local_so(tmp_path):
    _setup_version(tmp_path)
    confd = tmp_path / "etc" / "conf.d" / "8.4"
    confd.mkdir(parents=True)

    with patch("pbrew.cli.ext._query_extensions", return_value=({}, ["redis"], [])), \
         patch("pbrew.cli.ext._is_tty", return_value=True), \
         patch("pbrew.cli.ext._prompt_multiselect",
               return_value={"Lokale .so": ["redis"]}):
        result = _invoke(tmp_path, tmp_path, "ext", "add", "8.4")

    assert result.exit_code == 0, result.output
    assert (confd / "redis.ini").exists()
    assert "redis" in result.output


def test_ext_add_installs_pecl(tmp_path):
    _setup_version(tmp_path)
    with patch("pbrew.cli.ext._query_extensions", return_value=({}, [], [])), \
         patch("pbrew.cli.ext._is_tty", return_value=True), \
         patch("pbrew.cli.ext._prompt_multiselect",
               return_value={"PECL": ["xdebug"]}), \
         patch("pbrew.cli.ext._install_pecl_extension") as inst:
        result = _invoke(tmp_path, tmp_path, "ext", "add", "8.4")
    assert result.exit_code == 0, result.output
    inst.assert_called_once()
    assert inst.call_args.args[1] == "xdebug"


def test_ext_add_rebuild_adds_to_config(tmp_path):
    _setup_version(tmp_path)
    configs = tmp_path / "configs"
    configs.mkdir()
    (configs / "default.toml").write_text(
        '[build]\nvariants=["default", "opcache"]\n'
    )
    with patch("pbrew.cli.ext._query_extensions", return_value=({}, [], ["intl"])), \
         patch("pbrew.cli.ext._is_tty", return_value=True), \
         patch("pbrew.cli.ext._prompt_multiselect",
               return_value={"Standard (Rebuild)": ["intl"]}), \
         patch("pbrew.cli.ext._prompt_config_choice",
               return_value=configs / "default.toml"):
        result = _invoke(tmp_path, tmp_path, "ext", "add", "8.4")
    assert result.exit_code == 0, result.output
    assert "Rebuild" in result.output or "rebuild" in result.output.lower()
    text = (configs / "default.toml").read_text()
    assert "intl" in text


def test_ext_add_rebuild_creates_new_config(tmp_path):
    _setup_version(tmp_path)
    configs = tmp_path / "configs"
    configs.mkdir()
    new_cfg = configs / "myprofile.toml"
    # Neue Config existiert noch nicht
    assert not new_cfg.exists()
    with patch("pbrew.cli.ext._query_extensions", return_value=({}, [], ["intl"])), \
         patch("pbrew.cli.ext._is_tty", return_value=True), \
         patch("pbrew.cli.ext._prompt_multiselect",
               return_value={"Standard (Rebuild)": ["intl"]}), \
         patch("pbrew.cli.ext._prompt_config_choice",
               return_value=new_cfg):
        result = _invoke(tmp_path, tmp_path, "ext", "add", "8.4")
    assert result.exit_code == 0, result.output
    assert new_cfg.exists()
    import tomlkit
    data = tomlkit.loads(new_cfg.read_text()).unwrap()
    assert "intl" in data["build"]["variants"]
    # Kein active_variants-Überlauf: nur rebuild_picks sollen drin sein
    assert "opcache" not in data["build"]["variants"]


def test_ext_add_nothing_selected(tmp_path):
    _setup_version(tmp_path)
    with patch("pbrew.cli.ext._query_extensions", return_value=({}, ["redis"], [])), \
         patch("pbrew.cli.ext._is_tty", return_value=True), \
         patch("pbrew.cli.ext._prompt_multiselect", return_value={}):
        result = _invoke(tmp_path, tmp_path, "ext", "add", "8.4")
    assert result.exit_code == 0
    assert "Nichts" in result.output or "abgebrochen" in result.output.lower()
