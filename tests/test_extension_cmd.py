import json
import os
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

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
    ext_dir.mkdir(exist_ok=True)
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
# ext list – kombinierte Ansicht
# ---------------------------------------------------------------------------

def test_ext_list_shows_loaded_extensions(tmp_path):
    _setup_version(tmp_path)
    ext_dir = _fake_ext_dir(tmp_path, [])
    ext_output = "apcu|5.1.24\nbcmath|8.4.22\n"

    with patch("pbrew.cli.ext.subprocess.run", side_effect=_make_run(ext_output, ext_dir)):
        result = _invoke(tmp_path, tmp_path, "ext", "list", "8.4")

    assert result.exit_code == 0, result.output
    assert "Loaded extensions:" in result.output
    assert "[*]" in result.output
    assert "apcu" in result.output
    assert "5.1.24" in result.output
    assert "bcmath" in result.output


def test_ext_list_shows_available_local_extensions(tmp_path):
    _setup_version(tmp_path)
    # dba ist im extension_dir, aber nicht geladen
    ext_dir = _fake_ext_dir(tmp_path, ["dba", "ldap"])
    ext_output = "apcu|5.1.24\n"

    with patch("pbrew.cli.ext.subprocess.run", side_effect=_make_run(ext_output, ext_dir)):
        result = _invoke(tmp_path, tmp_path, "ext", "list", "8.4")

    assert result.exit_code == 0, result.output
    assert "Available local extensions:" in result.output
    assert "dba" in result.output
    assert "ldap" in result.output


def test_ext_list_marks_pbrew_loaded_extension(tmp_path):
    _setup_version(tmp_path)
    ext_dir = _fake_ext_dir(tmp_path, [])
    ext_output = "apcu|5.1.24\n"
    # apcu hat eine aktive pbrew-INI
    confd = tmp_path / "etc" / "conf.d" / "8.4"
    confd.mkdir(parents=True)
    (confd / "apcu.ini").write_text("extension=apcu.so\n")

    with patch("pbrew.cli.ext.subprocess.run", side_effect=_make_run(ext_output, ext_dir)):
        result = _invoke(tmp_path, tmp_path, "ext", "list", "8.4")

    assert result.exit_code == 0, result.output
    assert "[pbrew]" in result.output


def test_ext_list_marks_pbrew_disabled_extension(tmp_path):
    _setup_version(tmp_path)
    ext_dir = _fake_ext_dir(tmp_path, ["apcu"])
    ext_output = "json|8.4.22\n"
    # apcu ist deaktiviert
    confd = tmp_path / "etc" / "conf.d" / "8.4"
    confd.mkdir(parents=True)
    (confd / "apcu.ini.disabled").write_text("extension=apcu.so\n")

    with patch("pbrew.cli.ext.subprocess.run", side_effect=_make_run(ext_output, ext_dir)):
        result = _invoke(tmp_path, tmp_path, "ext", "list", "8.4")

    assert result.exit_code == 0, result.output
    assert "[-]" in result.output
    assert "pbrew, inaktiv" in result.output


def test_ext_list_no_local_section_when_all_loaded(tmp_path):
    _setup_version(tmp_path)
    ext_dir = _fake_ext_dir(tmp_path, ["apcu"])
    ext_output = "apcu|5.1.24\n"

    with patch("pbrew.cli.ext.subprocess.run", side_effect=_make_run(ext_output, ext_dir)):
        result = _invoke(tmp_path, tmp_path, "ext", "list", "8.4")

    assert result.exit_code == 0, result.output
    assert "Available local extensions:" not in result.output


def test_ext_list_shows_standard_extensions(tmp_path):
    _setup_version(tmp_path)
    ext_dir = _fake_ext_dir(tmp_path, [])
    ext_output = "json|8.4.22\n"

    with patch("pbrew.cli.ext.subprocess.run", side_effect=_make_run(ext_output, ext_dir)):
        result = _invoke(tmp_path, tmp_path, "ext", "list", "8.4")

    assert result.exit_code == 0, result.output
    assert "Standard extensions (not compiled):" in result.output
    assert "gmp" in result.output
    assert "mbstring" in result.output
    # json ist geladen, darf nicht nochmal in Standard erscheinen
    assert result.output.count("json") == 1


def test_ext_list_uses_global_default_family(tmp_path):
    _setup_version(tmp_path)
    ext_dir = _fake_ext_dir(tmp_path, [])
    ext_output = "json|8.4.22\n"

    with patch("pbrew.cli.ext.subprocess.run", side_effect=_make_run(ext_output, ext_dir)):
        result = _invoke(tmp_path, tmp_path, "ext", "list")

    assert result.exit_code == 0, result.output
    assert "json" in result.output


def test_ext_list_error_when_no_active_version(tmp_path):
    result = _invoke(tmp_path, tmp_path, "ext", "list")
    assert result.exit_code != 0
    assert "Keine aktive PHP-Version" in result.output


def test_ext_list_error_when_php_binary_missing(tmp_path):
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    (state_dir / "8.4.json").write_text(json.dumps({"active": "8.4.22"}))
    (state_dir / "global.json").write_text(json.dumps({"default_family": "8.4"}))

    result = _invoke(tmp_path, tmp_path, "ext", "list", "8.4")
    assert result.exit_code != 0
    assert "nicht gefunden" in result.output


# ---------------------------------------------------------------------------
# ext installed – nur pbrew-verwaltete Extensions
# ---------------------------------------------------------------------------

def test_ext_installed_shows_active_and_inactive(tmp_path):
    _setup_version(tmp_path)
    confd = tmp_path / "etc" / "conf.d" / "8.4"
    confd.mkdir(parents=True)
    (confd / "apcu.ini").write_text("extension=apcu.so\n")
    (confd / "xdebug.ini.disabled").write_text("zend_extension=xdebug.so\n")

    result = _invoke(tmp_path, tmp_path, "ext", "installed", "8.4")

    assert result.exit_code == 0, result.output
    assert "apcu" in result.output
    assert "xdebug" in result.output
    assert "aktiv" in result.output
    assert "inaktiv" in result.output


def test_ext_installed_without_scan_dir(tmp_path):
    _setup_version(tmp_path)
    result = _invoke(tmp_path, tmp_path, "ext", "installed", "8.4")
    assert result.exit_code == 0
    assert "Kein scan-dir" in result.output
