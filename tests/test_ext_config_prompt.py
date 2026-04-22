from unittest.mock import patch, MagicMock
from pathlib import Path
from pbrew.cli.ext import _prompt_config_choice


def test_prompt_config_choice_existing(tmp_path: Path):
    configs = tmp_path / "configs"
    configs.mkdir()
    (configs / "default.toml").write_text("[build]\nvariants=[\"default\"]\n")
    (configs / "dev.toml").write_text("[build]\nvariants=[\"default\"]\n")

    mock_q = MagicMock()
    mock_q.ask.return_value = "dev.toml"
    with patch("pbrew.cli.ext.questionary.select", return_value=mock_q):
        choice = _prompt_config_choice(configs, active_family="8.4")
    assert choice == configs / "dev.toml"


def test_prompt_config_choice_new(tmp_path: Path):
    configs = tmp_path / "configs"
    configs.mkdir()
    (configs / "default.toml").write_text("[build]\nvariants=[\"default\"]\n")

    select_mock = MagicMock()
    select_mock.ask.return_value = "<neu>"
    text_mock = MagicMock()
    text_mock.ask.return_value = "myprofile"
    with patch("pbrew.cli.ext.questionary.select", return_value=select_mock), \
         patch("pbrew.cli.ext.questionary.text", return_value=text_mock):
        choice = _prompt_config_choice(configs, active_family="8.4")
    assert choice == configs / "myprofile.toml"
