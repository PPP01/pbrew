from click.testing import CliRunner
from pbrew.cli import main


def test_version_flag():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "version" in result.output.lower()
    # Die Version selbst muss SemVer-Format haben
    version_str = result.output.strip().split()[-1]
    parts = version_str.split(".")
    assert len(parts) >= 2, f"Kein SemVer-Format: {result.output}"
    assert all(p.isdigit() for p in parts), f"Nicht-numerische Teile: {version_str}"


def test_version_module_attribute():
    from pbrew import __version__
    assert __version__ != "0.0.0-dev"
    assert "." in __version__
