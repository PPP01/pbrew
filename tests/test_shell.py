from pathlib import Path
import pytest
from pbrew.core.shell import write_settings_file, replace_or_append_integration


# ---------------------------------------------------------------------------
# write_settings_file
# ---------------------------------------------------------------------------

def test_write_settings_file_creates_file(tmp_path):
    prefix = tmp_path / "pbrew"
    prefix.mkdir()
    bin_path = prefix / "bin" / "pbrew"
    result = write_settings_file(prefix, bin_path)
    assert result.exists()


def test_write_settings_file_contains_pbrew_root(tmp_path):
    prefix = tmp_path / "pbrew"
    prefix.mkdir()
    bin_path = prefix / "bin" / "pbrew"
    result = write_settings_file(prefix, bin_path)
    assert f'PBREW_ROOT="{prefix}"' in result.read_text()


def test_write_settings_file_contains_path(tmp_path):
    prefix = tmp_path / "pbrew"
    prefix.mkdir()
    bin_dir = prefix / "bin"
    bin_path = bin_dir / "pbrew"
    result = write_settings_file(prefix, bin_path)
    assert f'PATH="{bin_dir}:$PATH"' in result.read_text()


def test_write_settings_file_contains_pbrew_function(tmp_path):
    prefix = tmp_path / "pbrew"
    prefix.mkdir()
    bin_path = prefix / "bin" / "pbrew"
    result = write_settings_file(prefix, bin_path)
    text = result.read_text()
    assert "pbrew()" in text
    # Shell-Syntax: einzelne geschweifte Klammer (kein Python-f-string-Artefakt)
    assert "pbrew() {" in text
    assert "pbrew() {{" not in text


def test_write_settings_file_contains_switch_sourcing(tmp_path):
    prefix = tmp_path / "pbrew"
    prefix.mkdir()
    bin_path = prefix / "bin" / "pbrew"
    result = write_settings_file(prefix, bin_path)
    assert ".switch" in result.read_text()


def test_write_settings_file_returns_path(tmp_path):
    prefix = tmp_path / "pbrew"
    prefix.mkdir()
    bin_path = prefix / "bin" / "pbrew"
    result = write_settings_file(prefix, bin_path)
    assert isinstance(result, Path)


# ---------------------------------------------------------------------------
# replace_or_append_integration
# ---------------------------------------------------------------------------

def test_replace_or_append_appends_when_no_existing(tmp_path):
    rc_file = tmp_path / ".bashrc"
    rc_file.write_text("# existing content\n")
    result = replace_or_append_integration(rc_file, "source ~/.pbrew/pbrew-settings.sh")
    assert result is False
    assert "source ~/.pbrew/pbrew-settings.sh" in rc_file.read_text()


def test_replace_or_append_replaces_old_pbrew_bin_entry(tmp_path):
    rc_file = tmp_path / ".bashrc"
    rc_file.write_text(
        "# some content\n"
        "\n"
        "# pbrew — hinzugefügt von 'pbrew init'\n"
        'export PATH="/home/user/.pbrew/bin:$PATH"\n'
        "\n"
    )
    result = replace_or_append_integration(rc_file, "source ~/.pbrew/pbrew-settings.sh")
    assert result is True
    text = rc_file.read_text()
    assert "source ~/.pbrew/pbrew-settings.sh" in text


def test_replace_or_append_new_marker_detected_after_replace(tmp_path):
    rc_file = tmp_path / ".bashrc"
    rc_file.write_text(
        "# pbrew — hinzugefügt von 'pbrew init'\n"
        'export PATH="/home/user/.pbrew/bin:$PATH"\n'
    )
    replace_or_append_integration(rc_file, "source ~/.pbrew/pbrew-settings.sh")
    text = rc_file.read_text()
    assert "pbrew-settings.sh" in text


def test_replace_or_append_does_not_duplicate(tmp_path):
    rc_file = tmp_path / ".bashrc"
    rc_file.write_text("# existing\n")
    snippet = "source ~/.pbrew/pbrew-settings.sh"
    replace_or_append_integration(rc_file, snippet)
    replace_or_append_integration(rc_file, snippet)
    count = rc_file.read_text().count(snippet)
    assert count == 1, f"Snippet {count}× statt einmal eingetragen"
