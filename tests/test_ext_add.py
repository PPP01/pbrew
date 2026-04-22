def test_pecl_suggestions_contains_popular_names():
    from pbrew.cli.ext import _PECL_SUGGESTIONS
    assert "xdebug" in _PECL_SUGGESTIONS
    assert "apcu" in _PECL_SUGGESTIONS
    assert "redis" in _PECL_SUGGESTIONS
    assert "imagick" in _PECL_SUGGESTIONS
    # Keine Dopplung mit Standard-Extensions
    from pbrew.cli.ext import _STANDARD_EXTENSIONS
    assert _PECL_SUGGESTIONS.isdisjoint(_STANDARD_EXTENSIONS)


def test_collect_add_candidates_splits_four_buckets():
    from pbrew.cli.ext import _collect_add_candidates

    loaded = {"json": ("json", "8.4"), "spl": ("spl", "8.4")}
    local = ["apcu", "redis"]
    standard = ["intl", "mysql", "tokenizer"]
    pbrew_active = {"apcu"}
    active_variants = {"opcache"}

    local_c, pecl_c, ext_c, build_opt_c = _collect_add_candidates(
        loaded=loaded, local=local, standard=standard,
        pbrew_active=pbrew_active, active_variants=active_variants,
    )
    assert local_c == ["redis"]
    assert "xdebug" in pecl_c
    assert "apcu" not in pecl_c          # ist lokal

    # ext_c = VARIANT_EXTENSIONS minus active_variants minus loaded/local
    assert "intl" in ext_c
    assert "mysql" in ext_c
    assert "tokenizer" not in ext_c      # immer eingebaut, kein Variant-Mapping
    assert "argon2" not in ext_c         # ist Build-Option, nicht Extension

    # build_opt_c = VARIANT_BUILD_OPTIONS minus active_variants
    assert "argon2" in build_opt_c


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
