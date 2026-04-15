"""Pre-Flight-Check für Build-Libraries.

Prüft vor dem PHP-Build, ob alle nötigen Dev-Libraries installiert sind, indem
pkg-config befragt wird. Liefert eine Liste fehlender Libs mit dem passenden
Distro-Installationsbefehl.
"""
import shutil
import subprocess
from dataclasses import dataclass

from pbrew.core.prerequisites import detect_package_manager


# Variant → pkg-config-Paketname.
# Variants ohne Eintrag (z.B. bcmath, sockets) brauchen keine externe Lib.
VARIANT_PKGCONFIG: dict[str, str] = {
    "openssl":      "openssl",
    "intl":         "icu-uc",
    "soap":         "libxml-2.0",
    "curl":         "libcurl",
    "zip":          "libzip",
    "sqlite":       "sqlite3",
    "pgsql":        "libpq",
    "fpm-systemd":  "libsystemd",
    "zlib":         "zlib",
}

# PHP 8.x braucht das immer (unabhängig von Variants):
#   libxml-2.0  → für XML-Parser im Core
#   sqlite3     → bundled SQLite3-Extension seit PHP 7.4
ALWAYS_REQUIRED: dict[str, str] = {
    "libxml-2.0":   "core",
    "sqlite3":      "core",
}

# pkg-config-Name → Distro-Paketname pro Paketmanager
DISTRO_PACKAGES: dict[str, dict[str, str]] = {
    "openssl":      {"apt-get": "libssl-dev",       "dnf": "openssl-devel",    "brew": "openssl"},
    "icu-uc":       {"apt-get": "libicu-dev",       "dnf": "libicu-devel",     "brew": "icu4c"},
    "libxml-2.0":   {"apt-get": "libxml2-dev",      "dnf": "libxml2-devel",    "brew": "libxml2"},
    "libcurl":      {"apt-get": "libcurl4-openssl-dev", "dnf": "libcurl-devel", "brew": "curl"},
    "libzip":       {"apt-get": "libzip-dev",       "dnf": "libzip-devel",     "brew": "libzip"},
    "sqlite3":      {"apt-get": "libsqlite3-dev",   "dnf": "sqlite-devel",     "brew": "sqlite"},
    "libpq":        {"apt-get": "libpq-dev",        "dnf": "postgresql-devel", "brew": "postgresql"},
    "libsystemd":   {"apt-get": "libsystemd-dev",   "dnf": "systemd-devel",    "brew": ""},
    "zlib":         {"apt-get": "zlib1g-dev",       "dnf": "zlib-devel",       "brew": "zlib"},
}


@dataclass
class MissingLib:
    pkgconfig: str
    variant: str           # "core" für ALWAYS_REQUIRED
    distro_pkg: "str | None"


def check_required_libs(variants: list[str]) -> list[MissingLib]:
    """Prüft, ob alle für die Variants benötigten pkg-config-Pakete da sind."""
    if not shutil.which("pkg-config"):
        return []  # Ohne pkg-config keine zuverlässige Aussage – kein false-positive

    needed: list[tuple[str, str]] = list(ALWAYS_REQUIRED.items())
    for variant in variants:
        pkg = VARIANT_PKGCONFIG.get(variant)
        if pkg:
            needed.append((pkg, variant))

    seen: set[str] = set()
    pm = detect_package_manager()
    missing: list[MissingLib] = []
    for pkg, source in needed:
        if pkg in seen:
            continue
        seen.add(pkg)
        if not _pkg_config_exists(pkg):
            distro_pkg = DISTRO_PACKAGES.get(pkg, {}).get(pm) if pm else None
            missing.append(MissingLib(pkgconfig=pkg, variant=source, distro_pkg=distro_pkg or None))
    return missing


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
