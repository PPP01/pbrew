def test_pecl_suggestions_contains_popular_names():
    from pbrew.cli.ext import _PECL_SUGGESTIONS
    assert "xdebug" in _PECL_SUGGESTIONS
    assert "apcu" in _PECL_SUGGESTIONS
    assert "redis" in _PECL_SUGGESTIONS
    assert "imagick" in _PECL_SUGGESTIONS
    # Keine Dopplung mit Standard-Extensions
    from pbrew.cli.ext import _STANDARD_EXTENSIONS
    assert _PECL_SUGGESTIONS.isdisjoint(_STANDARD_EXTENSIONS)
