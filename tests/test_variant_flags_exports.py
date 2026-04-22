from pbrew.core.builder import VARIANT_FLAGS, VARIANT_EXTENSIONS


def test_variant_flags_exposes_mapping():
    assert "opcache" in VARIANT_FLAGS
    assert VARIANT_FLAGS["mysql"] == [
        "--enable-mysqli", "--with-mysqli=mysqlnd", "--with-pdo-mysql=mysqlnd",
    ]


def test_variant_extensions_excludes_sapi_entries():
    assert "cli" not in VARIANT_EXTENSIONS
    assert "fpm" not in VARIANT_EXTENSIONS
    assert "fpm-systemd" not in VARIANT_EXTENSIONS
    assert "opcache" in VARIANT_EXTENSIONS
    assert "mysql" in VARIANT_EXTENSIONS
