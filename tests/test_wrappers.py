import os
from pathlib import Path
from unittest.mock import patch
from click.testing import CliRunner
from pbrew.cli import main
from pbrew.core.wrappers import write_naked_wrappers, write_versioned_wrappers


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
    (tmp_path / "bin").mkdir()
    write_naked_wrappers(tmp_path, "8.4.22", "8.4")
    php = tmp_path / "bin" / "php"
    assert php.exists()
    assert php.stat().st_mode & 0o111


def test_naked_phpd_wrapper_created(tmp_path):
    (tmp_path / "bin").mkdir()
    write_naked_wrappers(tmp_path, "8.4.22", "8.4")
    phpd = tmp_path / "bin" / "phpd"
    assert phpd.exists()
    assert phpd.stat().st_mode & 0o111


def test_naked_php_delegates_to_versioned_wrapper(tmp_path):
    (tmp_path / "bin").mkdir()
    write_naked_wrappers(tmp_path, "8.4.22", "8.4")
    content = (tmp_path / "bin" / "php").read_text()
    assert "php84" in content


def test_naked_phpd_delegates_to_fpm_wrapper(tmp_path):
    (tmp_path / "bin").mkdir()
    write_naked_wrappers(tmp_path, "8.4.22", "8.4")
    content = (tmp_path / "bin" / "phpd").read_text()
    assert "php-fpm84" in content


def test_naked_wrappers_overwritten_on_switch(tmp_path):
    """Nach switch auf 8.3 verweisen php/phpd auf php83/php-fpm83."""
    (tmp_path / "bin").mkdir()
    write_naked_wrappers(tmp_path, "8.4.22", "8.4")
    write_naked_wrappers(tmp_path, "8.3.10", "8.3")  # switch
    content = (tmp_path / "bin" / "php").read_text()
    assert "php83" in content
    assert "php84" not in content


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
    assert (tmp_path / "bin" / "phpd").exists()
    content = (tmp_path / "bin" / "php").read_text()
    assert "php84" in content
