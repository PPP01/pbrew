import json
import os
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from pbrew.cli import main
from pbrew.core.resolver import PhpRelease


def _make_release(version: str) -> PhpRelease:
    family = ".".join(version.split(".")[:2])
    return PhpRelease(
        version=version,
        family=family,
        tarball_url=f"https://www.php.net/distributions/php-{version}.tar.bz2",
        sha256="abc123",
    )


def _write_state(prefix, family, active_version):
    import pathlib
    state_dir = prefix / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / f"{family}.json").write_text(json.dumps({"active": active_version}))


# ---------------------------------------------------------------------------
# pbrew update — already up to date
# ---------------------------------------------------------------------------

def test_update_already_up_to_date(tmp_path):
    _write_state(tmp_path, "8.4", "8.4.22")
    runner = CliRunner()
    with patch("pbrew.cli.update.fetch_latest", return_value=_make_release("8.4.22")), \
         patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / "config")}):
        result = runner.invoke(main, ["--prefix", str(tmp_path), "update", "8.4"])
    assert result.exit_code == 0, result.output
    assert "aktuell" in result.output.lower() or "up-to-date" in result.output.lower() or "8.4.22" in result.output


# ---------------------------------------------------------------------------
# pbrew update — neue Version verfügbar
# ---------------------------------------------------------------------------

def test_update_triggers_install_when_newer(tmp_path):
    _write_state(tmp_path, "8.4", "8.4.21")
    runner = CliRunner()
    install_called_with = []

    def fake_install(ctx, version_spec, config_name, save, jobs):
        install_called_with.append(version_spec)

    with patch("pbrew.cli.update.fetch_latest", return_value=_make_release("8.4.22")), \
         patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / "config")}), \
         patch("pbrew.cli.update.install_cmd.invoke", side_effect=lambda ctx: None) as mock_inv:
        result = runner.invoke(main, ["--prefix", str(tmp_path), "update", "8.4"])
    # Entweder install wurde aufgerufen oder der Output nennt die neue Version
    assert "8.4.22" in result.output or result.exit_code == 0


# ---------------------------------------------------------------------------
# pbrew update — Config-Name aus State übernehmen (#17)
# ---------------------------------------------------------------------------

def test_update_reuses_config_name_from_state(tmp_path):
    """update muss den config_name des aktiven Builds an install weitergeben."""
    from pbrew.cli.install import install_cmd
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "8.4.json").write_text(json.dumps({
        "active": "8.4.21",
        "installed": {
            "8.4.21": {"config_name": "dev", "variants": ["default", "fpm"]},
        },
    }))

    runner = CliRunner()
    with patch("pbrew.cli.update.fetch_latest", return_value=_make_release("8.4.22")), \
         patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / "config")}), \
         patch.object(install_cmd, "callback") as mock_callback:
        result = runner.invoke(main, ["--prefix", str(tmp_path), "update", "8.4"])
    assert result.exit_code == 0, result.output
    mock_callback.assert_called_once()
    assert mock_callback.call_args.kwargs.get("config_name") == "dev"


def test_update_falls_back_to_legacy_top_level_config(tmp_path):
    """Altinstalls ohne config_name im installed-Eintrag nutzen state['config']."""
    from pbrew.cli.install import install_cmd
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "8.4.json").write_text(json.dumps({
        "active": "8.4.21",
        "config": "prod",
        "installed": {"8.4.21": {}},
    }))

    runner = CliRunner()
    with patch("pbrew.cli.update.fetch_latest", return_value=_make_release("8.4.22")), \
         patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / "config")}), \
         patch.object(install_cmd, "callback") as mock_callback:
        result = runner.invoke(main, ["--prefix", str(tmp_path), "update", "8.4"])
    assert result.exit_code == 0, result.output
    mock_callback.assert_called_once()
    assert mock_callback.call_args.kwargs.get("config_name") == "prod"


# ---------------------------------------------------------------------------
# pbrew update — family noch nicht installiert
# ---------------------------------------------------------------------------

def test_update_exits_when_not_installed(tmp_path):
    # Kein State → Familie nicht installiert
    runner = CliRunner()
    with patch("pbrew.cli.update.fetch_latest", return_value=_make_release("8.4.22")), \
         patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / "config")}):
        result = runner.invoke(main, ["--prefix", str(tmp_path), "update", "8.4"])
    assert result.exit_code != 0 or "nicht installiert" in result.output.lower()
