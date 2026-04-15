import shutil
from dataclasses import dataclass

REQUIRED_BINS = ["gcc", "make", "autoconf", "bison", "re2c", "pkg-config"]

_INSTALL_HINTS: dict[str, str] = {
    "apt-get": "sudo apt-get install -y build-essential autoconf bison re2c pkg-config",
    "dnf": "sudo dnf install -y gcc make autoconf bison re2c pkgconf-pkg-config",
    "brew": "brew install autoconf bison re2c pkg-config",
}


@dataclass
class PrerequisiteResult:
    name: str
    found: bool


def check_prerequisites() -> list[PrerequisiteResult]:
    """Prüft, ob alle Build-Voraussetzungen installiert sind."""
    return [PrerequisiteResult(name=b, found=shutil.which(b) is not None) for b in REQUIRED_BINS]


def detect_package_manager() -> "str | None":
    """Erkennt den verfügbaren Paketmanager (apt-get, dnf oder brew)."""
    for pm in ("apt-get", "dnf", "brew"):
        if shutil.which(pm):
            return pm
    return None


def install_hint() -> "str | None":
    """Gibt den passenden Installationsbefehl für fehlende Build-Tools zurück."""
    pm = detect_package_manager()
    return _INSTALL_HINTS.get(pm) if pm else None
