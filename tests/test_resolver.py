import json
from unittest.mock import patch, MagicMock
from pbrew.core.resolver import fetch_latest, fetch_known, PhpRelease


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

MOCK_ALL = {
    "8.4.22": MOCK_SINGLE["8.4.22"],
    "8.4.20": {
        "source": [
            {"filename": "php-8.4.20.tar.bz2", "sha256": "eee", "md5": "fff"}
        ]
    },
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
    with patch("pbrew.core.resolver.urllib.request.urlopen", return_value=_mock_urlopen(MOCK_ALL)):
        releases = fetch_known(8)
    assert len(releases) == 3


def test_fetch_known_sorted_descending():
    with patch("pbrew.core.resolver.urllib.request.urlopen", return_value=_mock_urlopen(MOCK_ALL)):
        releases = fetch_known(8)
    versions = [r.version for r in releases]
    assert versions == sorted(versions, reverse=True)
