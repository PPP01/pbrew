import os
import stat
import sys
from pathlib import Path
from unittest.mock import patch

from pbrew.core.wrapper_script import (
    detect_pbrew_bin,
    generate_wrapper_script,
    write_wrapper_env,
)


# ---------------------------------------------------------------------------
# detect_pbrew_bin
# ---------------------------------------------------------------------------

def test_detect_in_venv():
    """Wenn aus einem venv aufgerufen: {sys.prefix}/bin/pbrew."""
    fake_prefix = "/home/alice/project/.venv"
    with patch.object(sys, "prefix", fake_prefix), \
         patch.object(sys, "base_prefix", "/usr"):
        result = detect_pbrew_bin()
    assert result == Path(fake_prefix) / "bin" / "pbrew"


def test_detect_global_install():
    """Wenn kein venv: sucht pbrew im PATH."""
    with patch.object(sys, "prefix", "/usr"), \
         patch.object(sys, "base_prefix", "/usr"), \
         patch("pbrew.core.wrapper_script.shutil.which", return_value="/usr/local/bin/pbrew"):
        result = detect_pbrew_bin()
    assert result == Path("/usr/local/bin/pbrew")


def test_detect_fallback_to_sys_executable():
    """Kein venv, nicht im PATH: Fallback auf sys.executable."""
    with patch.object(sys, "prefix", "/usr"), \
         patch.object(sys, "base_prefix", "/usr"), \
         patch("pbrew.core.wrapper_script.shutil.which", return_value=None), \
         patch.object(sys, "executable", "/usr/bin/python3"):
        result = detect_pbrew_bin()
    assert result == Path("/usr/bin/python3")


# ---------------------------------------------------------------------------
# write_wrapper_env
# ---------------------------------------------------------------------------

def test_write_wrapper_env_creates_file(tmp_path):
    write_wrapper_env(tmp_path, Path("/some/venv/bin/pbrew"))
    env_file = tmp_path / "wrapper.env"
    assert env_file.exists()
    content = env_file.read_text()
    assert "PBREW_PYTHON_BIN" in content
    assert "/some/venv/bin/pbrew" in content


def test_write_wrapper_env_is_sourceable(tmp_path):
    """Die Datei muss bash-kompatibel sein (key=value, keine Leerzeichen um =)."""
    write_wrapper_env(tmp_path, Path("/test/bin/pbrew"))
    content = (tmp_path / "wrapper.env").read_text()
    # Bash-sourceable: Zeilen müssen KEY="VALUE" sein
    for line in content.splitlines():
        if line.strip() and not line.startswith("#"):
            assert "=" in line


def test_write_wrapper_env_overwrites(tmp_path):
    """Wiederholter Aufruf aktualisiert den Pfad."""
    write_wrapper_env(tmp_path, Path("/old/bin/pbrew"))
    write_wrapper_env(tmp_path, Path("/new/bin/pbrew"))
    content = (tmp_path / "wrapper.env").read_text()
    assert "/new/bin/pbrew" in content
    assert "/old/bin/pbrew" not in content


# ---------------------------------------------------------------------------
# Wrapper-Skript liest wrapper.env
# ---------------------------------------------------------------------------

def test_wrapper_script_sources_wrapper_env():
    content = generate_wrapper_script(Path("/home/alice/.pbrew"))
    assert "wrapper.env" in content
    assert "source" in content


def test_wrapper_script_checks_etc_fallback():
    content = generate_wrapper_script(Path("/home/alice/.pbrew"))
    assert "/etc/pbrew/wrapper.env" in content


def test_wrapper_script_no_pip_install():
    """Kein Auto-Install mehr – stattdessen Fehlermeldung mit Hinweis."""
    content = generate_wrapper_script(Path("/home/alice/.pbrew"))
    assert "pip install" not in content


def test_wrapper_script_shows_helpful_error():
    content = generate_wrapper_script(Path("/home/alice/.pbrew"))
    assert "pbrew init" in content  # Hinweis auf init


# ---------------------------------------------------------------------------
# pbrew init schreibt wrapper.env
# ---------------------------------------------------------------------------

def test_init_writes_wrapper_env(tmp_path):
    from click.testing import CliRunner
    from pbrew.cli import main
    prefix = tmp_path / "pbrew"
    runner = CliRunner()
    with patch.dict(os.environ, {
        "SHELL": "",
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
    }):
        result = runner.invoke(main, ["init"], input=f"{prefix}\n")
    assert result.exit_code == 0, result.output
    env_file = prefix / "wrapper.env"
    assert env_file.exists()
    content = env_file.read_text()
    assert "PBREW_PYTHON_BIN" in content
