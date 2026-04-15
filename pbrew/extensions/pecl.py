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
    with urllib.request.urlopen(url, timeout=30) as resp:
        xml_data = resp.read()

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


def fetch_latest_stable(package: str) -> PeclRelease:
    """Gibt das neueste stabile Release eines PECL-Pakets zurück."""
    releases = fetch_releases(package)
    stable = [r for r in releases if r.stability == "stable"]
    if not stable:
        raise RuntimeError(f"Kein stabiles Release für {package} gefunden")
    return stable[0]
