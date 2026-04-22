import json
import os
from unittest.mock import patch
from click.testing import CliRunner
from pbrew.cli import main


def _invoke_clean(prefix, tmp_path, *extra_args):
    args = ["--prefix", str(prefix), "clean", *extra_args]
    runner = CliRunner()
    with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(tmp_path / "config")}):
        return runner.invoke(main, args)


def _make_build_dir(prefix, version, ext=None):
    d = prefix / "build" / version
    if ext:
        d = d / ext
    d.mkdir(parents=True)
    (d / "dummy.c").write_text("// dummy\n")
    return d


def _make_tarball(prefix, version):
    ddir = prefix / "distfiles"
    ddir.mkdir(parents=True, exist_ok=True)
    tb = ddir / f"php-{version}.tar.bz2"
    tb.write_bytes(b"dummy")
    return tb


def _make_state(prefix, family, installed_versions):
    sdir = prefix / "state"
    sdir.mkdir(parents=True, exist_ok=True)
    state = {"active": installed_versions[0], "installed": {v: {} for v in installed_versions}}
    (sdir / f"{family}.json").write_text(json.dumps(state))


def test_clean_removes_all_build_dirs(tmp_path):
    _make_build_dir(tmp_path, "8.4.22")
    _make_build_dir(tmp_path, "8.5.5", "xdebug-3.5.1")
    result = _invoke_clean(tmp_path, tmp_path)
    assert result.exit_code == 0, result.output
    assert not (tmp_path / "build" / "8.4.22").exists()
    assert not (tmp_path / "build" / "8.5.5").exists()


def test_clean_removes_old_tarballs(tmp_path):
    _make_state(tmp_path, "8.4", ["8.4.22"])
    _make_tarball(tmp_path, "8.4.21")
    _make_tarball(tmp_path, "8.4.22")
    result = _invoke_clean(tmp_path, tmp_path)
    assert result.exit_code == 0, result.output
    assert not (tmp_path / "distfiles" / "php-8.4.21.tar.bz2").exists()
    assert (tmp_path / "distfiles" / "php-8.4.22.tar.bz2").exists()


def test_clean_dry_run_keeps_everything(tmp_path):
    _make_build_dir(tmp_path, "8.4.22")
    _make_state(tmp_path, "8.4", ["8.4.22"])
    _make_tarball(tmp_path, "8.4.21")
    result = _invoke_clean(tmp_path, tmp_path, "--dry-run")
    assert result.exit_code == 0, result.output
    assert (tmp_path / "build" / "8.4.22").exists()
    assert (tmp_path / "distfiles" / "php-8.4.21.tar.bz2").exists()
    assert "[dry-run]" in result.output


def test_clean_no_build_dirs_reports_nothing_found(tmp_path):
    result = _invoke_clean(tmp_path, tmp_path)
    assert result.exit_code == 0, result.output
    assert "gefunden" in result.output.lower()


def test_clean_version_removes_specific_build_dir(tmp_path):
    _make_build_dir(tmp_path, "8.4.22")
    _make_build_dir(tmp_path, "8.5.5")
    result = _invoke_clean(tmp_path, tmp_path, "8.4.22")
    assert result.exit_code == 0, result.output
    assert not (tmp_path / "build" / "8.4.22").exists()
    assert (tmp_path / "build" / "8.5.5").exists()


def test_clean_version_reports_when_not_found(tmp_path):
    result = _invoke_clean(tmp_path, tmp_path, "8.4.99")
    assert result.exit_code == 0, result.output
    assert "gefunden" in result.output.lower()
