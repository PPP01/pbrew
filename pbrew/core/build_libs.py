"""Pre-Flight-Check für Build-Libraries.

Prüft vor dem PHP-Build, ob alle nötigen Dev-Libraries installiert sind.
Strategie pro Lib: erst pkg-config, dann Header-Fallback (für Libs ohne
verlässlichen .pc-File wie bz2 oder readline).
"""
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from pbrew.core.prerequisites import detect_package_manager


@dataclass(frozen=True)
class LibCheck:
    """Wie eine Build-Library auf System-Verfügbarkeit geprüft wird."""
    pkgconfig: "str | None" = None
    headers: tuple[str, ...] = field(default_factory=tuple)


# Lib-ID → Prüfstrategie.
# Die Lib-ID ist der Schlüssel, über den DISTRO_PACKAGES gemappt werden.
LIB_CHECKS: dict[str, LibCheck] = {
    # pkg-config verfügbar
    "openssl":      LibCheck(pkgconfig="openssl"),
    "icu-uc":       LibCheck(pkgconfig="icu-uc"),
    "libxml-2.0":   LibCheck(pkgconfig="libxml-2.0"),
    "libcurl":      LibCheck(pkgconfig="libcurl"),
    "libzip":       LibCheck(pkgconfig="libzip"),
    "sqlite3":      LibCheck(pkgconfig="sqlite3"),
    "libpq":        LibCheck(pkgconfig="libpq"),
    "libsystemd":   LibCheck(pkgconfig="libsystemd"),
    "zlib":         LibCheck(pkgconfig="zlib"),
    "oniguruma":    LibCheck(pkgconfig="oniguruma"),
    "gmp":          LibCheck(headers=("/usr/include/gmp.h",)),
    # pkg-config + Header-Fallback (je nach Distro unzuverlässig)
    "tidy":         LibCheck(
        pkgconfig="tidy",
        headers=("/usr/include/tidy.h", "/usr/include/tidy/tidy.h"),
    ),
    # Nur Header (keine .pc-Files im Upstream-Projekt)
    "bz2":          LibCheck(
        headers=("/usr/include/bzlib.h",),
    ),
    "readline":     LibCheck(
        headers=(
            "/usr/include/readline/readline.h",
            "/usr/include/x86_64-linux-gnu/readline/readline.h",
        ),
    ),
}

# Variant-Name → Lib-ID
VARIANT_LIB: dict[str, str] = {
    "openssl":      "openssl",
    "intl":         "icu-uc",
    "soap":         "libxml-2.0",
    "curl":         "libcurl",
    "zip":          "libzip",
    "sqlite":       "sqlite3",
    "pgsql":        "libpq",
    "fpm-systemd":  "libsystemd",
    "zlib":         "zlib",
    "tidy":         "tidy",
    "bz2":          "bz2",
    "readline":     "readline",
    "mbstring":     "oniguruma",
    "gmp":          "gmp",
}

# PHP 8.x braucht das immer (unabhängig von Variants):
#   libxml-2.0  → für XML-Parser im Core
#   sqlite3     → bundled SQLite3-Extension seit PHP 7.4
ALWAYS_REQUIRED: dict[str, str] = {
    "libxml-2.0":   "core",
    "sqlite3":      "core",
}

# Lib-ID → Distro-Paketname pro Paketmanager
DISTRO_PACKAGES: dict[str, dict[str, str]] = {
    "openssl":      {"apt-get": "libssl-dev",           "dnf": "openssl-devel",     "brew": "openssl"},
    "icu-uc":       {"apt-get": "libicu-dev",           "dnf": "libicu-devel",      "brew": "icu4c"},
    "libxml-2.0":   {"apt-get": "libxml2-dev",          "dnf": "libxml2-devel",     "brew": "libxml2"},
    "libcurl":      {"apt-get": "libcurl4-openssl-dev", "dnf": "libcurl-devel",     "brew": "curl"},
    "libzip":       {"apt-get": "libzip-dev",           "dnf": "libzip-devel",      "brew": "libzip"},
    "sqlite3":      {"apt-get": "libsqlite3-dev",       "dnf": "sqlite-devel",      "brew": "sqlite"},
    "libpq":        {"apt-get": "libpq-dev",            "dnf": "postgresql-devel",  "brew": "postgresql"},
    "libsystemd":   {"apt-get": "libsystemd-dev",       "dnf": "systemd-devel"},
    "zlib":         {"apt-get": "zlib1g-dev",           "dnf": "zlib-devel",        "brew": "zlib"},
    "tidy":         {"apt-get": "libtidy-dev",          "dnf": "libtidy-devel",     "brew": "tidy-html5"},
    "bz2":          {"apt-get": "libbz2-dev",           "dnf": "bzip2-devel",       "brew": "bzip2"},
    "readline":     {"apt-get": "libreadline-dev",      "dnf": "readline-devel",    "brew": "readline"},
    "oniguruma":    {"apt-get": "libonig-dev",          "dnf": "oniguruma-devel",   "brew": "oniguruma"},
    "gmp":          {"apt-get": "libgmp-dev",           "dnf": "gmp-devel",         "brew": "gmp"},
}


@dataclass
class MissingLib:
    name: str                   # Lib-ID aus LIB_CHECKS
    variant: str                # "core" für ALWAYS_REQUIRED
    distro_pkg: "str | None"


def check_required_libs(variants: list[str]) -> list[MissingLib]:
    """Prüft, ob alle für die Variants benötigten Libs da sind."""
    # Ohne pkg-config können wir pkg-config-basierte Libs nicht prüfen → kein Check.
    # Header-only-Libs würden zwar funktionieren, aber das ist inkonsistent – lieber gar nichts melden.
    if not shutil.which("pkg-config"):
        return []

    needed: list[tuple[str, str]] = list(ALWAYS_REQUIRED.items())
    for variant in variants:
        lib_id = VARIANT_LIB.get(variant)
        if lib_id:
            needed.append((lib_id, variant))

    seen: set[str] = set()
    pm = detect_package_manager()
    missing: list[MissingLib] = []
    for lib_id, source in needed:
        if lib_id in seen:
            continue
        seen.add(lib_id)
        if _lib_available(lib_id):
            continue
        distro_pkg = DISTRO_PACKAGES.get(lib_id, {}).get(pm) if pm else None
        missing.append(MissingLib(name=lib_id, variant=source, distro_pkg=distro_pkg or None))
    return missing


def _lib_available(lib_id: str) -> bool:
    """Prüft Lib per pkg-config (wenn definiert) UND/ODER Header-Fallback."""
    check = LIB_CHECKS.get(lib_id)
    if check is None:
        return True  # Unbekannte Libs nicht als fehlend melden
    if check.pkgconfig and _pkg_config_exists(check.pkgconfig):
        return True
    if check.headers and _headers_exist(check.headers):
        return True
    return False


def install_command(missing: list[MissingLib]) -> "str | None":
    """Liefert den Installationsbefehl für alle bekannten Distro-Pakete (oder None)."""
    pm = detect_package_manager()
    if not pm:
        return None
    pkgs = sorted({m.distro_pkg for m in missing if m.distro_pkg})
    if not pkgs:
        return None
    pkg_str = " ".join(pkgs)
    if pm == "apt-get":
        return f"sudo apt install -y {pkg_str}"
    if pm == "dnf":
        return f"sudo dnf install -y {pkg_str}"
    if pm == "brew":
        return f"brew install {pkg_str}"
    return None


def _pkg_config_exists(pkg: str) -> bool:
    try:
        result = subprocess.run(
            ["pkg-config", "--exists", pkg],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _headers_exist(paths: tuple[str, ...]) -> bool:
    """True wenn mindestens eine der Header-Dateien existiert."""
    return any(Path(p).exists() for p in paths)
