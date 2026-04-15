import os
from unittest.mock import patch
from click.testing import CliRunner
from pbrew.cli import main


def _setup_version(prefix, version="8.4.22"):
    (prefix / "versions" / version / "bin").mkdir(parents=True)
    (prefix / "versions" / version / "bin" / "php").write_text("#!/bin/bash\n")


def _invoke(prefix, tmp_path, *args):
    runner = CliRunner()
    env = {"XDG_CONFIG_HOME": str(tmp_path / "config")}
    with patch.dict(os.environ, env):
        return runner.invoke(main, ["--prefix", str(prefix)] + list(args))


# ---------------------------------------------------------------------------
# pool add / list / remove
# ---------------------------------------------------------------------------

def test_pool_add_creates_config(tmp_path):
    _setup_version(tmp_path)
    result = _invoke(tmp_path, tmp_path, "fpm", "pool", "add", "alice", "8.4")
    assert result.exit_code == 0, result.output
    conf = tmp_path / "etc" / "fpm" / "8.4" / "php-fpm.d" / "alice.conf"
    assert conf.exists()
    assert "[alice]" in conf.read_text()


def test_pool_add_debug_creates_debug_config(tmp_path):
    _setup_version(tmp_path)
    result = _invoke(tmp_path, tmp_path, "fpm", "pool", "add", "alice", "8.4", "--debug")
    assert result.exit_code == 0, result.output
    conf = tmp_path / "etc" / "fpm" / "8.4d" / "php-fpm.d" / "alice.conf"
    assert conf.exists()
    assert "[alice-debug]" in conf.read_text()


def test_pool_list_shows_both_normal_and_debug(tmp_path):
    _setup_version(tmp_path)
    _invoke(tmp_path, tmp_path, "fpm", "pool", "add", "alice", "8.4")
    _invoke(tmp_path, tmp_path, "fpm", "pool", "add", "bob", "8.4", "--debug")
    result = _invoke(tmp_path, tmp_path, "fpm", "pool", "list", "8.4")
    assert result.exit_code == 0, result.output
    assert "alice" in result.output
    assert "bob" in result.output
    assert "normal" in result.output
    assert "debug" in result.output


def test_pool_list_empty(tmp_path):
    _setup_version(tmp_path)
    result = _invoke(tmp_path, tmp_path, "fpm", "pool", "list", "8.4")
    assert result.exit_code == 0
    assert "Keine Pools" in result.output


def test_pool_remove_deletes_config(tmp_path):
    _setup_version(tmp_path)
    _invoke(tmp_path, tmp_path, "fpm", "pool", "add", "alice", "8.4")
    result = _invoke(tmp_path, tmp_path, "fpm", "pool", "remove", "alice", "8.4")
    assert result.exit_code == 0
    conf = tmp_path / "etc" / "fpm" / "8.4" / "php-fpm.d" / "alice.conf"
    assert not conf.exists()


def test_pool_remove_missing_errors(tmp_path):
    _setup_version(tmp_path)
    result = _invoke(tmp_path, tmp_path, "fpm", "pool", "remove", "ghost", "8.4")
    assert result.exit_code != 0
    assert "nicht gefunden" in result.output


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

def test_status_without_versions(tmp_path):
    result = _invoke(tmp_path, tmp_path, "fpm", "status")
    assert result.exit_code == 0
    assert "Keine PHP-Versionen" in result.output


def test_status_with_versions_but_no_service(tmp_path):
    _setup_version(tmp_path)
    result = _invoke(tmp_path, tmp_path, "fpm", "status")
    assert result.exit_code == 0
    # Keine Services vorhanden (systemd-Unit fehlt) → leerer Status-Block


# ---------------------------------------------------------------------------
# setup_fpm
# ---------------------------------------------------------------------------

def test_setup_fpm_creates_pool_dir_and_conf(tmp_path):
    from pbrew.cli.fpm import setup_fpm
    _setup_version(tmp_path)
    # write_service scheitert ohne root – das wird in setup_fpm abgefangen
    with patch("pbrew.cli.fpm.write_service", side_effect=PermissionError):
        setup_fpm(tmp_path, "8.4.22", "8.4")
    conf = tmp_path / "etc" / "fpm" / "8.4" / "php-fpm.conf"
    assert conf.exists()
    assert "[global]" in conf.read_text()
    assert (tmp_path / "etc" / "fpm" / "8.4" / "php-fpm.d").is_dir()


def test_setup_fpm_with_xdebug_creates_debug_wrapper(tmp_path):
    from pbrew.cli.fpm import setup_fpm
    _setup_version(tmp_path)
    with patch("pbrew.cli.fpm.write_service", side_effect=PermissionError):
        setup_fpm(tmp_path, "8.4.22", "8.4", xdebug=True)
    assert (tmp_path / "bin" / "php84d").exists()
    assert (tmp_path / "etc" / "conf.d" / "8.4d" / "xdebug.ini").exists()
    assert (tmp_path / "etc" / "fpm" / "8.4d" / "php-fpm.conf").exists()
