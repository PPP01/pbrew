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
