import shutil
from unittest.mock import patch
from pbrew.core.prerequisites import (
    check_prerequisites,
    detect_package_manager,
    install_hint,
    REQUIRED_BINS,
    PrerequisiteResult,
)


def test_check_prerequisites_returns_one_result_per_bin():
    results = check_prerequisites()
    assert len(results) == len(REQUIRED_BINS)
    assert all(isinstance(r, PrerequisiteResult) for r in results)


def test_check_prerequisites_found_for_existing_binary():
    # gcc ist auf dem Build-System vorhanden
    results = check_prerequisites()
    gcc = next(r for r in results if r.name == "gcc")
    assert gcc.found is (shutil.which("gcc") is not None)


def test_check_prerequisites_not_found_for_missing():
    with patch("pbrew.core.prerequisites.shutil.which", return_value=None):
        results = check_prerequisites()
    assert all(not r.found for r in results)


def test_detect_package_manager_apt(tmp_path):
    def fake_which(name):
        return "/usr/bin/apt-get" if name == "apt-get" else None
    with patch("pbrew.core.prerequisites.shutil.which", side_effect=fake_which):
        assert detect_package_manager() == "apt-get"


def test_detect_package_manager_none_when_unknown():
    with patch("pbrew.core.prerequisites.shutil.which", return_value=None):
        assert detect_package_manager() is None


def test_install_hint_returns_string_for_known_pm():
    with patch("pbrew.core.prerequisites.detect_package_manager", return_value="apt-get"):
        hint = install_hint()
    assert hint is not None
    assert "apt-get" in hint


def test_install_hint_returns_none_when_no_pm():
    with patch("pbrew.core.prerequisites.detect_package_manager", return_value=None):
        assert install_hint() is None


# ---------------------------------------------------------------------------
# doctor_cmd nutzt check_prerequisites (Refactoring-Test)
# ---------------------------------------------------------------------------

def test_doctor_uses_prerequisites_module():
    """doctor_cmd importiert aus prerequisites – kein doppelter shutil.which-Code."""
    import ast, inspect
    from pbrew.cli import doctor
    src = inspect.getsource(doctor)
    tree = ast.parse(src)
    # Kein direkter Import von shutil in doctor.py
    imports = [
        node.names[0].name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
    ]
    assert "shutil" not in imports, "doctor.py importiert shutil direkt – bitte prerequisites nutzen"
