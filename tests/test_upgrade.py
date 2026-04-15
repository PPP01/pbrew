import json
import os
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from pbrew.cli import main
from pbrew.core.resolver import PhpRelease


def _make_release(version):
    family = ".".join(version.split(".")[:2])
    return PhpRelease(version=version, family=family,
                      tarball_url=f"https://x/{version}.tar.bz2", sha256="abc")


def _setup_installed(prefix, family, version, previous=None):
    (prefix / "versions" / version / "bin").mkdir(parents=True, exist_ok=True)
    state_dir = prefix / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state = {"active": version, "installed": {version: {}}}
    if previous:
        state["previous"] = previous
        (prefix / "versions" / previous / "bin").mkdir(parents=True, exist_ok=True)
        state["installed"][previous] = {}
    (state_dir / f"{family}.json").write_text(json.dumps(state))


def _invoke(prefix, tmp_path, *args, fetch_return=None, fetch_raises=None):
    runner = CliRunner()
    env = {"XDG_CONFIG_HOME": str(tmp_path / "config")}
    patches = [patch.dict(os.environ, env)]
    if fetch_return is not None:
        patches.append(patch("pbrew.cli.upgrade.fetch_latest", return_value=fetch_return))
    elif fetch_raises is not None:
        patches.append(patch("pbrew.cli.upgrade.fetch_latest", side_effect=fetch_raises))
    # Guards, damit ctx.invoke(install_cmd, ...) nichts wirklich tut
    patches.append(patch("pbrew.cli.upgrade.install_cmd") if False else _noop())
    with _stack(patches):
        return runner.invoke(main, ["--prefix", str(prefix)] + list(args))


from contextlib import ExitStack, contextmanager


@contextmanager
def _noop():
    yield None


@contextmanager
def _stack(patches):
    with ExitStack() as es:
        for p in patches:
            es.enter_context(p)
        yield


# ---------------------------------------------------------------------------
# upgrade — keine installierten Versionen
# ---------------------------------------------------------------------------

def test_upgrade_without_versions(tmp_path):
    result = _invoke(tmp_path, tmp_path, "upgrade")
    assert result.exit_code == 0
    assert "Keine installierten" in result.output


# ---------------------------------------------------------------------------
# upgrade — alle aktuell
# ---------------------------------------------------------------------------

def test_upgrade_all_current(tmp_path):
    _setup_installed(tmp_path, "8.4", "8.4.22")
    result = _invoke(tmp_path, tmp_path, "upgrade", "8.4",
                     fetch_return=_make_release("8.4.22"))
    assert result.exit_code == 0
    assert "aktuell" in result.output
    assert "Alle Versionen" in result.output


# ---------------------------------------------------------------------------
# upgrade --dry-run zeigt Updates ohne zu installieren
# ---------------------------------------------------------------------------

def test_upgrade_dry_run(tmp_path):
    _setup_installed(tmp_path, "8.4", "8.4.21")
    result = _invoke(tmp_path, tmp_path, "upgrade", "8.4", "--dry-run",
                     fetch_return=_make_release("8.4.22"))
    assert result.exit_code == 0
    assert "8.4.21" in result.output
    assert "8.4.22" in result.output
    assert "verfügbar" in result.output


# ---------------------------------------------------------------------------
# upgrade — Netzwerkfehler pro Family
# ---------------------------------------------------------------------------

def test_upgrade_handles_fetch_error(tmp_path):
    _setup_installed(tmp_path, "8.4", "8.4.21")
    result = _invoke(tmp_path, tmp_path, "upgrade", "8.4",
                     fetch_raises=RuntimeError("Netzwerk weg"))
    # Kein Crash; Fehler wird gemeldet, Gesamtlauf endet sauber
    assert "Fehler beim Abrufen" in result.output


# ---------------------------------------------------------------------------
# rollback
# ---------------------------------------------------------------------------

def test_rollback_without_previous_fails(tmp_path):
    _setup_installed(tmp_path, "8.4", "8.4.22")
    result = _invoke(tmp_path, tmp_path, "rollback", "8.4")
    assert result.exit_code != 0
    assert "Keine vorherige" in result.output


def test_rollback_previous_not_installed_fails(tmp_path):
    _setup_installed(tmp_path, "8.4", "8.4.22", previous="8.4.21")
    # Directory für previous entfernen → simuliert 'bereits bereinigt'
    import shutil
    shutil.rmtree(tmp_path / "versions" / "8.4.21")
    result = _invoke(tmp_path, tmp_path, "rollback", "8.4")
    assert result.exit_code != 0
    assert "nicht mehr installiert" in result.output


def test_rollback_switches_to_previous(tmp_path):
    _setup_installed(tmp_path, "8.4", "8.4.22", previous="8.4.21")
    # write_versioned_wrappers wird gemockt, damit keine Binaries nötig sind
    runner = CliRunner()
    env = {"XDG_CONFIG_HOME": str(tmp_path / "config")}
    with patch.dict(os.environ, env), \
         patch("pbrew.cli.upgrade.write_versioned_wrappers" if False else
               "pbrew.core.wrappers.write_versioned_wrappers"), \
         patch("subprocess.run"):  # sudo-Aufrufe blockieren
        result = runner.invoke(main, ["--prefix", str(tmp_path), "rollback", "8.4"])
    assert result.exit_code == 0, result.output
    assert "Rollback" in result.output
