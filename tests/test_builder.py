from pathlib import Path
from pbrew.core.builder import build_configure_args, get_jobs


PREFIX = Path("/opt/pbrew")


def test_configure_args_contains_prefix():
    args = build_configure_args(PREFIX, "8.4.22", "8.4", {})
    assert any("--prefix=" in a for a in args)
    assert any("versions/8.4.22" in a for a in args)


def test_configure_args_contains_cli_and_fpm():
    args = build_configure_args(PREFIX, "8.4.22", "8.4", {})
    assert "--enable-cli" in args
    assert "--enable-fpm" in args


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
