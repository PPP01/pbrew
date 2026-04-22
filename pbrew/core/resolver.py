import json
import urllib.request
from dataclasses import dataclass

from pbrew.core.paths import version_key

PHP_RELEASES_URL = "https://www.php.net/releases/index.php"


@dataclass
class PhpRelease:
    version: str        # "8.4.22"
    family: str         # "8.4"
    tarball_url: str    # "https://www.php.net/distributions/php-8.4.22.tar.bz2"
    sha256: str
    eol: bool = False


def _fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read())


def _parse_release(version: str, release_data: dict) -> "PhpRelease | None":
    parts = version.split(".")
    if len(parts) < 3:
        return None
    sources = release_data.get("source", [])
    bz2 = next((s for s in sources if s.get("filename", "").endswith(".tar.bz2")), None)
    if not bz2:
        return None
    sha256 = bz2.get("sha256", "")
    if not sha256:
        return None  # Kein Hash → Release ablehnen, SHA-256-Prüfung wäre nicht möglich
    return PhpRelease(
        version=version,
        family=f"{parts[0]}.{parts[1]}",
        tarball_url=f"https://www.php.net/distributions/{bz2['filename']}",
        sha256=sha256,
    )


def fetch_latest(family: str) -> PhpRelease:
    """Gibt die neueste Version einer PHP-Family zurück (z.B. '8.4')."""
    url = f"{PHP_RELEASES_URL}?json=1&version={family}&max=1"
    data = _fetch_json(url)
    if not data:
        raise RuntimeError(f"Keine Releases für PHP {family} gefunden")
    version = next(iter(data))
    release = _parse_release(version, data[version])
    if release is None:
        raise RuntimeError(f"Keine .tar.bz2 Quelle für PHP {version} gefunden")
    return release


def fetch_specific(version: str) -> PhpRelease:
    """Gibt eine exakte PHP-Version zurück (z.B. '8.4.19').

    Lädt alle Releases der betreffenden Family und sucht die angegebene Version.
    Wirft RuntimeError, wenn die Version nicht gefunden wird (z.B. zu alt oder falsch).
    """
    parts = version.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError(f"Vollständige Version erwartet (z.B. 8.4.19), bekommen: {version}")
    family = f"{parts[0]}.{parts[1]}"
    url = f"{PHP_RELEASES_URL}?json=1&version={family}&max=100"
    data = _fetch_json(url)
    if version not in data:
        raise RuntimeError(
            f"PHP {version} nicht auf php.net gefunden – "
            f"Version nicht verfügbar oder falsch angegeben."
        )
    release = _parse_release(version, data[version])
    if release is None:
        raise RuntimeError(f"Keine .tar.bz2 Quelle für PHP {version} gefunden")
    return release


def fetch_known(major: int = 8, include_eol: bool = False) -> list[PhpRelease]:
    """Gibt alle bekannten Releases für eine Major-Version zurück.

    Fragt zuerst die supported_versions ab, dann pro Family alle Releases.
    Mit include_eol=True werden zusätzlich EOL-Families (Minor 0–9) geprobt.
    """
    meta = _fetch_json(f"{PHP_RELEASES_URL}?json=1&version={major}")
    supported: set[str] = set(meta.get("supported_versions", []))

    families: list[str] = sorted(supported, reverse=True)
    if include_eol or not supported:
        for minor in range(9, -1, -1):
            family = f"{major}.{minor}"
            if family not in supported:
                families.append(family)

    if not families:
        raise RuntimeError(f"Keine PHP-{major}.x Families gefunden")

    releases = []
    for family in families:
        try:
            data = _fetch_json(f"{PHP_RELEASES_URL}?json=1&version={family}&max=100")
        except Exception:
            continue
        if not data:
            continue
        for version, release_data in data.items():
            release = _parse_release(version, release_data)
            if release:
                release.eol = family not in supported
                releases.append(release)
    return sorted(releases, key=lambda r: version_key(r.version), reverse=True)
