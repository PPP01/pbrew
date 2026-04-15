from pathlib import Path
from pbrew.fpm.services import (
    generate_fpm_service,
    service_name,
    service_path,
)

PREFIX = Path("/opt/pbrew")


def test_service_name_normal():
    assert service_name("8.4") == "php84-fpm"


def test_service_name_debug():
    assert service_name("8.4", debug=True) == "php84d-fpm"


def test_service_path():
    assert service_path("8.4") == Path("/etc/systemd/system/php84-fpm.service")


def test_generate_fpm_service_contains_binary():
    content = generate_fpm_service(PREFIX, "8.4.22", "8.4")
    assert "/opt/pbrew/versions/8.4.22/sbin/php-fpm" in content


def test_generate_fpm_service_contains_php_ini():
    content = generate_fpm_service(PREFIX, "8.4.22", "8.4")
    assert "--php-ini /opt/pbrew/etc/fpm/8.4/php.ini" in content


def test_generate_fpm_service_contains_fpm_conf():
    content = generate_fpm_service(PREFIX, "8.4.22", "8.4")
    assert "--fpm-config /opt/pbrew/etc/fpm/8.4/php-fpm.conf" in content


def test_generate_fpm_service_no_env_for_normal():
    content = generate_fpm_service(PREFIX, "8.4.22", "8.4")
    assert "PHP_INI_SCAN_DIR" not in content


def test_generate_fpm_service_debug_has_scan_dir_env():
    content = generate_fpm_service(PREFIX, "8.4.22", "8.4", debug=True)
    assert "PHP_INI_SCAN_DIR" in content
    assert "conf.d/8.4:" in content
    assert "conf.d/8.4d" in content


def test_generate_fpm_service_debug_uses_8_4d_conf():
    content = generate_fpm_service(PREFIX, "8.4.22", "8.4", debug=True)
    assert "fpm/8.4d/php-fpm.conf" in content


def test_generate_fpm_service_is_type_notify():
    content = generate_fpm_service(PREFIX, "8.4.22", "8.4")
    assert "Type=notify" in content
