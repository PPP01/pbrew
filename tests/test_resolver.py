import json
from unittest.mock import patch, MagicMock, call
import pytest
from pbrew.core.resolver import fetch_latest, fetch_known, fetch_specific, PhpRelease


MOCK_SINGLE = {
    "8.4.22": {
        "announcement": {},
        "tags": [],
        "date": "14 Apr 2026",
        "source": [
            {
                "filename": "php-8.4.22.tar.gz",
                "name": "PHP 8.4.22 (tar.gz)",
                "sha256": "aaa",
                "md5": "bbb",
            },
            {
                "filename": "php-8.4.22.tar.bz2",
                "name": "PHP 8.4.22 (tar.bz2)",
                "sha256": "ccc111",
                "md5": "ddd",
            },
        ],
    }
}

# fetch_known macht 3 Requests: 1× Meta + 1× pro Family
MOCK_KNOWN_META = {"supported_versions": ["8.4", "8.3"], "version": "8.4.22"}
MOCK_KNOWN_84 = {
    "8.4.22": MOCK_SINGLE["8.4.22"],
    "8.4.20": {
        "source": [
            {"filename": "php-8.4.20.tar.bz2", "sha256": "eee", "md5": "fff"}
        ]
    },
}
MOCK_KNOWN_83 = {
    "8.3.10": {
        "source": [
            {"filename": "php-8.3.10.tar.bz2", "sha256": "ggg", "md5": "hhh"}
        ]
    },
}


def _mock_urlopen(data: dict):
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(data).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def _mock_urlopen_sequence(*responses):
    """Gibt bei aufeinanderfolgenden Calls unterschiedliche Responses zurück."""
    mocks = [_mock_urlopen(r) for r in responses]
    return MagicMock(side_effect=mocks)


def test_fetch_latest_returns_release():
    with patch("pbrew.core.resolver.urllib.request.urlopen", return_value=_mock_urlopen(MOCK_SINGLE)):
        release = fetch_latest("8.4")
    assert release.version == "8.4.22"
    assert release.family == "8.4"
    assert release.sha256 == "ccc111"
    assert "php-8.4.22.tar.bz2" in release.tarball_url


def test_fetch_latest_selects_bz2_over_gz():
    with patch("pbrew.core.resolver.urllib.request.urlopen", return_value=_mock_urlopen(MOCK_SINGLE)):
        release = fetch_latest("8.4")
    assert release.tarball_url.endswith(".tar.bz2")


def test_fetch_known_returns_all_releases():
    with patch("pbrew.core.resolver.urllib.request.urlopen",
               _mock_urlopen_sequence(MOCK_KNOWN_META, MOCK_KNOWN_84, MOCK_KNOWN_83)):
        releases = fetch_known(8)
    assert len(releases) == 3


def test_fetch_known_sorted_descending():
    with patch("pbrew.core.resolver.urllib.request.urlopen",
               _mock_urlopen_sequence(MOCK_KNOWN_META, MOCK_KNOWN_84, MOCK_KNOWN_83)):
        releases = fetch_known(8)
    versions = [r.version for r in releases]
    assert versions == sorted(versions, reverse=True)


def test_fetch_specific_returns_exact_version():
    family_data = {
        "8.4.22": MOCK_SINGLE["8.4.22"],
        "8.4.19": {
            "source": [{"filename": "php-8.4.19.tar.bz2", "sha256": "old123", "md5": "x"}]
        },
    }
    with patch("pbrew.core.resolver.urllib.request.urlopen", return_value=_mock_urlopen(family_data)):
        release = fetch_specific("8.4.19")
    assert release.version == "8.4.19"
    assert release.sha256 == "old123"
    assert "php-8.4.19.tar.bz2" in release.tarball_url


def test_fetch_specific_raises_if_not_found():
    with patch("pbrew.core.resolver.urllib.request.urlopen", return_value=_mock_urlopen(MOCK_SINGLE)):
        with pytest.raises(RuntimeError, match="nicht auf php.net gefunden"):
            fetch_specific("8.4.1")


def test_fetch_specific_raises_on_invalid_format():
    with pytest.raises(ValueError, match="Vollständige Version"):
        fetch_specific("8.4")


def test_fetch_known_numeric_sort_single_digit_patch():
    """String-Sort würde '8.3.9' nach '8.3.10' einordnen – numerisch muss 8.3.10 > 8.3.9."""
    meta = {"supported_versions": ["8.3"]}
    family_data = {
        "8.3.10": {"source": [{"filename": "php-8.3.10.tar.bz2", "sha256": "x", "md5": "y"}]},
        "8.3.9": {"source": [{"filename": "php-8.3.9.tar.bz2", "sha256": "x", "md5": "y"}]},
    }
    with patch("pbrew.core.resolver.urllib.request.urlopen",
               _mock_urlopen_sequence(meta, family_data)):
        releases = fetch_known(8)
    assert releases[0].version == "8.3.10"
    assert releases[1].version == "8.3.9"
