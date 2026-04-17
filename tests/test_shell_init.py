from click.testing import CliRunner
from pbrew.cli import main


def test_bash_init_includes_unswitch():
    """bash-Init enthält 'unswitch' in der eval-Bedingung."""
    runner = CliRunner()
    result = runner.invoke(main, ["--prefix", "/tmp/test", "shell-init", "bash"])
    assert result.exit_code == 0, result.output
    assert "unswitch" in result.output


def test_bash_init_sources_switch_file():
    """bash-Init sourcet .switch wenn vorhanden."""
    runner = CliRunner()
    result = runner.invoke(main, ["--prefix", "/tmp/test", "shell-init", "bash"])
    assert result.exit_code == 0, result.output
    assert ".switch" in result.output


def test_zsh_init_includes_unswitch():
    """zsh-Init enthält 'unswitch' in der eval-Bedingung."""
    runner = CliRunner()
    result = runner.invoke(main, ["--prefix", "/tmp/test", "shell-init", "zsh"])
    assert result.exit_code == 0, result.output
    assert "unswitch" in result.output


def test_zsh_init_sources_switch_file():
    """zsh-Init sourcet .switch wenn vorhanden."""
    runner = CliRunner()
    result = runner.invoke(main, ["--prefix", "/tmp/test", "shell-init", "zsh"])
    assert result.exit_code == 0, result.output
    assert ".switch" in result.output


def test_fish_init_includes_unswitch():
    """fish-Init enthält 'unswitch' in der eval-Bedingung."""
    runner = CliRunner()
    result = runner.invoke(main, ["--prefix", "/tmp/test", "shell-init", "fish"])
    assert result.exit_code == 0, result.output
    assert "unswitch" in result.output


def test_fish_init_sources_switch_fish_file():
    """fish-Init sourcet .switch.fish (fish-kompatibel) statt .switch."""
    runner = CliRunner()
    result = runner.invoke(main, ["--prefix", "/tmp/test", "shell-init", "fish"])
    assert result.exit_code == 0, result.output
    assert ".switch.fish" in result.output
