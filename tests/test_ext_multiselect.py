from unittest.mock import patch, MagicMock
from pbrew.cli.ext import _prompt_multiselect


def test_prompt_multiselect_groups_and_returns_choices():
    mock = MagicMock()
    mock.ask.return_value = ["Lokale .so::redis", "Standard (Rebuild)::intl"]
    groups = {
        "Lokale .so": ["redis"],
        "PECL": ["xdebug"],
        "Standard (Rebuild)": ["intl", "mysql"],
    }
    with patch("pbrew.cli.ext.questionary.checkbox", return_value=mock) as cb:
        result = _prompt_multiselect("Was hinzufuegen?", groups)
    assert result == {"Lokale .so": ["redis"], "Standard (Rebuild)": ["intl"]}
    # sichergehen, dass Separators gebaut wurden
    called_choices = cb.call_args.kwargs["choices"]
    assert any(getattr(c, "title", None) is not None for c in called_choices) \
        or any("Separator" in type(c).__name__ for c in called_choices)


def test_prompt_multiselect_returns_empty_on_abort():
    mock = MagicMock()
    mock.ask.return_value = None
    with patch("pbrew.cli.ext.questionary.checkbox", return_value=mock):
        result = _prompt_multiselect("x", {"g": ["a"]})
    assert result == {}
