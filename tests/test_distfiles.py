import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from pbrew.cli import main


def _setup_prefix(prefix: Path, version: str = "8.4.22", family: str = "8.4") -> None:
    """Legt ein minimales Prefix für Tests an."""
    (prefix / "distfiles").mkdir(parents=True)
    (prefix / "state").mkdir(parents=True)
    (prefix / "bin").mkdir(parents=True)


# ---------------------------------------------------------------------------
# distfiles_dir aus paths.py
# ---------------------------------------------------------------------------

def test_distfiles_dir_returns_correct_path(tmp_path):
    from pbrew.core.paths import distfiles_dir
    assert distfiles_dir(tmp_path) == tmp_path / "distfiles"


# ---------------------------------------------------------------------------
# install nutzt distfiles_dir aus paths
# ---------------------------------------------------------------------------

def test_install_uses_distfiles_dir(tmp_path):
    """install.py darf prefix / 'distfiles' nicht hardcoden."""
    import ast, inspect
    from pbrew.cli import install
    src = inspect.getsource(install)
    tree = ast.parse(src)
    # Suche nach direkten String-Konstruktionen wie prefix / "distfiles"
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value == "distfiles":
            raise AssertionError(
                "install.py enthält hardcodierten 'distfiles'-String — bitte distfiles_dir() verwenden"
            )


# ---------------------------------------------------------------------------
# pbrew cleanup
# ---------------------------------------------------------------------------

def test_cleanup_removes_old_tarballs(tmp_path):
    _setup_prefix(tmp_path)
    # Zwei Tarballs anlegen, 8.4.20 ist nicht mehr installiert
    (tmp_path / "distfiles" / "php-8.4.20.tar.bz2").write_bytes(b"old")
    (tmp_path / "distfiles" / "php-8.4.22.tar.bz2").write_bytes(b"current")
    # State: 8.4.22 aktiv installiert
    (tmp_path / "state" / "8.4.json").write_text(json.dumps({
        "active": "8.4.22",
        "installed": {"8.4.22": {}},
    }))

    runner = CliRunner()
    with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / "config")}):
        result = runner.invoke(main, ["--prefix", str(tmp_path), "cleanup"])
    assert result.exit_code == 0, result.output
    assert not (tmp_path / "distfiles" / "php-8.4.20.tar.bz2").exists()
    assert (tmp_path / "distfiles" / "php-8.4.22.tar.bz2").exists()


def test_cleanup_dry_run_does_not_delete(tmp_path):
    _setup_prefix(tmp_path)
    (tmp_path / "distfiles" / "php-8.4.20.tar.bz2").write_bytes(b"old")
    (tmp_path / "state" / "8.4.json").write_text(json.dumps({"installed": {}}))

    runner = CliRunner()
    with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / "config")}):
        result = runner.invoke(main, ["--prefix", str(tmp_path), "cleanup", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "distfiles" / "php-8.4.20.tar.bz2").exists()
    assert "php-8.4.20.tar.bz2" in result.output
