from unittest.mock import patch
from pbrew.core.build_libs import (
    MissingLib,
    check_required_libs,
    install_command,
    LibCheck,
    LIB_CHECKS,
    VARIANT_LIB,
)


# ---------------------------------------------------------------------------
# check_required_libs – pkg-config-Pfad
# ---------------------------------------------------------------------------

def test_check_returns_empty_when_all_present():
    with patch("pbrew.core.build_libs._pkg_config_exists", return_value=True), \
         patch("pbrew.core.build_libs._headers_exist", return_value=True), \
         patch("pbrew.core.build_libs.shutil.which", return_value="/usr/bin/pkg-config"):
        missing = check_required_libs(["openssl", "intl"])
    assert missing == []


def test_check_finds_missing_variant_lib():
    def fake_pkg(pkg):
        return pkg != "icu-uc"
    with patch("pbrew.core.build_libs._pkg_config_exists", side_effect=fake_pkg), \
         patch("pbrew.core.build_libs._headers_exist", return_value=False), \
         patch("pbrew.core.build_libs.shutil.which", return_value="/usr/bin/pkg-config"):
        missing = check_required_libs(["intl"])
    assert any(m.name == "icu-uc" for m in missing)
    assert any(m.variant == "intl" for m in missing)


def test_check_includes_always_required_libs():
    with patch("pbrew.core.build_libs._pkg_config_exists", return_value=False), \
         patch("pbrew.core.build_libs._headers_exist", return_value=False), \
         patch("pbrew.core.build_libs.shutil.which", return_value="/usr/bin/pkg-config"):
        missing = check_required_libs([])
    names = {m.name for m in missing}
    assert "libxml-2.0" in names
    assert "sqlite3" in names


def test_check_skips_unknown_variants():
    with patch("pbrew.core.build_libs._pkg_config_exists", return_value=True), \
         patch("pbrew.core.build_libs._headers_exist", return_value=True), \
         patch("pbrew.core.build_libs.shutil.which", return_value="/usr/bin/pkg-config"):
        missing = check_required_libs(["bcmath", "sockets", "exif"])
    assert missing == []


def test_check_returns_empty_when_pkg_config_not_installed():
    """Ohne pkg-config selbst: keine Prüfung (kein false-positive)."""
    with patch("pbrew.core.build_libs.shutil.which", return_value=None):
        missing = check_required_libs(["openssl", "intl"])
    assert missing == []


def test_check_dedups_libs_referenced_by_multiple_variants():
    with patch("pbrew.core.build_libs._pkg_config_exists", return_value=False), \
         patch("pbrew.core.build_libs._headers_exist", return_value=False), \
         patch("pbrew.core.build_libs.shutil.which", return_value="/usr/bin/pkg-config"):
        missing = check_required_libs(["soap"])
    libxml_entries = [m for m in missing if m.name == "libxml-2.0"]
    assert len(libxml_entries) == 1


# ---------------------------------------------------------------------------
# Header-Fallback für Libs ohne pkg-config (#39)
# ---------------------------------------------------------------------------

def test_bz2_detected_via_header(tmp_path):
    """bz2 hat kein pkg-config – muss per Header gefunden werden."""
    header = tmp_path / "bzlib.h"
    header.write_text("")
    # Patch LIB_CHECKS für bz2: benutze das tmp_path-Header
    patched_checks = dict(LIB_CHECKS)
    patched_checks["bz2"] = LibCheck(headers=(str(header),))
    with patch("pbrew.core.build_libs._pkg_config_exists", return_value=True), \
         patch("pbrew.core.build_libs.LIB_CHECKS", patched_checks), \
         patch("pbrew.core.build_libs.shutil.which", return_value="/usr/bin/pkg-config"):
        missing = check_required_libs(["bz2"])
    assert not any(m.name == "bz2" for m in missing)


def test_bz2_missing_when_no_header(tmp_path):
    """Header existiert nicht → bz2 fehlt."""
    patched_checks = dict(LIB_CHECKS)
    patched_checks["bz2"] = LibCheck(headers=(str(tmp_path / "nonexistent.h"),))
    with patch("pbrew.core.build_libs._pkg_config_exists", return_value=True), \
         patch("pbrew.core.build_libs.LIB_CHECKS", patched_checks), \
         patch("pbrew.core.build_libs.shutil.which", return_value="/usr/bin/pkg-config"):
        missing = check_required_libs(["bz2"])
    assert any(m.name == "bz2" for m in missing)


def test_tidy_found_via_pkgconfig_only():
    """tidy hat pkg-config + Header-Fallback. pkg-config reicht allein."""
    with patch("pbrew.core.build_libs._pkg_config_exists", return_value=True), \
         patch("pbrew.core.build_libs._headers_exist", return_value=False), \
         patch("pbrew.core.build_libs.shutil.which", return_value="/usr/bin/pkg-config"):
        missing = check_required_libs(["tidy"])
    assert not any(m.name == "tidy" for m in missing)


def test_tidy_found_via_header_fallback():
    """tidy ohne pkg-config aber mit Header → nicht als fehlend melden."""
    def fake_pkg(pkg):
        return pkg != "tidy"  # tidy.pc fehlt auf dieser Distro
    with patch("pbrew.core.build_libs._pkg_config_exists", side_effect=fake_pkg), \
         patch("pbrew.core.build_libs._headers_exist", return_value=True), \
         patch("pbrew.core.build_libs.shutil.which", return_value="/usr/bin/pkg-config"):
        missing = check_required_libs(["tidy"])
    assert not any(m.name == "tidy" for m in missing)


def test_tidy_missing_when_no_pkgconfig_and_no_header():
    with patch("pbrew.core.build_libs._pkg_config_exists", return_value=False), \
         patch("pbrew.core.build_libs._headers_exist", return_value=False), \
         patch("pbrew.core.build_libs.shutil.which", return_value="/usr/bin/pkg-config"):
        missing = check_required_libs(["tidy"])
    assert any(m.name == "tidy" for m in missing)


def test_readline_uses_headers_only():
    """readline hat kein pkg-config, nur Header."""
    assert LIB_CHECKS["readline"].pkgconfig is None
    assert LIB_CHECKS["readline"].headers


def test_bz2_uses_headers_only():
    assert LIB_CHECKS["bz2"].pkgconfig is None
    assert LIB_CHECKS["bz2"].headers


# ---------------------------------------------------------------------------
# install_command
# ---------------------------------------------------------------------------

def test_install_command_apt():
    missing = [
        MissingLib(name="icu-uc", variant="intl", distro_pkg="libicu-dev"),
        MissingLib(name="openssl", variant="openssl", distro_pkg="libssl-dev"),
    ]
    with patch("pbrew.core.build_libs.detect_package_manager", return_value="apt-get"):
        cmd = install_command(missing)
    assert cmd is not None
    assert "apt install" in cmd
    assert "libicu-dev" in cmd
    assert "libssl-dev" in cmd


def test_install_command_returns_none_without_pm():
    missing = [MissingLib(name="x", variant="y", distro_pkg="z")]
    with patch("pbrew.core.build_libs.detect_package_manager", return_value=None):
        assert install_command(missing) is None


def test_install_command_skips_libs_without_distro_package():
    missing = [
        MissingLib(name="x", variant="y", distro_pkg=None),
        MissingLib(name="openssl", variant="openssl", distro_pkg="libssl-dev"),
    ]
    with patch("pbrew.core.build_libs.detect_package_manager", return_value="apt-get"):
        cmd = install_command(missing)
    assert "libssl-dev" in cmd
    assert "None" not in cmd


# ---------------------------------------------------------------------------
# Mapping-Konsistenz
# ---------------------------------------------------------------------------

def test_all_mapped_variants_appear_in_builder_variant_flags():
    """Jedes Variant aus VARIANT_LIB muss auch im Builder bekannt sein."""
    from pbrew.core.builder import _VARIANT_FLAGS
    for variant in VARIANT_LIB:
        assert variant in _VARIANT_FLAGS, f"{variant} fehlt in builder._VARIANT_FLAGS"


def test_every_variant_lib_has_a_check():
    """Jede in VARIANT_LIB referenzierte Lib-ID hat einen Eintrag in LIB_CHECKS."""
    for variant, lib_id in VARIANT_LIB.items():
        assert lib_id in LIB_CHECKS, f"Lib-ID {lib_id!r} (via {variant}) fehlt in LIB_CHECKS"


# ---------------------------------------------------------------------------
# install_cmd-Integration
# ---------------------------------------------------------------------------

def test_install_aborts_on_missing_libs(tmp_path):
    import os
    from click.testing import CliRunner
    from pbrew.cli import main
    from pbrew.core.resolver import PhpRelease

    release = PhpRelease(version="8.4.22", family="8.4", tarball_url="x", sha256="y")
    fake_missing = [MissingLib(name="icu-uc", variant="intl", distro_pkg="libicu-dev")]

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
    import os
    from click.testing import CliRunner
    from pbrew.cli import main
    from pbrew.core.resolver import PhpRelease

    release = PhpRelease(version="8.4.22", family="8.4", tarball_url="x", sha256="y")
    fake_missing = [MissingLib(name="icu-uc", variant="intl", distro_pkg="libicu-dev")]

    runner = CliRunner()
    with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / "config")}), \
         patch("pbrew.cli.install.resolver.fetch_latest", return_value=release), \
         patch("pbrew.cli.install.build_libs.check_required_libs", return_value=fake_missing) as mock_check, \
         patch("pbrew.cli.install.dl_mod.download", side_effect=RuntimeError("download blockt")):
        result = runner.invoke(main, ["--prefix", str(tmp_path / "pbrew"), "install", "8.4", "--skip-lib-check"])

    mock_check.assert_not_called()
    assert "icu-uc" not in result.output
