def test_pecl_suggestions_contains_popular_names():
    from pbrew.cli.ext import _PECL_SUGGESTIONS
    assert "xdebug" in _PECL_SUGGESTIONS
    assert "apcu" in _PECL_SUGGESTIONS
    assert "redis" in _PECL_SUGGESTIONS
    assert "imagick" in _PECL_SUGGESTIONS
    # Keine Dopplung mit Standard-Extensions
    from pbrew.cli.ext import _STANDARD_EXTENSIONS
    assert _PECL_SUGGESTIONS.isdisjoint(_STANDARD_EXTENSIONS)


def test_collect_add_candidates_splits_three_buckets():
    from unittest.mock import patch
    from pbrew.cli.ext import _collect_add_candidates

    loaded = {"json": ("json", "8.4"), "spl": ("spl", "8.4")}
    local = ["apcu", "redis"]
    standard = ["intl", "mysql", "pdo_firebird"]
    pbrew_active = {"apcu"}  # apcu soll NICHT unter local_candidates landen
    active_variants = {"opcache"}

    local_c, pecl_c, rebuild_c = _collect_add_candidates(
        loaded=loaded, local=local, standard=standard,
        pbrew_active=pbrew_active, active_variants=active_variants,
    )
    assert local_c == ["redis"]
    # pecl_candidates = _PECL_SUGGESTIONS minus loaded/local/standard
    assert "xdebug" in pecl_c
    assert "apcu" not in pecl_c          # ist lokal
    # rebuild_c = standard ∩ VARIANT_EXTENSIONS minus active_variants
    assert "intl" in rebuild_c
    assert "mysql" in rebuild_c
    assert "pdo_firebird" not in rebuild_c  # kein Variant-Mapping


import tomlkit
from pathlib import Path
from pbrew.cli.ext import _update_config_variants


def test_update_config_variants_adds_without_duplicates(tmp_path: Path):
    cfg = tmp_path / "default.toml"
    cfg.write_text(tomlkit.dumps({
        "build": {"variants": ["default", "opcache"]},
    }))
    added = _update_config_variants(cfg, ["intl", "opcache", "soap"])
    data = tomlkit.loads(cfg.read_text()).unwrap()
    assert data["build"]["variants"] == [
        "default", "opcache", "intl", "soap"
    ]
    assert added == ["intl", "soap"]


def test_update_config_variants_removes(tmp_path: Path):
    from pbrew.cli.ext import _remove_config_variants
    cfg = tmp_path / "dev.toml"
    cfg.write_text(tomlkit.dumps({
        "build": {"variants": ["default", "opcache", "intl", "soap"]},
    }))
    removed = _remove_config_variants(cfg, ["intl", "notthere"])
    data = tomlkit.loads(cfg.read_text()).unwrap()
    assert data["build"]["variants"] == ["default", "opcache", "soap"]
    assert removed == ["intl"]
