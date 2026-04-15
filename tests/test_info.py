import json
import os
from unittest.mock import patch
from click.testing import CliRunner
from pbrew.cli import main


def _write_state(prefix, family, data):
    state_dir = prefix / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / f"{family}.json").write_text(json.dumps(data))


def _make_install(prefix, version):
    vdir = prefix / "versions" / version
    (vdir / "bin").mkdir(parents=True)
    (vdir / "bin" / "php").write_text("#!/bin/bash\n")


# ---------------------------------------------------------------------------
# info — Glücksfall: alles vorhanden
# ---------------------------------------------------------------------------

def test_info_shows_version_details(tmp_path):
    _make_install(tmp_path, "8.4.22")
    _write_state(tmp_path, "8.4", {
        "active": "8.4.22",
        "installed": {
            "8.4.22": {
                "installed_at": "2026-04-15T14:23:45+00:00",
                "build_duration_seconds": 133,
                "config_name": "dev",
                "variants": ["default", "fpm", "intl", "opcache"],
            },
        },
    })
    _write_state(tmp_path, "global", {})  # Placeholder, doesn't matter

    runner = CliRunner()
    with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / "config")}):
        result = runner.invoke(main, ["--prefix", str(tmp_path), "info", "8.4.22"])
    assert result.exit_code == 0, result.output
    assert "8.4.22" in result.output
    assert "dev" in result.output
    assert "fpm" in result.output
    assert "opcache" in result.output


def test_info_shows_active_marker(tmp_path):
    _make_install(tmp_path, "8.4.22")
    _write_state(tmp_path, "8.4", {
        "active": "8.4.22",
        "installed": {"8.4.22": {"config_name": "standard"}},
    })
    runner = CliRunner()
    with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / "config")}):
        result = runner.invoke(main, ["--prefix", str(tmp_path), "info", "8.4.22"])
    assert result.exit_code == 0, result.output
    assert "aktiv" in result.output.lower()


# ---------------------------------------------------------------------------
# info — nicht installiert
# ---------------------------------------------------------------------------

def test_info_exits_when_version_not_installed(tmp_path):
    (tmp_path / "versions").mkdir()  # leer
    runner = CliRunner()
    with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / "config")}):
        result = runner.invoke(main, ["--prefix", str(tmp_path), "info", "8.4.22"])
    assert result.exit_code != 0
    assert "nicht installiert" in result.output.lower()


# ---------------------------------------------------------------------------
# info — Legacy-Install ohne Metadaten
# ---------------------------------------------------------------------------

def test_info_handles_legacy_install_without_metadata(tmp_path):
    """Version existiert auf Disk, aber State ist leer (z.B. manuell installiert)."""
    _make_install(tmp_path, "8.3.10")
    runner = CliRunner()
    with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / "config")}):
        result = runner.invoke(main, ["--prefix", str(tmp_path), "info", "8.3.10"])
    assert result.exit_code == 0, result.output
    assert "8.3.10" in result.output
    # Keine Metadaten – darf aber nicht crashen
    assert "—" in result.output or "unbekannt" in result.output.lower() or "keine" in result.output.lower()


# ---------------------------------------------------------------------------
# info — Family als Argument (statt expliziter Version)
# ---------------------------------------------------------------------------

def test_info_accepts_family_and_resolves_to_active(tmp_path):
    """`pbrew info 8.4` sollte die aktive Version der Family anzeigen."""
    _make_install(tmp_path, "8.4.22")
    _write_state(tmp_path, "8.4", {
        "active": "8.4.22",
        "installed": {"8.4.22": {"config_name": "prod"}},
    })
    runner = CliRunner()
    with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / "config")}):
        result = runner.invoke(main, ["--prefix", str(tmp_path), "info", "8.4"])
    assert result.exit_code == 0, result.output
    assert "8.4.22" in result.output
    assert "prod" in result.output
