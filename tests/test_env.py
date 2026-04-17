import json
import os
from unittest.mock import patch
from click.testing import CliRunner
from pbrew.cli import main


def _setup_global_state(prefix, default_family=None):
    state_dir = prefix / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state = {}
    if default_family:
        state["default_family"] = default_family
    (state_dir / "global.json").write_text(json.dumps(state))


def _setup_naked_wrapper(prefix, target_name):
    bdir = prefix / "bin"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "php").write_text(f'#!/bin/bash\nexec {bdir / target_name} "$@"\n')


def _invoke(prefix, tmp_path, env=None):
    base_env = {"XDG_CONFIG_HOME": str(tmp_path / "config")}
    if env:
        base_env.update(env)
    runner = CliRunner()
    with patch.dict(os.environ, base_env, clear=False):
        return runner.invoke(main, ["--prefix", str(prefix), "env"])


# ---------------------------------------------------------------------------
# env zeigt Basis-Informationen
# ---------------------------------------------------------------------------

def test_env_shows_pbrew_root(tmp_path):
    result = _invoke(tmp_path, tmp_path)
    assert result.exit_code == 0, result.output
    assert "PBREW_ROOT" in result.output
    assert str(tmp_path) in result.output


def test_env_shows_default_family(tmp_path):
    _setup_global_state(tmp_path, default_family="8.4")
    result = _invoke(tmp_path, tmp_path)
    assert result.exit_code == 0, result.output
    assert "8.4" in result.output


def test_env_shows_pbrew_path_when_set(tmp_path):
    _setup_global_state(tmp_path)
    result = _invoke(tmp_path, tmp_path, env={"PBREW_PATH": "/home/user/.pbrew/versions/8.3.10/bin"})
    assert result.exit_code == 0, result.output
    assert "PBREW_PATH" in result.output
    assert "/home/user/.pbrew/versions/8.3.10/bin" in result.output


def test_env_shows_pbrew_active_when_set(tmp_path):
    _setup_global_state(tmp_path)
    result = _invoke(tmp_path, tmp_path, env={"PBREW_ACTIVE": "8.3.10"})
    assert result.exit_code == 0, result.output
    assert "PBREW_ACTIVE" in result.output
    assert "8.3.10" in result.output


def test_env_shows_dash_when_env_vars_not_set(tmp_path):
    _setup_global_state(tmp_path)
    result = _invoke(tmp_path, tmp_path)
    assert result.exit_code == 0, result.output
    assert "PBREW_PATH" in result.output
    assert "PBREW_ACTIVE" in result.output


def test_env_shows_naked_wrapper_target(tmp_path):
    """Wenn bin/php existiert, zeigt env das Ziel des Wrappers."""
    _setup_naked_wrapper(tmp_path, "php84")
    _setup_global_state(tmp_path)
    result = _invoke(tmp_path, tmp_path)
    assert result.exit_code == 0, result.output
    assert "php84" in result.output


def test_env_handles_missing_naked_wrapper(tmp_path):
    """Kein bin/php vorhanden → kein Crash, Hinweis wird angezeigt."""
    _setup_global_state(tmp_path)
    result = _invoke(tmp_path, tmp_path)
    assert result.exit_code == 0, result.output
    # Muss laufen, darf keinen KeyError werfen


def test_env_shows_path_status(tmp_path):
    """env zeigt ob ~/.pbrew/bin/ im PATH ist."""
    _setup_global_state(tmp_path)
    bdir = str(tmp_path / "bin")
    result = _invoke(tmp_path, tmp_path, env={"PATH": f"{bdir}:/usr/bin"})
    assert result.exit_code == 0, result.output
    assert "PATH" in result.output


def test_env_aware_wrapper_shows_env_aware_label(tmp_path):
    """Wrapper mit $PBREW_PATH zeigt 'ENV-aware ($PBREW_PATH)' statt kaputter Pfad."""
    bdir = tmp_path / "bin"
    bdir.mkdir(parents=True, exist_ok=True)
    # ENV-aware Wrapper wie von write_naked_wrappers erzeugt
    (bdir / "php").write_text('#!/bin/bash\nexec "$PBREW_PATH/php" "$@"\n')
    _setup_global_state(tmp_path)
    result = _invoke(tmp_path, tmp_path)
    assert result.exit_code == 0, result.output
    assert "ENV-aware ($PBREW_PATH)" in result.output
    # Darf nicht den rohen String mit Anführungszeichen zeigen
    assert '"$PBREW_PATH' not in result.output
