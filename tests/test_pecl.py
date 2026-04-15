from unittest.mock import patch, MagicMock
import pytest
from pbrew.extensions.pecl import fetch_releases, fetch_latest_stable, PeclRelease

_XML = b"""<?xml version="1.0" encoding="UTF-8" ?>
<a xmlns="http://pear.php.net/dtd/rest.allreleases">
 <p>xdebug</p>
 <c>pecl.php.net</c>
 <r><v>3.3.2</v><s>stable</s></r>
 <r><v>3.3.1</v><s>stable</s></r>
 <r><v>3.4.0beta1</v><s>beta</s></r>
</a>"""


def _mock_urlopen(data: bytes):
    mock_resp = MagicMock()
    mock_resp.read.return_value = data
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def test_fetch_releases_returns_all():
    with patch("pbrew.extensions.pecl.urllib.request.urlopen",
               return_value=_mock_urlopen(_XML)):
        releases = fetch_releases("xdebug")
    assert len(releases) == 3


def test_fetch_releases_parses_version():
    with patch("pbrew.extensions.pecl.urllib.request.urlopen",
               return_value=_mock_urlopen(_XML)):
        releases = fetch_releases("xdebug")
    assert releases[0].version == "3.3.2"


def test_fetch_releases_parses_stability():
    with patch("pbrew.extensions.pecl.urllib.request.urlopen",
               return_value=_mock_urlopen(_XML)):
        releases = fetch_releases("xdebug")
    assert releases[0].stability == "stable"
    assert releases[2].stability == "beta"


def test_fetch_releases_builds_tarball_url():
    with patch("pbrew.extensions.pecl.urllib.request.urlopen",
               return_value=_mock_urlopen(_XML)):
        releases = fetch_releases("xdebug")
    assert releases[0].tarball_url == "https://pecl.php.net/get/xdebug-3.3.2.tgz"


def test_fetch_latest_stable_skips_beta():
    with patch("pbrew.extensions.pecl.urllib.request.urlopen",
               return_value=_mock_urlopen(_XML)):
        release = fetch_latest_stable("xdebug")
    assert release.version == "3.3.2"
    assert release.stability == "stable"


def test_fetch_latest_stable_raises_when_no_stable():
    xml_only_beta = b"""<?xml version="1.0" ?>
<a xmlns="http://pear.php.net/dtd/rest.allreleases">
 <r><v>1.0.0beta</v><s>beta</s></r>
</a>"""
    with patch("pbrew.extensions.pecl.urllib.request.urlopen",
               return_value=_mock_urlopen(xml_only_beta)):
        with pytest.raises(RuntimeError, match="[Kk]ein stabiles"):
            fetch_latest_stable("myext")
