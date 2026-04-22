import json
import os
from unittest.mock import patch
from click.testing import CliRunner
from pbrew.cli import main


def _setup_version(prefix, family="8.4", version="8.4.22"):
    (prefix / "versions" / version / "bin").mkdir(parents=True)
    state_dir = prefix / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / f"{family}.json").write_text(json.dumps({"active": version}))
    (state_dir / "global.json").write_text(json.dumps({"default_family": family}))


def _write_ini(prefix, family, ext_name, disabled=False):
    confd = prefix / "etc" / "conf.d" / family
    confd.mkdir(parents=True, exist_ok=True)
    suffix = ".ini.disabled" if disabled else ".ini"
    path = confd / f"{ext_name}{suffix}"
    path.write_text(f"extension={ext_name}.so\n")
    return path


def _invoke(prefix, tmp_path, *args, env_extra=None):
    runner = CliRunner()
    env = {"XDG_CONFIG_HOME": str(tmp_path / "config")}
    if env_extra:
        env.update(env_extra)
    with patch.dict(os.environ, env):
        return runner.invoke(main, ["--prefix", str(prefix)] + list(args))


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------

def test_ext_list_shows_active_and_inactive(tmp_path):
    _setup_version(tmp_path)
    _write_ini(tmp_path, "8.4", "apcu")
    _write_ini(tmp_path, "8.4", "xdebug", disabled=True)
    result = _invoke(tmp_path, tmp_path, "ext", "list", "8.4")
    assert result.exit_code == 0, result.output
    assert "apcu" in result.output
    assert "xdebug" in result.output
    assert "aktiv" in result.output
    assert "inaktiv" in result.output


def test_ext_list_without_scan_dir(tmp_path):
    _setup_version(tmp_path)
    result = _invoke(tmp_path, tmp_path, "ext", "list", "8.4")
    assert result.exit_code == 0
    assert "Kein scan-dir" in result.output


# ---------------------------------------------------------------------------
# disable / enable
# ---------------------------------------------------------------------------

def test_ext_disable_renames_ini(tmp_path):
    _setup_version(tmp_path)
    _write_ini(tmp_path, "8.4", "apcu")
    result = _invoke(tmp_path, tmp_path, "ext", "disable", "apcu", "8.4")
    assert result.exit_code == 0, result.output
    assert not (tmp_path / "etc" / "conf.d" / "8.4" / "apcu.ini").exists()
    assert (tmp_path / "etc" / "conf.d" / "8.4" / "apcu.ini.disabled").exists()


def test_ext_enable_renames_back(tmp_path):
    _setup_version(tmp_path)
    _write_ini(tmp_path, "8.4", "apcu", disabled=True)
    result = _invoke(tmp_path, tmp_path, "ext", "enable", "apcu", "8.4")
    assert result.exit_code == 0, result.output
    assert (tmp_path / "etc" / "conf.d" / "8.4" / "apcu.ini").exists()
    assert not (tmp_path / "etc" / "conf.d" / "8.4" / "apcu.ini.disabled").exists()


def test_ext_enable_already_active(tmp_path):
    _setup_version(tmp_path)
    _write_ini(tmp_path, "8.4", "apcu")
    result = _invoke(tmp_path, tmp_path, "ext", "enable", "apcu", "8.4")
    assert result.exit_code == 0
    assert "bereits aktiv" in result.output


def test_ext_disable_already_disabled(tmp_path):
    _setup_version(tmp_path)
    result = _invoke(tmp_path, tmp_path, "ext", "disable", "ghost", "8.4")
    assert result.exit_code == 0
    assert "bereits deaktiviert" in result.output


# ---------------------------------------------------------------------------
# remove
# ---------------------------------------------------------------------------

def test_ext_remove_existing(tmp_path):
    _setup_version(tmp_path)
    _write_ini(tmp_path, "8.4", "apcu")
    result = _invoke(tmp_path, tmp_path, "ext", "remove", "apcu", "8.4")
    assert result.exit_code == 0
    assert (tmp_path / "etc" / "conf.d" / "8.4" / "apcu.ini.disabled").exists()


def test_ext_remove_missing_fails(tmp_path):
    _setup_version(tmp_path)
    result = _invoke(tmp_path, tmp_path, "ext", "remove", "ghost", "8.4")
    assert result.exit_code != 0
    assert "nicht gefunden" in result.output


# ---------------------------------------------------------------------------
# Family-Resolver
# ---------------------------------------------------------------------------

def test_family_resolved_from_pbrew_active(tmp_path):
    """Ohne explizites Argument wird PBREW_ACTIVE verwendet (neue Architektur)."""
    _setup_version(tmp_path)
    _write_ini(tmp_path, "8.4", "apcu")
    result = _invoke(tmp_path, tmp_path, "ext", "list", env_extra={"PBREW_ACTIVE": "8.4.22"})
    assert result.exit_code == 0
    assert "apcu" in result.output


def test_family_resolved_from_pbrew_php_fallback(tmp_path):
    """PBREW_PHP wird als Fallback akzeptiert, wenn PBREW_ACTIVE nicht gesetzt."""
    _setup_version(tmp_path)
    _write_ini(tmp_path, "8.4", "apcu")
    result = _invoke(tmp_path, tmp_path, "ext", "list", env_extra={"PBREW_PHP": "8.4"})
    assert result.exit_code == 0
    assert "apcu" in result.output


def test_family_resolved_from_global_state(tmp_path):
    """Ohne PBREW_PHP fällt er auf global state's default_family zurück."""
    _setup_version(tmp_path)
    _write_ini(tmp_path, "8.4", "apcu")
    # Kein PBREW_PHP; global state hat default_family=8.4
    result = _invoke(tmp_path, tmp_path, "ext", "list")
    assert result.exit_code == 0, result.output
    assert "apcu" in result.output


def test_family_error_without_any_hint(tmp_path):
    """Keine Argumente, kein Env, kein Global → Fehler mit Hinweis."""
    # Kein setup – also auch kein global.json mit default_family
    result = _invoke(tmp_path, tmp_path, "ext", "list")
    assert result.exit_code != 0
    assert "Keine aktive PHP-Version" in result.output
