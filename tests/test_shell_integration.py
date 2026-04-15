import os
from pathlib import Path
from unittest.mock import patch
from click.testing import CliRunner
from pbrew.cli import main
from pbrew.core.shell import detect_shell, already_integrated, append_shell_integration, SHELL_MAP


# ---------------------------------------------------------------------------
# detect_shell
# ---------------------------------------------------------------------------

def test_detect_shell_bash():
    with patch.dict(os.environ, {"SHELL": "/bin/bash"}):
        assert detect_shell() == "bash"


def test_detect_shell_zsh():
    with patch.dict(os.environ, {"SHELL": "/usr/bin/zsh"}):
        assert detect_shell() == "zsh"


def test_detect_shell_fish():
    with patch.dict(os.environ, {"SHELL": "/usr/bin/fish"}):
        assert detect_shell() == "fish"


def test_detect_shell_unknown_returns_none():
    with patch.dict(os.environ, {"SHELL": "/bin/tcsh"}):
        assert detect_shell() is None


def test_detect_shell_missing_env_returns_none():
    env = {k: v for k, v in os.environ.items() if k != "SHELL"}
    with patch.dict(os.environ, env, clear=True):
        assert detect_shell() is None


# ---------------------------------------------------------------------------
# already_integrated
# ---------------------------------------------------------------------------

def test_already_integrated_false_for_missing_file(tmp_path):
    assert not already_integrated(tmp_path / ".bashrc")


def test_already_integrated_false_for_empty_file(tmp_path):
    rc = tmp_path / ".bashrc"
    rc.write_text("")
    assert not already_integrated(rc)


def test_already_integrated_true_if_marker_present(tmp_path):
    rc = tmp_path / ".bashrc"
    rc.write_text('eval "$(pbrew shell-init bash)"\n')
    assert already_integrated(rc)


# ---------------------------------------------------------------------------
# append_shell_integration
# ---------------------------------------------------------------------------

def test_append_creates_file_if_missing(tmp_path):
    rc = tmp_path / ".bashrc"
    append_shell_integration(rc, 'eval "$(pbrew shell-init bash)"')
    assert rc.exists()
    assert "pbrew shell-init bash" in rc.read_text()


def test_append_preserves_existing_content(tmp_path):
    rc = tmp_path / ".bashrc"
    rc.write_text("# existing content\n")
    append_shell_integration(rc, 'eval "$(pbrew shell-init bash)"')
    text = rc.read_text()
    assert "# existing content" in text
    assert "pbrew shell-init bash" in text


def test_append_creates_parent_dirs(tmp_path):
    rc = tmp_path / ".config" / "fish" / "config.fish"
    append_shell_integration(rc, "pbrew shell-init fish | source")
    assert rc.exists()


# ---------------------------------------------------------------------------
# pbrew shell-init fish (neues Template)
# ---------------------------------------------------------------------------

def test_shell_init_fish_outputs_fish_syntax(tmp_path):
    runner = CliRunner()
    with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / "config")}):
        result = runner.invoke(main, ["--prefix", str(tmp_path / "pbrew"), "shell-init", "fish"])
    assert result.exit_code == 0, result.output
    assert "fish_add_path" in result.output
    assert "function pbrew" in result.output


# ---------------------------------------------------------------------------
# pbrew init — Shell-Setup-Schritt
# ---------------------------------------------------------------------------

def test_init_integrates_shell_when_confirmed(tmp_path):
    runner = CliRunner()
    prefix = tmp_path / "pbrew"
    rc_file = tmp_path / ".bashrc"
    with patch.dict(os.environ, {
        "SHELL": "/bin/bash",
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
    }), patch("pbrew.cli.init_._rc_file_for", return_value=rc_file):
        # Eingaben: Präfix-Prompt + Shell-Confirm (y)
        result = runner.invoke(main, ["init"], input=f"{prefix}\ny\n")
    assert result.exit_code == 0, result.output
    assert rc_file.exists()
    assert "pbrew shell-init bash" in rc_file.read_text()


def test_init_skips_shell_when_declined(tmp_path):
    runner = CliRunner()
    prefix = tmp_path / "pbrew"
    rc_file = tmp_path / ".bashrc"
    with patch.dict(os.environ, {
        "SHELL": "/bin/bash",
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
    }), patch("pbrew.cli.init_._rc_file_for", return_value=rc_file):
        result = runner.invoke(main, ["init"], input=f"{prefix}\nn\n")
    assert result.exit_code == 0, result.output
    assert not rc_file.exists()


def test_init_shell_idempotent(tmp_path):
    """Zweimaliges init trägt die Integration nicht doppelt ein."""
    runner = CliRunner()
    prefix = tmp_path / "pbrew"
    rc_file = tmp_path / ".bashrc"
    env = {
        "SHELL": "/bin/bash",
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
    }
    with patch.dict(os.environ, env), patch("pbrew.cli.init_._rc_file_for", return_value=rc_file):
        runner.invoke(main, ["init"], input=f"{prefix}\ny\n")
        runner.invoke(main, ["init"], input=f"{prefix}\ny\n")
    count = rc_file.read_text().count("pbrew shell-init bash")
    assert count == 1, f"Marker {count}× eingetragen statt einmal"
