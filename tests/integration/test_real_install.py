"""Integrationstests: bauen tatsächlich eine PHP-Version.

Laufzeit: ~3-5 Minuten pro Test. Wird NICHT im Standard-Test-Run ausgeführt.

Ausführen mit:
    pytest -m integration

Oder nur diesen Test:
    pytest tests/integration/test_real_install.py -m integration -v -s

Voraussetzungen:
    - Build-Tools: gcc, make, autoconf, bison, re2c, pkg-config
    - Libraries: libxml2-dev, libssl-dev, libsqlite3-dev

Fehlende Tools → Test wird geskippt, nicht gefailt.
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from pbrew.cli import main
from pbrew.core.prerequisites import check_prerequisites


REQUIRED_LIBS = {
    "libxml-2.0": "libxml2-dev",
    "openssl": "libssl-dev",
    "sqlite3": "libsqlite3-dev",
}


def _check_pkg_config(pkg: str) -> bool:
    try:
        result = subprocess.run(
            ["pkg-config", "--exists", pkg],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _skip_if_prerequisites_missing():
    """Skippt den Test, wenn Build-Tools oder Libs fehlen."""
    missing_bins = [r.name for r in check_prerequisites() if not r.found]
    if missing_bins:
        pytest.skip(f"Build-Tools fehlen: {', '.join(missing_bins)}")

    missing_libs = [pkg for pkg in REQUIRED_LIBS if not _check_pkg_config(pkg)]
    if missing_libs:
        dev_pkgs = [REQUIRED_LIBS[pkg] for pkg in missing_libs]
        pytest.skip(f"Dev-Libraries fehlen (apt): {', '.join(dev_pkgs)}")


@pytest.mark.integration
def test_install_minimal_build_succeeds(tmp_path):
    """Baut eine echte PHP-Version mit dem minimal-Profil.

    Validiert: Binary existiert, startet, gibt richtige Version aus.
    """
    _skip_if_prerequisites_missing()

    prefix = tmp_path / "pbrew"
    prefix.mkdir()

    # Manuell die Verzeichnisse anlegen die sonst `pbrew init` erstellen würde
    for sub in ("versions", "bin", "etc", "distfiles", "state", "configs"):
        (prefix / sub).mkdir()

    # Minimal-Profil schreiben (nur cli + openssl → kein FPM, keine externen Libs)
    import tomlkit
    minimal = {"build": {"variants": ["default", "openssl"]}, "xdebug": {"enabled": False}}
    (prefix / "configs" / "minimal.toml").write_text(tomlkit.dumps(minimal))

    runner = CliRunner()
    env = {**os.environ, "XDG_CONFIG_HOME": str(tmp_path / "config")}
    with runner.isolation():
        result = runner.invoke(
            main,
            ["--prefix", str(prefix), "install", "8.4", "--config=minimal"],
            catch_exceptions=False,
            env=env,
        )

    assert result.exit_code == 0, f"install fehlgeschlagen:\n{result.output}"

    # Verify: Binary existiert und funktioniert
    versions_dir = prefix / "versions"
    installed = [p for p in versions_dir.iterdir() if p.is_dir()]
    assert len(installed) == 1, f"Erwarte genau eine installierte Version, gefunden: {installed}"
    version_path = installed[0]

    php_bin = version_path / "bin" / "php"
    assert php_bin.exists(), f"php-Binary fehlt: {php_bin}"
    assert php_bin.stat().st_mode & 0o111, "php-Binary ist nicht ausführbar"

    # PHP aufrufen und Version vergleichen
    result = subprocess.run([str(php_bin), "-v"], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, f"php -v fehlgeschlagen:\n{result.stderr}"
    assert "PHP" in result.stdout
    assert version_path.name in result.stdout, f"Version {version_path.name} nicht im Output: {result.stdout}"


@pytest.mark.integration
def test_install_creates_naked_wrappers(tmp_path):
    """Nach der Erstinstallation existieren php und phpd in bin/."""
    _skip_if_prerequisites_missing()

    prefix = tmp_path / "pbrew"
    prefix.mkdir()
    for sub in ("versions", "bin", "etc", "distfiles", "state", "configs"):
        (prefix / sub).mkdir()

    import tomlkit
    minimal = {"build": {"variants": ["default", "openssl"]}}
    (prefix / "configs" / "minimal.toml").write_text(tomlkit.dumps(minimal))

    runner = CliRunner()
    env = {**os.environ, "XDG_CONFIG_HOME": str(tmp_path / "config")}
    result = runner.invoke(
        main,
        ["--prefix", str(prefix), "install", "8.4", "--config=minimal"],
        catch_exceptions=False,
        env=env,
    )
    assert result.exit_code == 0, result.output

    # Versionierter Wrapper + nackter php
    assert (prefix / "bin" / "php84").exists()
    assert (prefix / "bin" / "php").exists()
