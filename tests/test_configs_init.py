import os
from pathlib import Path
from unittest.mock import patch
from click.testing import CliRunner
from pbrew.cli import main
from pbrew.core.config import init_profiles, PRESETS


# ---------------------------------------------------------------------------
# init_profiles
# ---------------------------------------------------------------------------

def test_init_profiles_creates_all_four(tmp_path):
    created = init_profiles(tmp_path)
    assert set(created) == {"minimal", "standard", "dev", "prod"}
    for name in ("minimal", "standard", "dev", "prod"):
        assert (tmp_path / f"{name}.toml").exists()


def test_init_profiles_does_not_overwrite_existing(tmp_path):
    import tomlkit
    (tmp_path / "dev.toml").write_text(tomlkit.dumps({"custom": True}))
    created = init_profiles(tmp_path)
    assert "dev" not in created
    data = tomlkit.loads((tmp_path / "dev.toml").read_text())
    assert data.get("custom") is True


def test_minimal_has_fewer_variants_than_standard(tmp_path):
    import tomlkit
    init_profiles(tmp_path)
    minimal = tomlkit.loads((tmp_path / "minimal.toml").read_text())
    standard = tomlkit.loads((tmp_path / "standard.toml").read_text())
    assert len(minimal["build"]["variants"]) < len(standard["build"]["variants"])


def test_dev_has_xdebug_enabled(tmp_path):
    import tomlkit
    init_profiles(tmp_path)
    dev = tomlkit.loads((tmp_path / "dev.toml").read_text())
    assert dev["xdebug"]["enabled"] is True


def test_prod_has_xdebug_disabled(tmp_path):
    import tomlkit
    init_profiles(tmp_path)
    prod = tomlkit.loads((tmp_path / "prod.toml").read_text())
    assert prod["xdebug"]["enabled"] is False


def test_all_presets_are_valid_config(tmp_path):
    """Jedes Preset lässt sich über load_config laden ohne Fehler."""
    from pbrew.core.config import load_config, init_profiles
    init_profiles(tmp_path)
    for name in PRESETS:
        cfg = load_config(tmp_path, "8.4", named=name)
        assert "build" in cfg
        assert "variants" in cfg["build"]


# ---------------------------------------------------------------------------
# pbrew init — Profiles-Schritt
# ---------------------------------------------------------------------------

def test_init_creates_config_profiles(tmp_path):
    runner = CliRunner()
    prefix = tmp_path / "pbrew"
    with patch.dict(os.environ, {
        "SHELL": "",
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
    }):
        result = runner.invoke(main, ["init"], input=f"{prefix}\n")
    assert result.exit_code == 0, result.output
    configs = prefix / "configs"
    for name in ("minimal", "standard", "dev", "prod"):
        assert (configs / f"{name}.toml").exists(), f"Fehlendes Profil: {name}.toml"
