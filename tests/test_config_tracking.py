import json
from pathlib import Path
from pbrew.core.state import record_install, get_family_state


# ---------------------------------------------------------------------------
# record_install speichert variants
# ---------------------------------------------------------------------------

def test_record_install_stores_variants(tmp_path):
    sf = tmp_path / "8.4.json"
    variants = ["default", "fpm", "intl", "mysql", "opcache"]
    record_install(sf, "8.4.22", config="dev", variants=variants)
    state = get_family_state(sf)
    assert state["installed"]["8.4.22"]["variants"] == variants


def test_record_install_stores_config_name_in_entry(tmp_path):
    sf = tmp_path / "8.4.json"
    record_install(sf, "8.4.22", config="prod", variants=["default"])
    state = get_family_state(sf)
    assert state["installed"]["8.4.22"]["config_name"] == "prod"


def test_record_install_without_variants_still_works(tmp_path):
    """Variants-Parameter ist optional – bestehende Aufrufe ohne ihn funktionieren weiter."""
    sf = tmp_path / "8.4.json"
    record_install(sf, "8.4.22", config="default")
    state = get_family_state(sf)
    assert "8.4.22" in state["installed"]
    # variants ist None oder nicht vorhanden – kein Fehler
    entry = state["installed"]["8.4.22"]
    assert "variants" not in entry or entry["variants"] is None


def test_record_install_overwrites_previous_variants(tmp_path):
    """Zweiter Install mit anderen Variants überschreibt den vorherigen Eintrag."""
    sf = tmp_path / "8.4.json"
    record_install(sf, "8.4.22", config="standard", variants=["default", "fpm"])
    record_install(sf, "8.4.22", config="dev", variants=["default", "fpm", "xdebug"])
    state = get_family_state(sf)
    assert state["installed"]["8.4.22"]["variants"] == ["default", "fpm", "xdebug"]


# ---------------------------------------------------------------------------
# install_cmd übergibt variants an record_install
# ---------------------------------------------------------------------------

def test_install_cmd_passes_variants_to_record_install(tmp_path):
    """Smoke-Test: install.py ruft record_install mit variants auf."""
    import ast, inspect
    from pbrew.cli import install
    src = inspect.getsource(install)
    tree = ast.parse(src)
    # Suche nach record_install-Aufruf mit variants-Argument
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = getattr(func, "attr", None) or getattr(func, "id", None)
            if name == "record_install":
                keywords = [kw.arg for kw in node.keywords]
                assert "variants" in keywords, \
                    "record_install wird ohne 'variants'-Argument aufgerufen"
                return
    raise AssertionError("record_install nicht in install.py gefunden")
