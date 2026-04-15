import pytest
import tomlkit
from pathlib import Path
from pbrew.core.config import load_config, save_config, init_default_config, DEFAULT_CONFIG


def test_load_config_returns_defaults_when_no_files(tmp_path):
    cfg = load_config(tmp_path / "configs", "8.4")
    assert cfg["build"]["jobs"] == "auto"
    assert "fpm" in cfg["build"]["variants"]
    assert cfg["xdebug"]["enabled"] is False


def test_load_config_merges_family_override(tmp_path):
    configs = tmp_path / "configs"
    configs.mkdir()
    family_conf = {"build": {"extra": {"with-config-file-scan-dir": "/custom/scan"}}}
    (configs / "8.4.toml").write_text(tomlkit.dumps(family_conf))

    cfg = load_config(configs, "8.4")
    assert cfg["build"]["extra"]["with-config-file-scan-dir"] == "/custom/scan"
    # Default variants should still be present
    assert "fpm" in cfg["build"]["variants"]


def test_load_config_named_overrides_family(tmp_path):
    configs = tmp_path / "configs"
    configs.mkdir()
    (configs / "8.4.toml").write_text(tomlkit.dumps({"build": {"jobs": 4}}))
    (configs / "production.toml").write_text(tomlkit.dumps({"build": {"jobs": 2}}))

    cfg = load_config(configs, "8.4", named="production")
    assert cfg["build"]["jobs"] == 2


def test_load_config_named_missing_falls_back_to_family(tmp_path):
    configs = tmp_path / "configs"
    configs.mkdir()
    (configs / "8.4.toml").write_text(tomlkit.dumps({"build": {"jobs": 6}}))

    cfg = load_config(configs, "8.4", named="nonexistent")
    assert cfg["build"]["jobs"] == 6


def test_save_config_writes_toml(tmp_path):
    configs = tmp_path / "configs"
    save_config(configs, "test", {"build": {"jobs": 3}})
    loaded = tomlkit.loads((configs / "test.toml").read_text())
    assert loaded["build"]["jobs"] == 3


def test_init_default_config_creates_file(tmp_path):
    configs = tmp_path / "configs"
    init_default_config(configs)
    assert (configs / "default.toml").exists()


def test_init_default_config_does_not_overwrite(tmp_path):
    configs = tmp_path / "configs"
    configs.mkdir()
    (configs / "default.toml").write_text(tomlkit.dumps({"build": {"jobs": 99}}))
    init_default_config(configs)
    loaded = tomlkit.loads((configs / "default.toml").read_text())
    assert loaded["build"]["jobs"] == 99
