from unittest.mock import patch
from pbrew.core.build_libs import (
    MissingLib,
    check_required_libs,
    install_command,
    VARIANT_PKGCONFIG,
)


# ---------------------------------------------------------------------------
# check_required_libs
# ---------------------------------------------------------------------------

def test_check_returns_empty_when_all_present():
    """Alle pkg-config-Calls liefern 0 → keine fehlende Lib."""
    with patch("pbrew.core.build_libs._pkg_config_exists", return_value=True), \
         patch("pbrew.core.build_libs.shutil.which", return_value="/usr/bin/pkg-config"):
        missing = check_required_libs(["openssl", "intl"])
    assert missing == []


def test_check_finds_missing_variant_lib():
    """Variant intl ohne icu-uc → muss als fehlend gemeldet werden."""
    def fake_exists(pkg):
        return pkg != "icu-uc"
    with patch("pbrew.core.build_libs._pkg_config_exists", side_effect=fake_exists), \
         patch("pbrew.core.build_libs.shutil.which", return_value="/usr/bin/pkg-config"):
        missing = check_required_libs(["intl"])
    assert any(m.pkgconfig == "icu-uc" for m in missing)
    assert any(m.variant == "intl" for m in missing)


def test_check_includes_always_required_libs():
    """libxml-2.0 und sqlite3 sind unabhängig von Variants Pflicht."""
    with patch("pbrew.core.build_libs._pkg_config_exists", return_value=False), \
         patch("pbrew.core.build_libs.shutil.which", return_value="/usr/bin/pkg-config"):
        missing = check_required_libs([])
    pkgs = {m.pkgconfig for m in missing}
    assert "libxml-2.0" in pkgs
    assert "sqlite3" in pkgs


def test_check_skips_unknown_variants():
    """Variants ohne pkg-config-Mapping (z.B. bcmath) verursachen keinen Fehler."""
    with patch("pbrew.core.build_libs._pkg_config_exists", return_value=True), \
         patch("pbrew.core.build_libs.shutil.which", return_value="/usr/bin/pkg-config"):
        missing = check_required_libs(["bcmath", "sockets", "exif"])
    assert missing == []


def test_check_returns_empty_when_pkg_config_not_installed():
    """Ohne pkg-config selbst können wir nichts prüfen – keine false-positives."""
    with patch("pbrew.core.build_libs.shutil.which", return_value=None):
        missing = check_required_libs(["openssl", "intl"])
    assert missing == []


def test_check_dedups_libs_referenced_by_multiple_variants():
    """libxml-2.0 ist core + (theoretisch auch von soap) → nur einmal gemeldet."""
    with patch("pbrew.core.build_libs._pkg_config_exists", return_value=False), \
         patch("pbrew.core.build_libs.shutil.which", return_value="/usr/bin/pkg-config"):
        missing = check_required_libs(["soap"])
    libxml_entries = [m for m in missing if m.pkgconfig == "libxml-2.0"]
    assert len(libxml_entries) == 1


# ---------------------------------------------------------------------------
# install_command
# ---------------------------------------------------------------------------

def test_install_command_apt():
    missing = [
        MissingLib(pkgconfig="icu-uc", variant="intl", distro_pkg="libicu-dev"),
        MissingLib(pkgconfig="openssl", variant="openssl", distro_pkg="libssl-dev"),
    ]
    with patch("pbrew.core.build_libs.detect_package_manager", return_value="apt-get"):
        cmd = install_command(missing)
    assert cmd is not None
    assert "apt install" in cmd
    assert "libicu-dev" in cmd
    assert "libssl-dev" in cmd


def test_install_command_returns_none_without_pm():
    missing = [MissingLib(pkgconfig="x", variant="y", distro_pkg="z")]
    with patch("pbrew.core.build_libs.detect_package_manager", return_value=None):
        assert install_command(missing) is None


def test_install_command_skips_libs_without_distro_package():
    """Eine Lib ohne bekanntes Distro-Paket darf den Befehl nicht zerstören."""
    missing = [
        MissingLib(pkgconfig="x", variant="y", distro_pkg=None),
        MissingLib(pkgconfig="openssl", variant="openssl", distro_pkg="libssl-dev"),
    ]
    with patch("pbrew.core.build_libs.detect_package_manager", return_value="apt-get"):
        cmd = install_command(missing)
    assert "libssl-dev" in cmd
    assert "None" not in cmd


# ---------------------------------------------------------------------------
# Mapping-Konsistenz
# ---------------------------------------------------------------------------

def test_all_mapped_variants_appear_in_builder_variant_flags():
    """Jedes Variant aus VARIANT_PKGCONFIG muss auch im Builder bekannt sein."""
    from pbrew.core.builder import _VARIANT_FLAGS
    for variant in VARIANT_PKGCONFIG:
        assert variant in _VARIANT_FLAGS, f"{variant} fehlt in builder._VARIANT_FLAGS"


# ---------------------------------------------------------------------------
# install_cmd-Integration
# ---------------------------------------------------------------------------

def test_install_aborts_on_missing_libs(tmp_path):
    """install bricht ab, wenn Pre-Flight-Libs fehlen, mit Installationshinweis."""
    import os
    from click.testing import CliRunner
    from pbrew.cli import main
    from pbrew.core.resolver import PhpRelease

    release = PhpRelease(version="8.4.22", family="8.4",
                         tarball_url="x", sha256="y")
    fake_missing = [MissingLib(pkgconfig="icu-uc", variant="intl", distro_pkg="libicu-dev")]

    runner = CliRunner()
    with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / "config")}), \
         patch("pbrew.cli.install.resolver.fetch_latest", return_value=release), \
         patch("pbrew.cli.install.build_libs.check_required_libs", return_value=fake_missing), \
         patch("pbrew.cli.install.build_libs.install_command", return_value="sudo apt install -y libicu-dev"):
        result = runner.invoke(main, ["--prefix", str(tmp_path / "pbrew"), "install", "8.4"])

    assert result.exit_code != 0
    assert "icu-uc" in result.output
    assert "libicu-dev" in result.output
    assert "--skip-lib-check" in result.output


def test_install_skips_lib_check_with_flag(tmp_path):
    """--skip-lib-check überspringt den Check komplett."""
    import os
    from click.testing import CliRunner
    from pbrew.cli import main
    from pbrew.core.resolver import PhpRelease

    release = PhpRelease(version="8.4.22", family="8.4",
                         tarball_url="x", sha256="y")
    fake_missing = [MissingLib(pkgconfig="icu-uc", variant="intl", distro_pkg="libicu-dev")]

    runner = CliRunner()
    with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / "config")}), \
         patch("pbrew.cli.install.resolver.fetch_latest", return_value=release), \
         patch("pbrew.cli.install.build_libs.check_required_libs", return_value=fake_missing) as mock_check, \
         patch("pbrew.cli.install.dl_mod.download", side_effect=RuntimeError("download blockt")):
        result = runner.invoke(main, ["--prefix", str(tmp_path / "pbrew"), "install", "8.4", "--skip-lib-check"])

    # Check darf nicht aufgerufen worden sein
    mock_check.assert_not_called()
    # Wir scheitern stattdessen am Download (das ist OK – beweist, dass der Check übersprungen wurde)
    assert "icu-uc" not in result.output
