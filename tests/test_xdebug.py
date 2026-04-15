from pathlib import Path
from pbrew.fpm.xdebug import (
    create_debug_wrapper,
    create_xdebug_ini,
    debug_scan_dir,
)

PREFIX = Path("/opt/pbrew")


def test_create_debug_wrapper_creates_file(tmp_path):
    wrapper = create_debug_wrapper(tmp_path, "8.4.22", "8.4")
    assert wrapper.exists()
    assert wrapper.name == "php84d"


def test_create_debug_wrapper_is_executable(tmp_path):
    wrapper = create_debug_wrapper(tmp_path, "8.4.22", "8.4")
    assert wrapper.stat().st_mode & 0o111


def test_create_debug_wrapper_sets_scan_dir(tmp_path):
    wrapper = create_debug_wrapper(tmp_path, "8.4.22", "8.4")
    content = wrapper.read_text()
    assert "PHP_INI_SCAN_DIR" in content
    assert "conf.d/8.4:" in content
    assert "conf.d/8.4d" in content


def test_create_debug_wrapper_execs_php_bin(tmp_path):
    wrapper = create_debug_wrapper(tmp_path, "8.4.22", "8.4")
    content = wrapper.read_text()
    assert "versions/8.4.22/bin/php" in content
    assert '"$@"' in content


def test_create_xdebug_ini_creates_file(tmp_path):
    ini = create_xdebug_ini(tmp_path, "8.4")
    assert ini.exists()
    assert ini.parent.name == "8.4d"


def test_create_xdebug_ini_does_not_overwrite(tmp_path):
    ini = create_xdebug_ini(tmp_path, "8.4")
    ini.write_text("custom")
    create_xdebug_ini(tmp_path, "8.4")
    assert ini.read_text() == "custom"


def test_debug_scan_dir_format():
    result = debug_scan_dir(PREFIX, "8.4")
    assert result == "/opt/pbrew/etc/conf.d/8.4:/opt/pbrew/etc/conf.d/8.4d"
