import os
from pathlib import Path
from unittest.mock import patch
from click.testing import CliRunner
from pbrew.cli import main
from pbrew.core.wrappers import (
    find_xdebug,
    write_naked_wrappers,
    write_phpd_wrapper,
    write_versioned_wrappers,
)


def _make_version_bins(prefix: Path, version: str) -> None:
    """Legt Dummy-Binaries für eine PHP-Version an."""
    vdir = prefix / "versions" / version
    (vdir / "bin").mkdir(parents=True)
    (vdir / "sbin").mkdir(parents=True)
    for name in ("php", "phpize", "php-config"):
        (vdir / "bin" / name).write_text("#!/bin/bash\n")
        (vdir / "bin" / name).chmod(0o755)
    (vdir / "sbin" / "php-fpm").write_text("#!/bin/bash\n")
    (vdir / "sbin" / "php-fpm").chmod(0o755)


# ---------------------------------------------------------------------------
# write_versioned_wrappers
# ---------------------------------------------------------------------------

def test_versioned_wrappers_created(tmp_path):
    _make_version_bins(tmp_path, "8.4.22")
    write_versioned_wrappers(tmp_path, "8.4.22", "8.4")
    bdir = tmp_path / "bin"
    for name in ("php84", "phpize84", "php-config84", "php-fpm84"):
        wrapper = bdir / name
        assert wrapper.exists(), f"Fehlt: {name}"
        assert wrapper.stat().st_mode & 0o111, f"Nicht ausführbar: {name}"


def test_versioned_wrapper_executes_correct_binary(tmp_path):
    _make_version_bins(tmp_path, "8.3.10")
    write_versioned_wrappers(tmp_path, "8.3.10", "8.3")
    content = (tmp_path / "bin" / "php83").read_text()
    assert "versions/8.3.10/bin/php" in content


# ---------------------------------------------------------------------------
# write_naked_wrappers
# ---------------------------------------------------------------------------

def test_naked_php_wrapper_created(tmp_path):
    write_naked_wrappers(tmp_path)
    php = tmp_path / "bin" / "php"
    assert php.exists()
    assert php.stat().st_mode & 0o111


def test_naked_php_wrapper_checks_pbrew_path(tmp_path):
    write_naked_wrappers(tmp_path)
    content = (tmp_path / "bin" / "php").read_text()
    assert "$PBREW_PATH" in content
    assert "/usr/bin/env php" in content


def test_naked_phpize_and_php_config_wrappers_created(tmp_path):
    write_naked_wrappers(tmp_path)
    bdir = tmp_path / "bin"
    for name in ("phpize", "php-config"):
        wrapper = bdir / name
        assert wrapper.exists(), f"Fehlt: {name}"
        assert wrapper.stat().st_mode & 0o111, f"Nicht ausführbar: {name}"


def test_naked_php_fpm_wrapper_created(tmp_path):
    write_naked_wrappers(tmp_path)
    php_fpm = tmp_path / "bin" / "php-fpm"
    assert php_fpm.exists()
    assert php_fpm.stat().st_mode & 0o111


def test_naked_php_fpm_wrapper_checks_sbin_path(tmp_path):
    write_naked_wrappers(tmp_path)
    content = (tmp_path / "bin" / "php-fpm").read_text()
    assert "sbin/php-fpm" in content
    assert "PBREW_PATH" in content


def test_naked_wrappers_idempotent(tmp_path):
    write_naked_wrappers(tmp_path)
    write_naked_wrappers(tmp_path)
    content = (tmp_path / "bin" / "php").read_text()
    assert "$PBREW_PATH" in content


# ---------------------------------------------------------------------------
# find_xdebug
# ---------------------------------------------------------------------------

def test_find_xdebug_returns_none_when_not_present(tmp_path):
    version_dir = tmp_path / "versions" / "8.4.22"
    version_dir.mkdir(parents=True)
    result = find_xdebug(version_dir)
    assert result is None


def test_find_xdebug_finds_xdebug_so(tmp_path):
    version_dir = tmp_path / "versions" / "8.4.22"
    ext_dir = version_dir / "lib" / "php" / "extensions" / "no-debug-non-zts-20240924"
    ext_dir.mkdir(parents=True)
    xdebug_so = ext_dir / "xdebug.so"
    xdebug_so.write_text("")
    result = find_xdebug(version_dir)
    assert result == xdebug_so


# ---------------------------------------------------------------------------
# write_phpd_wrapper
# ---------------------------------------------------------------------------

def test_write_phpd_wrapper_skipped_when_no_xdebug(tmp_path):
    version = "8.4.22"
    version_dir = tmp_path / "versions" / version
    version_dir.mkdir(parents=True)
    (tmp_path / "bin").mkdir()
    result = write_phpd_wrapper(tmp_path, version)
    assert result is False
    assert not (tmp_path / "bin" / "phpd").exists()


def test_write_phpd_wrapper_creates_wrapper_when_xdebug_present(tmp_path):
    version = "8.4.22"
    version_dir = tmp_path / "versions" / version
    ext_dir = version_dir / "lib" / "php" / "extensions" / "no-debug-non-zts-20240924"
    ext_dir.mkdir(parents=True)
    (ext_dir / "xdebug.so").write_text("")
    (tmp_path / "bin").mkdir()
    result = write_phpd_wrapper(tmp_path, version)
    assert result is True
    phpd = tmp_path / "bin" / "phpd"
    assert phpd.exists()
    assert phpd.stat().st_mode & 0o111
    content = phpd.read_text()
    assert "-dzend_extension=" in content


# ---------------------------------------------------------------------------
# pbrew switch aktualisiert naked wrappers
# ---------------------------------------------------------------------------

def test_switch_updates_naked_wrappers(tmp_path):
    import json
    # State vorbereiten: 8.4.22 installiert und aktiv
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    (state_dir / "8.4.json").write_text(json.dumps({"active": "8.4.22"}))
    (tmp_path / "bin").mkdir()
    # Versioned wrapper muss existieren damit naked wrapper drauf zeigen kann
    (tmp_path / "bin" / "php84").write_text("#!/bin/bash\n")
    (tmp_path / "bin" / "php-fpm84").write_text("#!/bin/bash\n")

    runner = CliRunner()
    with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / "config")}):
        result = runner.invoke(main, ["--prefix", str(tmp_path), "switch", "8.4"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "bin" / "php").exists()
    content = (tmp_path / "bin" / "php").read_text()
    assert "$PBREW_PATH" in content
