import json
import os
from unittest.mock import patch
from click.testing import CliRunner
from pbrew.cli import main
from pbrew.core.resolver import PhpRelease


def _make_release(version: str) -> PhpRelease:
    family = ".".join(version.split(".")[:2])
    return PhpRelease(
        version=version,
        family=family,
        tarball_url=f"https://www.php.net/distributions/php-{version}.tar.bz2",
        sha256="abc",
    )


def _setup(prefix, family, active_version):
    vdir = prefix / "versions" / active_version
    (vdir / "bin").mkdir(parents=True)
    state_dir = prefix / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / f"{family}.json").write_text(json.dumps({"active": active_version}))


def _invoke(prefix, tmp_path, fetch_side_effect):
    runner = CliRunner()
    with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / "config")}), \
         patch("pbrew.cli.outdated.fetch_latest", side_effect=fetch_side_effect):
        return runner.invoke(main, ["--prefix", str(prefix), "outdated"])


# ---------------------------------------------------------------------------
# outdated: alles aktuell
# ---------------------------------------------------------------------------

def test_outdated_all_current(tmp_path):
    _setup(tmp_path, "8.4", "8.4.22")
    result = _invoke(tmp_path, tmp_path, lambda family: _make_release("8.4.22"))
    assert result.exit_code == 0, result.output
    assert "aktuell" in result.output.lower()


# ---------------------------------------------------------------------------
# outdated: Update verfügbar → Exit 1
# ---------------------------------------------------------------------------

def test_outdated_shows_available_update(tmp_path):
    _setup(tmp_path, "8.3", "8.3.10")
    result = _invoke(tmp_path, tmp_path, lambda family: _make_release("8.3.12"))
    assert result.exit_code == 1, result.output
    assert "8.3.10" in result.output
    assert "8.3.12" in result.output
    assert "verfügbar" in result.output.lower() or "update" in result.output.lower()


# ---------------------------------------------------------------------------
# outdated: mehrere Familien mit gemischtem Status
# ---------------------------------------------------------------------------

def test_outdated_mixed_status(tmp_path):
    _setup(tmp_path, "8.4", "8.4.22")
    _setup(tmp_path, "8.3", "8.3.10")
    responses = {"8.4": _make_release("8.4.22"), "8.3": _make_release("8.3.12")}
    result = _invoke(tmp_path, tmp_path, lambda family: responses[family])
    assert result.exit_code == 1  # mindestens eine Family hat Update
    assert "8.4.22" in result.output
    assert "8.3.12" in result.output


# ---------------------------------------------------------------------------
# outdated: keine Familien installiert
# ---------------------------------------------------------------------------

def test_outdated_no_families_installed(tmp_path):
    (tmp_path / "state").mkdir()  # leer
    runner = CliRunner()
    with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / "config")}):
        result = runner.invoke(main, ["--prefix", str(tmp_path), "outdated"])
    assert result.exit_code == 0
    assert "keine" in result.output.lower()


# ---------------------------------------------------------------------------
# outdated: Netzwerkfehler pro Family soll Gesamtlauf nicht abbrechen
# ---------------------------------------------------------------------------

def test_outdated_handles_fetch_errors_gracefully(tmp_path):
    _setup(tmp_path, "8.4", "8.4.22")
    _setup(tmp_path, "8.3", "8.3.10")

    def fetcher(family):
        if family == "8.3":
            raise RuntimeError("Netzwerkfehler")
        return _make_release("8.4.22")

    result = _invoke(tmp_path, tmp_path, fetcher)
    assert "8.4.22" in result.output
    assert "fehler" in result.output.lower() or "netzwerk" in result.output.lower()
