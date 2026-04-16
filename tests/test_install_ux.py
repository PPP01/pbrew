"""Tests für den Install-Output (nicht den echten Build – der läuft per Integrationstest)."""
import json
import os
import tarfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from pbrew.cli import main
from pbrew.core.resolver import PhpRelease


def _make_release(version="8.4.22"):
    family = ".".join(version.split(".")[:2])
    return PhpRelease(
        version=version,
        family=family,
        tarball_url=f"https://www.php.net/distributions/php-{version}.tar.bz2",
        sha256="abc",
    )


def _prepare_prefix(prefix: Path, version="8.4.22"):
    """Legt alles außer versions/<v>/ an – das erzeugt erst der gemockte 'make install'."""
    for sub in ("distfiles", "state", "bin", "etc", "configs"):
        (prefix / sub).mkdir(parents=True, exist_ok=True)
    (prefix / "distfiles" / f"php-{version}.tar.bz2").write_bytes(b"")
    build_dir = prefix / "build" / version
    build_dir.mkdir(parents=True)
    return build_dir


def _simulate_make_install(prefix: Path, version: str):
    """Erzeugt die Binary-Struktur, die make install normalerweise anlegen würde."""
    vdir = prefix / "versions" / version
    (vdir / "bin").mkdir(parents=True)
    (vdir / "bin" / "php").write_text("#!/bin/bash\n")
    (vdir / "bin" / "php").chmod(0o755)
    (vdir / "sbin").mkdir()
    (vdir / "sbin" / "php-fpm").write_text("#!/bin/bash\n")


def _invoke_install(prefix, tmp_path, version="8.4.22"):
    runner = CliRunner()
    env = {"XDG_CONFIG_HOME": str(tmp_path / "config")}
    with patch.dict(os.environ, env), \
         patch("pbrew.cli.install.resolver.fetch_latest", return_value=_make_release(version)), \
         patch("pbrew.cli.install.build_libs.check_required_libs", return_value=[]), \
         patch("pbrew.cli.install.builder.run_configure", return_value=None) as mc, \
         patch("pbrew.cli.install.builder.run_make", return_value=None) as mm, \
         patch("pbrew.cli.install.builder.run_make_install",
               side_effect=lambda *a, **kw: _simulate_make_install(prefix, version)) as mi, \
         patch("pbrew.cli.install.run_basic_checks", return_value=[]):
        result = runner.invoke(main, ["--prefix", str(prefix), "install", "8.4"])
        return result, (mc, mm, mi)


# ---------------------------------------------------------------------------
# Log-Pfad und Tail-Hinweis werden VOR dem Build angezeigt
# ---------------------------------------------------------------------------

def test_output_shows_log_path_and_tail_hint(tmp_path):
    prefix = tmp_path / "pbrew"
    _prepare_prefix(prefix)
    result, _ = _invoke_install(prefix, tmp_path)
    assert result.exit_code == 0, result.output
    assert "Build-Log:" in result.output
    assert "tail -f" in result.output


# ---------------------------------------------------------------------------
# Jede Phase erscheint einzeln im Output
# ---------------------------------------------------------------------------

def test_output_shows_each_phase(tmp_path):
    prefix = tmp_path / "pbrew"
    _prepare_prefix(prefix)
    result, _ = _invoke_install(prefix, tmp_path)
    assert result.exit_code == 0, result.output
    out = result.output
    assert "configure" in out.lower()
    assert "make" in out.lower()
    assert "install" in out.lower()
    # Phasen müssen in dieser Reihenfolge erscheinen
    assert out.lower().index("configure") < out.lower().index("make ")
    # Erfolgs-Icon nach jeder Phase
    assert out.count("✓") >= 3  # 3 Phasen


# ---------------------------------------------------------------------------
# Bei Phasen-Fehler wird die betroffene Phase genannt
# ---------------------------------------------------------------------------

def test_install_pinned_version_uses_fetch_specific(tmp_path):
    """Bei 3-stelliger Versionsangabe wird fetch_specific statt fetch_latest genutzt."""
    version = "8.4.19"
    prefix = tmp_path / "pbrew"
    _prepare_prefix(prefix, version)
    runner = CliRunner()
    env = {"XDG_CONFIG_HOME": str(tmp_path / "config")}
    with patch.dict(os.environ, env), \
         patch("pbrew.cli.install.resolver.fetch_specific", return_value=_make_release(version)) as mfs, \
         patch("pbrew.cli.install.resolver.fetch_latest") as mfl, \
         patch("pbrew.cli.install.build_libs.check_required_libs", return_value=[]), \
         patch("pbrew.cli.install.builder.run_configure", return_value=None), \
         patch("pbrew.cli.install.builder.run_make", return_value=None), \
         patch("pbrew.cli.install.builder.run_make_install",
               side_effect=lambda *a, **kw: _simulate_make_install(prefix, version)), \
         patch("pbrew.cli.install.run_basic_checks", return_value=[]):
        result = runner.invoke(main, ["--prefix", str(prefix), "install", version])
    assert result.exit_code == 0, result.output
    mfs.assert_called_once_with(version)
    mfl.assert_not_called()
    assert "8.4.19" in result.output


def test_install_family_uses_fetch_latest(tmp_path):
    """Bei 2-stelliger Versionsangabe wird fetch_latest genutzt."""
    prefix = tmp_path / "pbrew"
    _prepare_prefix(prefix)
    result, (mc, mm, mi) = _invoke_install(prefix, tmp_path)
    assert result.exit_code == 0, result.output
    assert "Neueste Version" in result.output


def test_error_in_configure_reports_which_phase(tmp_path):
    prefix = tmp_path / "pbrew"
    _prepare_prefix(prefix)
    runner = CliRunner()
    env = {"XDG_CONFIG_HOME": str(tmp_path / "config")}
    with patch.dict(os.environ, env), \
         patch("pbrew.cli.install.resolver.fetch_latest", return_value=_make_release()), \
         patch("pbrew.cli.install.build_libs.check_required_libs", return_value=[]), \
         patch("pbrew.cli.install.builder.run_configure",
               side_effect=RuntimeError("bison not found")):
        result = runner.invoke(main, ["--prefix", str(prefix), "install", "8.4"])
    assert result.exit_code != 0
    assert "configure" in result.output.lower()
    assert "bison" in result.output.lower()
