import hashlib
from unittest.mock import patch, MagicMock
import pytest
from pbrew.utils.download import download


CONTENT = b"fake tarball content " * 100


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _mock_response(content: bytes):
    mock_resp = MagicMock()
    mock_resp.headers.get.return_value = str(len(content))
    mock_resp.read.side_effect = [content[:1024], content[1024:], b""]
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def test_download_writes_file(tmp_path):
    dest = tmp_path / "php-8.4.22.tar.bz2"
    with patch("pbrew.utils.download.urllib.request.urlopen", return_value=_mock_response(CONTENT)):
        download("https://example.com/php.tar.bz2", dest)
    assert dest.exists()
    assert dest.read_bytes() == CONTENT


def test_download_verifies_sha256(tmp_path):
    dest = tmp_path / "php.tar.bz2"
    correct_sha = _sha256(CONTENT)
    with patch("pbrew.utils.download.urllib.request.urlopen", return_value=_mock_response(CONTENT)):
        download("https://example.com/php.tar.bz2", dest, expected_sha256=correct_sha)
    assert dest.exists()


def test_download_raises_on_wrong_sha256(tmp_path):
    dest = tmp_path / "php.tar.bz2"
    with patch("pbrew.utils.download.urllib.request.urlopen", return_value=_mock_response(CONTENT)):
        with pytest.raises(ValueError, match="SHA-256"):
            download("https://example.com/php.tar.bz2", dest, expected_sha256="wrong")
    assert not dest.exists()


def test_download_creates_parent_dirs(tmp_path):
    dest = tmp_path / "sub" / "dir" / "file.tar.bz2"
    with patch("pbrew.utils.download.urllib.request.urlopen", return_value=_mock_response(CONTENT)):
        download("https://example.com/php.tar.bz2", dest)
    assert dest.exists()
