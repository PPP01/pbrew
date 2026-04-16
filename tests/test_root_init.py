import os
from pathlib import Path
from unittest.mock import patch
from click.testing import CliRunner
from pbrew.cli import main


def _invoke_init(tmp_path, user_input, uid=0):
    runner = CliRunner()
    with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / "config"), "SHELL": ""}), \
         patch("pbrew.cli.init_.os.getuid", return_value=uid):
        return runner.invoke(main, ["init"], input=user_input)


# ---------------------------------------------------------------------------
# Root: systemweit → /opt/pbrew als Default
# ---------------------------------------------------------------------------

def test_root_asked_about_systemwide(tmp_path):
    """Root bekommt die Frage 'systemweit einrichten?'."""
    prefix = tmp_path / "opt-pbrew"
    result = _invoke_init(tmp_path, f"y\n{prefix}\n", uid=0)
    assert result.exit_code == 0, result.output
    assert "systemweit" in result.output.lower()


def test_root_systemwide_yes_shows_opt_default(tmp_path):
    """Bei 'y' wird /opt/pbrew als Default im Prompt angezeigt."""
    prefix = tmp_path / "opt-pbrew"
    result = _invoke_init(tmp_path, f"y\n{prefix}\n", uid=0)
    assert result.exit_code == 0, result.output
    assert "/opt/pbrew" in result.output


def test_root_systemwide_no_normal_flow(tmp_path):
    """Bei 'n' → normaler Flow ohne /opt/pbrew-Default."""
    prefix = tmp_path / "rootpbrew"
    result = _invoke_init(tmp_path, f"n\n{prefix}\n", uid=0)
    assert result.exit_code == 0, result.output
    assert "/opt/pbrew" not in result.output


# ---------------------------------------------------------------------------
# Normaler User: kein systemweit-Prompt
# ---------------------------------------------------------------------------

def test_normal_user_no_systemwide_prompt(tmp_path):
    """Normaler User bekommt keine systemweit-Frage."""
    prefix = tmp_path / "mypbrew"
    result = _invoke_init(tmp_path, f"{prefix}\n", uid=1000)
    assert result.exit_code == 0, result.output
    assert "systemweit" not in result.output.lower()
    assert (prefix / "bin" / "pbrew").exists()
