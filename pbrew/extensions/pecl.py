import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass

PECL_REST = "https://pecl.php.net/rest/r"
_NS = {"p": "http://pear.php.net/dtd/rest.allreleases"}


@dataclass
class PeclRelease:
    package: str
    version: str
    stability: str        # "stable", "beta", "alpha"
    tarball_url: str


def fetch_releases(package: str) -> list[PeclRelease]:
    """Holt alle Releases eines PECL-Pakets von pecl.php.net."""
    url = f"{PECL_REST}/{package.lower()}/allreleases.xml"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            xml_data = resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise RuntimeError(
                f"PECL-Paket '{package}' nicht gefunden. "
                f"Name prüfen: https://pecl.php.net/package/{package}"
            ) from e
        raise RuntimeError(f"PECL-Fehler für '{package}': HTTP {e.code} {e.reason}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Netzwerkfehler beim Abrufen von '{package}': {e.reason}") from e

    root = ET.fromstring(xml_data)
    releases: list[PeclRelease] = []
    for r in root.findall("p:r", _NS):
        version = r.findtext("p:v", namespaces=_NS, default="")
        stability = r.findtext("p:s", namespaces=_NS, default="")
        if version and stability:
            releases.append(PeclRelease(
                package=package,
                version=version,
                stability=stability,
                tarball_url=f"https://pecl.php.net/get/{package.lower()}-{version}.tgz",
            ))
    return releases


_STABILITY_ALIASES = {"latest": "stable", "stable": "stable", "beta": "beta", "alpha": "alpha"}


def fetch_latest_stable(package: str) -> PeclRelease:
    """Gibt das neueste stabile Release eines PECL-Pakets zurück."""
    return fetch_latest_by_stability(package, "stable")


def fetch_latest_by_stability(package: str, stability: str) -> PeclRelease:
    """Gibt das neueste Release eines PECL-Pakets mit der angegebenen Stabilität zurück.

    stability: 'stable' | 'beta' | 'alpha'
    Bei 'beta' werden auch stabile Releases als Kandidaten akzeptiert (stable > beta).
    Bei 'alpha' werden alle Stabilitätsstufen akzeptiert.
    """
    releases = fetch_releases(package)
    accepted = {"stable": {"stable"}, "beta": {"stable", "beta"}, "alpha": {"stable", "beta", "alpha"}}
    candidates = [r for r in releases if r.stability in accepted[stability]]
    if not candidates:
        raise RuntimeError(f"Kein {stability}-Release für {package} gefunden")
    return candidates[0]
