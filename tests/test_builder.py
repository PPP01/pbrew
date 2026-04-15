from pathlib import Path
from pbrew.core.builder import build_configure_args, get_jobs


PREFIX = Path("/opt/pbrew")


def test_configure_args_contains_prefix():
    args = build_configure_args(PREFIX, "8.4.22", "8.4", {})
    assert any("--prefix=" in a for a in args)
    assert any("versions/8.4.22" in a for a in args)


def test_configure_args_contains_cli():
    """cli wird immer als Basis hinzugefügt (kein Variant)."""
    args = build_configure_args(PREFIX, "8.4.22", "8.4", {})
    assert "--enable-cli" in args


def test_configure_args_fpm_only_when_in_variants():
    """fpm darf nur hinzukommen, wenn in variants gelistet."""
    args = build_configure_args(PREFIX, "8.4.22", "8.4", {"build": {"variants": ["default"]}})
    assert "--enable-fpm" not in args


def test_configure_args_sets_config_file_path():
    args = build_configure_args(PREFIX, "8.4.22", "8.4", {})
    assert any("--with-config-file-path=" in a and "etc/cli/8.4" in a for a in args)


def test_configure_args_sets_scan_dir():
    args = build_configure_args(PREFIX, "8.4.22", "8.4", {})
    assert any("--with-config-file-scan-dir=" in a and "conf.d/8.4" in a for a in args)


def test_configure_args_extra_option_overrides_scan_dir():
    config = {"build": {"extra": {"with-config-file-scan-dir": "/custom/scan"}}}
    args = build_configure_args(PREFIX, "8.4.22", "8.4", config)
    scan_args = [a for a in args if "--with-config-file-scan-dir" in a]
    assert len(scan_args) == 1
    assert scan_args[0] == "--with-config-file-scan-dir=/custom/scan"


def test_configure_args_bool_extra_option():
    config = {"build": {"extra": {"with-password-argon2": True}}}
    args = build_configure_args(PREFIX, "8.4.22", "8.4", config)
    assert "--with-password-argon2" in args


def test_configure_args_false_extra_option_omitted():
    config = {"build": {"extra": {"enable-gd": False}}}
    args = build_configure_args(PREFIX, "8.4.22", "8.4", config)
    assert "--enable-gd" not in args


def test_get_jobs_auto_returns_int():
    jobs = get_jobs({"build": {"jobs": "auto"}})
    assert isinstance(jobs, int)
    assert jobs >= 1


def test_get_jobs_fixed():
    assert get_jobs({"build": {"jobs": 4}}) == 4


def test_get_jobs_override():
    assert get_jobs({"build": {"jobs": "auto"}}, override=2) == 2


# ---------------------------------------------------------------------------
# Variant-Mapping (#29)
# ---------------------------------------------------------------------------

def test_no_fpm_systemd_by_default():
    """--with-fpm-systemd darf nicht automatisch gesetzt werden (libsystemd-Abhängigkeit)."""
    config = {"build": {"variants": ["default", "fpm"]}}
    args = build_configure_args(PREFIX, "8.4.22", "8.4", config)
    assert "--with-fpm-systemd" not in args


def test_fpm_systemd_as_explicit_variant():
    """fpm-systemd als eigener Variant aktiviert --with-fpm-systemd."""
    config = {"build": {"variants": ["fpm-systemd"]}}
    args = build_configure_args(PREFIX, "8.4.22", "8.4", config)
    assert "--enable-fpm" in args
    assert "--with-fpm-systemd" in args


def test_mysql_variant_maps_to_mysqli_and_pdo():
    """mysql → mysqli + pdo-mysql mit mysqlnd-Treiber (seit PHP 7.0)."""
    config = {"build": {"variants": ["mysql"]}}
    args = build_configure_args(PREFIX, "8.4.22", "8.4", config)
    assert "--enable-mysqli" in args
    assert "--with-mysqli=mysqlnd" in args
    assert "--with-pdo-mysql=mysqlnd" in args
    assert "--with-mysql" not in args  # vor PHP 7.0 entfernt


def test_sqlite_variant_maps_to_sqlite3_and_pdo():
    config = {"build": {"variants": ["sqlite"]}}
    args = build_configure_args(PREFIX, "8.4.22", "8.4", config)
    assert "--with-sqlite3" in args
    assert "--with-pdo-sqlite" in args
    assert "--with-sqlite" not in args


def test_iconv_uses_with_not_enable():
    config = {"build": {"variants": ["iconv"]}}
    args = build_configure_args(PREFIX, "8.4.22", "8.4", config)
    assert "--with-iconv" in args
    assert "--enable-iconv" not in args


def test_tidy_uses_with_not_enable():
    config = {"build": {"variants": ["tidy"]}}
    args = build_configure_args(PREFIX, "8.4.22", "8.4", config)
    assert "--with-tidy" in args
    assert "--enable-tidy" not in args


def test_gettext_uses_with_not_enable():
    config = {"build": {"variants": ["gettext"]}}
    args = build_configure_args(PREFIX, "8.4.22", "8.4", config)
    assert "--with-gettext" in args
    assert "--enable-gettext" not in args


def test_unknown_variant_falls_back_to_enable():
    """Variant ohne explizites Mapping bekommt standardmäßig --enable-X."""
    config = {"build": {"variants": ["customextension"]}}
    args = build_configure_args(PREFIX, "8.4.22", "8.4", config)
    assert "--enable-customextension" in args


def test_minimal_profile_produces_clean_args():
    """Minimal-Profil soll nur cli + default erzeugen – kein FPM."""
    config = {"build": {"variants": ["default", "openssl"]}}
    args = build_configure_args(PREFIX, "8.4.22", "8.4", config)
    assert "--enable-cli" in args
    assert "--with-openssl" in args
    assert "--enable-fpm" not in args
    assert "--with-fpm-systemd" not in args
