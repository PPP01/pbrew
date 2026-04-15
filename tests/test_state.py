from pathlib import Path
from pbrew.core.state import (
    get_family_state,
    set_active_version,
    set_build_duration,
    add_extension,
    get_global_state,
    set_global_default,
)


def test_get_family_state_returns_empty_for_missing(tmp_path):
    assert get_family_state(tmp_path / "8.4.json") == {}


def test_set_active_version_creates_file(tmp_path):
    sf = tmp_path / "8.4.json"
    set_active_version(sf, "8.4.22")
    state = get_family_state(sf)
    assert state["active"] == "8.4.22"
    assert "8.4.22" in state["installed"]


def test_set_active_version_tracks_previous(tmp_path):
    sf = tmp_path / "8.4.json"
    set_active_version(sf, "8.4.20")
    set_active_version(sf, "8.4.22")
    state = get_family_state(sf)
    assert state["active"] == "8.4.22"
    assert state["previous"] == "8.4.20"


def test_set_active_version_stores_config_name(tmp_path):
    sf = tmp_path / "8.4.json"
    set_active_version(sf, "8.4.22", config="production")
    assert get_family_state(sf)["config"] == "production"


def test_set_build_duration(tmp_path):
    sf = tmp_path / "8.4.json"
    set_active_version(sf, "8.4.22")
    set_build_duration(sf, "8.4.22", 134.7)
    state = get_family_state(sf)
    assert state["installed"]["8.4.22"]["build_duration_seconds"] == 135


def test_add_extension(tmp_path):
    sf = tmp_path / "8.4.json"
    add_extension(sf, "apcu")
    add_extension(sf, "redis")
    add_extension(sf, "apcu")  # duplicate
    state = get_family_state(sf)
    assert state["extensions"] == ["apcu", "redis"]


def test_set_global_default(tmp_path):
    gsf = tmp_path / "global.json"
    set_global_default(gsf, "8.4")
    assert get_global_state(gsf)["default_family"] == "8.4"
