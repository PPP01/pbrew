import tarfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch, MagicMock
from pbrew.extensions.installer import (
    extract_tarball,
    install_extension,
    write_ext_ini,
)

PREFIX = Path("/opt/pbrew")


def _make_tgz(tmp_path: Path, name: str) -> Path:
    """Erstellt einen minimalen .tgz für Tests."""
    src = tmp_path / name
    src.mkdir()
    (src / "config.m4").write_text("PHP_ARG_ENABLE(myext)")
    tgz = tmp_path / f"{name}.tgz"
    with tarfile.open(tgz, "w:gz") as tar:
        tar.add(src, arcname=name)
    return tgz


def test_extract_tarball_returns_src_dir(tmp_path):
    tgz = _make_tgz(tmp_path, "xdebug-3.3.2")
    dest = tmp_path / "build"
    src_dir = extract_tarball(tgz, dest)
    assert src_dir.exists()
    assert src_dir.name == "xdebug-3.3.2"


def test_extract_tarball_creates_dest_dir(tmp_path):
    tgz = _make_tgz(tmp_path, "apcu-5.1.0")
    dest = tmp_path / "build" / "nested"
    extract_tarball(tgz, dest)
    assert dest.exists()


def test_write_ext_ini_creates_file(tmp_path):
    ini = write_ext_ini(tmp_path, "8.4", "apcu")
    assert ini.exists()
    assert ini.read_text() == "extension=apcu.so\n"


def test_write_ext_ini_zend_extension(tmp_path):
    ini = write_ext_ini(tmp_path, "8.4", "xdebug", is_zend=True)
    assert ini.read_text() == "zend_extension=xdebug.so\n"


def test_write_ext_ini_does_not_overwrite(tmp_path):
    ini = write_ext_ini(tmp_path, "8.4", "apcu")
    ini.write_text("custom=value\n")
    write_ext_ini(tmp_path, "8.4", "apcu")
    assert ini.read_text() == "custom=value\n"


def test_write_ext_ini_path(tmp_path):
    ini = write_ext_ini(tmp_path, "8.4", "redis")
    assert ini == tmp_path / "etc" / "conf.d" / "8.4" / "redis.ini"


def test_install_extension_calls_phpize(tmp_path):
    src_dir = tmp_path / "ext-src"
    src_dir.mkdir()
    (src_dir / "configure").write_text("#!/bin/bash\necho ok")
    (src_dir / "configure").chmod(0o755)

    calls: list[str] = []

    def fake_popen(cmd, **kwargs):
        calls.append(cmd[0].split("/")[-1] if "/" in cmd[0] else cmd[0])
        proc = MagicMock()
        proc.stdout = iter([])
        proc.wait.return_value = None
        proc.returncode = 0
        return proc

    with patch("pbrew.extensions.installer.subprocess.Popen", side_effect=fake_popen):
        install_extension(PREFIX, "8.4.22", "myext", src_dir, 4, StringIO())

    assert "phpize" in calls
    assert "make" in calls
