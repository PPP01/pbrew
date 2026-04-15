import json
import os
from unittest.mock import patch
from click.testing import CliRunner
from pbrew.cli import main


def _setup(prefix, family, active, other=None):
    """Legt State mit aktiver Version (active) und optional weiterer Version (other) an."""
    for version in filter(None, [active, other]):
        vdir = prefix / "versions" / version
        (vdir / "bin").mkdir(parents=True)
        (vdir / "bin" / "php").write_text("#!/bin/bash\n")

    state_dir = prefix / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    installed = {active: {"config_name": "dev"}}
    if other:
        installed[other] = {"config_name": "standard"}
    state = {"active": active, "installed": installed}
    if other:
        state["previous"] = other
    (state_dir / f"{family}.json").write_text(json.dumps(state))


def _invoke_clean(prefix, tmp_path, version, yes=True):
    args = ["--prefix", str(prefix), "clean", version]
    if yes:
        args.append("--yes")
    runner = CliRunner()
    with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / "config")}):
        return runner.invoke(main, args)


# ---------------------------------------------------------------------------
# State wird aufgeräumt
# ---------------------------------------------------------------------------

def test_clean_removes_installed_entry_from_state(tmp_path):
    _setup(tmp_path, "8.4", active="8.4.22", other="8.4.21")
    result = _invoke_clean(tmp_path, tmp_path, "8.4.21")
    assert result.exit_code == 0, result.output

    state = json.loads((tmp_path / "state" / "8.4.json").read_text())
    assert "8.4.21" not in state["installed"]
    # Die aktive Version bleibt unberührt
    assert "8.4.22" in state["installed"]


def test_clean_clears_previous_if_it_matches_removed_version(tmp_path):
    """Wenn previous == gelöschte Version, muss previous auf None."""
    _setup(tmp_path, "8.4", active="8.4.22", other="8.4.21")
    # previous ist nach _setup "8.4.21"
    result = _invoke_clean(tmp_path, tmp_path, "8.4.21")
    assert result.exit_code == 0, result.output

    state = json.loads((tmp_path / "state" / "8.4.json").read_text())
    assert state.get("previous") is None or "previous" not in state


def test_clean_keeps_previous_if_different_version(tmp_path):
    """Wenn previous != gelöschte Version, bleibt previous erhalten."""
    _setup(tmp_path, "8.4", active="8.4.22", other="8.4.21")
    # Zusätzlich noch 8.4.20 ins installed
    state_path = tmp_path / "state" / "8.4.json"
    state = json.loads(state_path.read_text())
    state["installed"]["8.4.20"] = {}
    state_path.write_text(json.dumps(state))
    (tmp_path / "versions" / "8.4.20" / "bin").mkdir(parents=True)

    result = _invoke_clean(tmp_path, tmp_path, "8.4.20")
    assert result.exit_code == 0, result.output

    state = json.loads(state_path.read_text())
    assert state.get("previous") == "8.4.21"  # unverändert


# ---------------------------------------------------------------------------
# clean blockiert aktive Version
# ---------------------------------------------------------------------------

def test_clean_refuses_to_remove_active_version(tmp_path):
    _setup(tmp_path, "8.4", active="8.4.22", other="8.4.21")
    result = _invoke_clean(tmp_path, tmp_path, "8.4.22")
    assert result.exit_code != 0
    assert "aktive" in result.output.lower()
    # Verzeichnis darf nicht gelöscht worden sein
    assert (tmp_path / "versions" / "8.4.22").exists()


# ---------------------------------------------------------------------------
# clean akzeptiert nicht-installierte Versionen ohne Fehler
# ---------------------------------------------------------------------------

def test_clean_warns_when_version_not_installed(tmp_path):
    _setup(tmp_path, "8.4", active="8.4.22")
    result = _invoke_clean(tmp_path, tmp_path, "8.4.99")
    assert result.exit_code == 0
    assert "nicht installiert" in result.output.lower()
