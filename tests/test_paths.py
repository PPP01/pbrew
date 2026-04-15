import pytest
from pathlib import Path
from pbrew.core.paths import (
    family_from_version,
    version_dir,
    cli_ini_dir,
    confd_dir,
    state_file,
    bin_dir,
    build_log,
    version_bin,
)

PREFIX = Path("/opt/pbrew")


def test_family_from_version_full():
    assert family_from_version("8.4.22") == "8.4"


def test_family_from_version_short_digits():
    assert family_from_version("84") == "8.4"


def test_family_from_version_two_part():
    assert family_from_version("8.4") == "8.4"


def test_family_from_version_invalid():
    with pytest.raises(ValueError):
        family_from_version("abc")


def test_version_dir():
    assert version_dir(PREFIX, "8.4.22") == Path("/opt/pbrew/versions/8.4.22")


def test_cli_ini_dir():
    assert cli_ini_dir(PREFIX, "8.4") == Path("/opt/pbrew/etc/cli/8.4")


def test_confd_dir():
    assert confd_dir(PREFIX, "8.4") == Path("/opt/pbrew/etc/conf.d/8.4")


def test_state_file():
    assert state_file(PREFIX, "8.4") == Path("/opt/pbrew/state/8.4.json")


def test_bin_dir():
    assert bin_dir(PREFIX) == Path("/opt/pbrew/bin")


def test_build_log():
    assert build_log(PREFIX, "8.4.22") == Path("/opt/pbrew/state/logs/8.4.22-build.log")


def test_version_bin():
    assert version_bin(PREFIX, "8.4.22", "php") == Path("/opt/pbrew/versions/8.4.22/bin/php")
