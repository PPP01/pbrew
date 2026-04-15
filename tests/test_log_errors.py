from pathlib import Path
from pbrew.cli.install import _extract_errors_from_log


def test_extracts_configure_error_line(tmp_path):
    log = tmp_path / "build.log"
    log.write_text(
        "checking for icu... no\n"
        "configure: error: Package requirements (icu-uc >= 50.1) were not met:\n"
        "No package 'icu-uc' found\n"
    )
    lines = _extract_errors_from_log(log)
    assert any("icu-uc" in l for l in lines)
    assert any("Package requirements" in l for l in lines)


def test_includes_context_after_error(tmp_path):
    """Folgezeilen direkt nach einer error-Zeile werden als Kontext mitgenommen."""
    log = tmp_path / "build.log"
    log.write_text(
        "configure: error: something went wrong\n"
        "  additional context line 1\n"
        "  additional context line 2\n"
        "unrelated line at end\n"
    )
    lines = _extract_errors_from_log(log)
    text = "\n".join(lines)
    assert "something went wrong" in text
    assert "context line 1" in text


def test_shows_last_errors_when_many(tmp_path):
    """Bei vielen error-Zeilen nur die letzten paar zeigen, sonst wird es unlesbar."""
    log = tmp_path / "build.log"
    content = "\n".join([f"error: failure {i}" for i in range(50)])
    log.write_text(content)
    lines = _extract_errors_from_log(log, max_matches=3)
    assert len(lines) <= 10  # 3 errors + kleiner Kontext je, nicht alle 50
    # Die letzten errors müssen drin sein
    text = "\n".join(lines)
    assert "failure 49" in text
    assert "failure 0" not in text


def test_fallback_to_tail_when_no_error_keyword(tmp_path):
    """Wenn keine error-Zeile gefunden, zeige die letzten Zeilen als Fallback."""
    log = tmp_path / "build.log"
    content = "\n".join([f"line {i}" for i in range(30)])
    log.write_text(content)
    lines = _extract_errors_from_log(log)
    assert len(lines) > 0
    text = "\n".join(lines)
    assert "line 29" in text  # letzte Zeile muss drin sein


def test_handles_missing_log(tmp_path):
    """Existiert das Log nicht (z.B. Exception vor open), kein Crash."""
    lines = _extract_errors_from_log(tmp_path / "does-not-exist.log")
    assert lines == []


def test_handles_empty_log(tmp_path):
    log = tmp_path / "build.log"
    log.write_text("")
    lines = _extract_errors_from_log(log)
    assert lines == []
