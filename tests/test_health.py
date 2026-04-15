from pathlib import Path
from unittest.mock import patch, MagicMock
from pbrew.utils.health import (
    check_php_version,
    check_extensions_loaded,
    check_fpm_config,
    check_scan_dir,
    CheckResult,
)


def _mock_run(returncode: int, stdout: str = "", stderr: str = ""):
    result = MagicMock()
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = stderr
    return result


PHP_BIN = Path("/opt/pbrew/versions/8.4.22/bin/php")
FPM_BIN = Path("/opt/pbrew/versions/8.4.22/sbin/php-fpm")


def test_check_php_version_ok():
    with patch("pbrew.utils.health.subprocess.run",
               return_value=_mock_run(0, "PHP 8.4.22 (cli)\n")):
        result = check_php_version(PHP_BIN)
    assert result.ok is True
    assert "PHP 8.4.22" in result.message


def test_check_php_version_fail():
    with patch("pbrew.utils.health.subprocess.run",
               return_value=_mock_run(1, stderr="command not found")):
        result = check_php_version(PHP_BIN)
    assert result.ok is False


def test_check_extensions_loaded_all_present():
    output = "[PHP Modules]\napcu\nopcache\nintl\n"
    with patch("pbrew.utils.health.subprocess.run",
               return_value=_mock_run(0, output)):
        results = check_extensions_loaded(PHP_BIN, ["apcu", "opcache", "intl"])
    assert all(r.ok for r in results)


def test_check_extensions_loaded_missing():
    output = "[PHP Modules]\napcu\n"
    with patch("pbrew.utils.health.subprocess.run",
               return_value=_mock_run(0, output)):
        results = check_extensions_loaded(PHP_BIN, ["apcu", "redis"])
    ok_map = {r.name: r.ok for r in results}
    assert ok_map["ext:apcu"] is True
    assert ok_map["ext:redis"] is False


def test_check_fpm_config_ok():
    with patch("pbrew.utils.health.subprocess.run",
               return_value=_mock_run(0)):
        result = check_fpm_config(
            FPM_BIN,
            Path("/opt/pbrew/etc/fpm/8.4/php.ini"),
            Path("/opt/pbrew/etc/fpm/8.4/php-fpm.conf"),
        )
    assert result.ok is True


def test_check_fpm_config_fail():
    with patch("pbrew.utils.health.subprocess.run",
               return_value=_mock_run(1, stderr="syntax error")):
        result = check_fpm_config(
            FPM_BIN,
            Path("/opt/pbrew/etc/fpm/8.4/php.ini"),
            Path("/opt/pbrew/etc/fpm/8.4/php-fpm.conf"),
        )
    assert result.ok is False
    assert "syntax error" in result.message


def test_check_scan_dir_matches_expected():
    expected = Path("/opt/pbrew/etc/conf.d/8.4")
    ini_output = (
        "Configuration File (php.ini) Path: /opt/pbrew/etc/cli/8.4\n"
        "Loaded Configuration File: /opt/pbrew/etc/cli/8.4/php.ini\n"
        "Scan for additional .ini files in: /opt/pbrew/etc/conf.d/8.4\n"
        "Additional .ini files parsed: (none)\n"
    )
    with patch("pbrew.utils.health.subprocess.run",
               return_value=_mock_run(0, ini_output)):
        result = check_scan_dir(PHP_BIN, expected)
    assert result.ok is True


def test_check_scan_dir_detects_mismatch():
    expected = Path("/opt/pbrew/etc/conf.d/8.4")
    ini_output = (
        'Scan for additional .ini files in: "/opt/pbrew/etc/conf.d/8.4"\n'
    )
    with patch("pbrew.utils.health.subprocess.run",
               return_value=_mock_run(0, ini_output)):
        result = check_scan_dir(PHP_BIN, expected)
    assert result.ok is False
    assert "Anführungszeichen" in result.message or "quote" in result.message.lower()


def test_check_scan_dir_none_reported():
    expected = Path("/opt/pbrew/etc/conf.d/8.4")
    ini_output = "Scan for additional .ini files in: (none)\n"
    with patch("pbrew.utils.health.subprocess.run",
               return_value=_mock_run(0, ini_output)):
        result = check_scan_dir(PHP_BIN, expected)
    assert result.ok is False
    assert "(none)" in result.message
