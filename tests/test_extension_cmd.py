import json
import os
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import call, patch

from click.testing import CliRunner

from pbrew.cli import main


def _setup_version(prefix, family="8.4", version="8.4.22"):
    php_bin = prefix / "versions" / version / "bin" / "php"
    php_bin.parent.mkdir(parents=True)
    php_bin.touch()
    state_dir = prefix / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / f"{family}.json").write_text(json.dumps({"active": version}))
    (state_dir / "global.json").write_text(json.dumps({"default_family": family}))
    return php_bin


def _fake_ext_dir(tmp_path: Path, so_names: list[str]) -> Path:
    ext_dir = tmp_path / "ext_dir"
    ext_dir.mkdir()
    for name in so_names:
        (ext_dir / f"{name}.so").touch()
    return ext_dir


def _make_run(ext_output: str, ext_dir: Path):
    """Gibt eine Mock-Funktion zurück, die zwei subprocess.run-Aufrufe simuliert."""
    def _run(cmd, **kwargs):
        script = cmd[2] if len(cmd) > 2 else ""
        if "get_loaded_extensions" in script:
            return CompletedProcess(cmd, 0, stdout=ext_output, stderr="")
        return CompletedProcess(cmd, 0, stdout=str(ext_dir), stderr="")
    return _run


def _invoke(prefix, tmp_path, *args, env_extra=None):
    runner = CliRunner()
    env = {"XDG_CONFIG_HOME": str(tmp_path / "config")}
    if env_extra:
        env.update(env_extra)
    with patch.dict(os.environ, env):
        return runner.invoke(main, ["--prefix", str(prefix)] + list(args))


# ---------------------------------------------------------------------------
# Grundlegende Ausgabe
# ---------------------------------------------------------------------------

def test_extension_shows_loaded_extensions(tmp_path):
    php_bin = _setup_version(tmp_path)
    ext_dir = _fake_ext_dir(tmp_path, [])
    ext_output = "apcu|5.1.24\nbcmath|8.4.22\n"

    with patch("pbrew.cli.ext.subprocess.run", side_effect=_make_run(ext_output, ext_dir)):
        result = _invoke(tmp_path, tmp_path, "extension", "8.4")

    assert result.exit_code == 0, result.output
    assert "Loaded extensions:" in result.output
    assert "[*]" in result.output
    assert "apcu" in result.output
    assert "5.1.24" in result.output
    assert "bcmath" in result.output


def test_extension_shows_available_extensions(tmp_path):
    php_bin = _setup_version(tmp_path)
    # dba ist im extension_dir, aber nicht geladen
    ext_dir = _fake_ext_dir(tmp_path, ["dba", "ldap"])
    ext_output = "apcu|5.1.24\n"

    with patch("pbrew.cli.ext.subprocess.run", side_effect=_make_run(ext_output, ext_dir)):
        result = _invoke(tmp_path, tmp_path, "extension", "8.4")

    assert result.exit_code == 0, result.output
    assert "Available local extensions:" in result.output
    assert "[ ]" in result.output
    assert "dba" in result.output
    assert "ldap" in result.output


def test_extension_no_available_section_when_all_loaded(tmp_path):
    _setup_version(tmp_path)
    ext_dir = _fake_ext_dir(tmp_path, ["apcu"])
    ext_output = "apcu|5.1.24\n"

    with patch("pbrew.cli.ext.subprocess.run", side_effect=_make_run(ext_output, ext_dir)):
        result = _invoke(tmp_path, tmp_path, "extension", "8.4")

    assert result.exit_code == 0, result.output
    assert "Available local extensions:" not in result.output


def test_extension_uses_global_default_family(tmp_path):
    _setup_version(tmp_path)
    ext_dir = _fake_ext_dir(tmp_path, [])
    ext_output = "json|8.4.22\n"

    with patch("pbrew.cli.ext.subprocess.run", side_effect=_make_run(ext_output, ext_dir)):
        result = _invoke(tmp_path, tmp_path, "extension")

    assert result.exit_code == 0, result.output
    assert "json" in result.output


def test_extension_error_when_no_active_version(tmp_path):
    result = _invoke(tmp_path, tmp_path, "extension")
    assert result.exit_code != 0
    assert "Keine aktive PHP-Version" in result.output


def test_extension_error_when_php_binary_missing(tmp_path):
    # Version im State, aber kein Binary auf Disk
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    (state_dir / "8.4.json").write_text(json.dumps({"active": "8.4.22"}))
    (state_dir / "global.json").write_text(json.dumps({"default_family": "8.4"}))

    result = _invoke(tmp_path, tmp_path, "extension", "8.4")
    assert result.exit_code != 0
    assert "nicht gefunden" in result.output
