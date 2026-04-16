import os
import stat
from pathlib import Path
from unittest.mock import patch
from click.testing import CliRunner

from pbrew.core.wrapper_script import generate_wrapper_script, write_wrapper_script
from pbrew.core.shell import already_integrated


# ---------------------------------------------------------------------------
# generate_wrapper_script
# ---------------------------------------------------------------------------

def test_wrapper_sources_wrapper_env():
    content = generate_wrapper_script(Path("/home/alice/.pbrew"))
    assert "wrapper.env" in content
    assert "source" in content


def test_wrapper_checks_etc_fallback():
    content = generate_wrapper_script(Path("/home/alice/.pbrew"))
    assert "/etc/pbrew/wrapper.env" in content


def test_wrapper_no_pip_install():
    """Kein Auto-Install mehr – stattdessen Fehlermeldung."""
    content = generate_wrapper_script(Path("/home/alice/.pbrew"))
    assert "pip install" not in content


def test_wrapper_contains_use_switch_handling():
    """use/switch brauchen Sonderbehandlung um Parent-Env zu aendern."""
    content = generate_wrapper_script(Path("/home/alice/.pbrew"))
    assert "use|switch" in content


def test_wrapper_contains_exec_for_normal_commands():
    """Normale Commands per exec – kein unnötiger Subprozess."""
    content = generate_wrapper_script(Path("/home/alice/.pbrew"))
    assert "exec" in content


def test_wrapper_bakes_in_prefix():
    content = generate_wrapper_script(Path("/opt/custom-pbrew"))
    assert "/opt/custom-pbrew" in content


def test_wrapper_has_shebang():
    content = generate_wrapper_script(Path("/home/alice/.pbrew"))
    assert content.startswith("#!/bin/bash\n")


# ---------------------------------------------------------------------------
# write_wrapper_script
# ---------------------------------------------------------------------------

def test_write_creates_executable_file(tmp_path):
    write_wrapper_script(tmp_path)
    wrapper = tmp_path / "bin" / "pbrew"
    assert wrapper.exists()
    assert wrapper.stat().st_mode & stat.S_IXUSR


def test_write_does_not_overwrite_existing(tmp_path):
    (tmp_path / "bin").mkdir(parents=True)
    wrapper = tmp_path / "bin" / "pbrew"
    wrapper.write_text("#!/bin/bash\n# custom wrapper\n")
    write_wrapper_script(tmp_path, overwrite=False)
    assert "custom wrapper" in wrapper.read_text()


def test_write_overwrites_when_requested(tmp_path):
    (tmp_path / "bin").mkdir(parents=True)
    wrapper = tmp_path / "bin" / "pbrew"
    wrapper.write_text("#!/bin/bash\n# old\n")
    write_wrapper_script(tmp_path, overwrite=True)
    assert "old" not in wrapper.read_text()
    assert "wrapper.env" in wrapper.read_text()


# ---------------------------------------------------------------------------
# already_integrated – erkennt sowohl alte als auch neue Integration
# ---------------------------------------------------------------------------

def test_detects_old_shell_init_integration(tmp_path):
    rc = tmp_path / ".bashrc"
    rc.write_text('something pbrew shell-init bash\n')
    assert already_integrated(rc)


def test_detects_new_path_integration(tmp_path):
    rc = tmp_path / ".bashrc"
    rc.write_text('export PATH="$HOME/.pbrew/bin:$PATH"\n')
    assert already_integrated(rc)


def test_detects_custom_prefix_path(tmp_path):
    rc = tmp_path / ".bashrc"
    rc.write_text('export PATH="/opt/pbrew/bin:$PATH"\n')
    assert already_integrated(rc)


def test_no_detection_on_empty_file(tmp_path):
    rc = tmp_path / ".bashrc"
    rc.write_text("")
    assert not already_integrated(rc)


# ---------------------------------------------------------------------------
# pbrew init schreibt Wrapper + PATH-Export
# ---------------------------------------------------------------------------

def test_init_creates_wrapper_script(tmp_path):
    from pbrew.cli import main
    prefix = tmp_path / "pbrew"
    runner = CliRunner()
    with patch.dict(os.environ, {
        "SHELL": "/bin/bash",
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
    }), patch("pbrew.cli.init_._rc_file_for", return_value=tmp_path / ".bashrc"):
        result = runner.invoke(main, ["init"], input=f"{prefix}\ny\n")
    assert result.exit_code == 0, result.output
    wrapper = prefix / "bin" / "pbrew"
    assert wrapper.exists()
    assert wrapper.stat().st_mode & stat.S_IXUSR


def test_init_writes_path_export_not_shell_init(tmp_path):
    from pbrew.cli import main
    prefix = tmp_path / "pbrew"
    rc_file = tmp_path / ".bashrc"
    runner = CliRunner()
    with patch.dict(os.environ, {
        "SHELL": "/bin/bash",
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
    }), patch("pbrew.cli.init_._rc_file_for", return_value=rc_file):
        result = runner.invoke(main, ["init"], input=f"{prefix}\n")
    assert result.exit_code == 0, result.output
    content = rc_file.read_text()
    assert "source" in content
    assert "pbrew-settings.sh" in content
    # Kein shell-init in der .bashrc
    assert "shell-init" not in content
