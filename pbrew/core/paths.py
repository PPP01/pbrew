import os
from pathlib import Path


def get_prefix() -> Path:
    """Gibt das pbrew-Prefix zurück (PBREW_ROOT env oder ~/.pbrew)."""
    env = os.environ.get("PBREW_ROOT")
    if env:
        return Path(env)
    return Path.home() / ".pbrew"


def family_from_version(version: str) -> str:
    """Leitet die PHP-Family aus einer Versionsangabe ab.

    '8.4.22' -> '8.4'
    '84'     -> '8.4'
    '8.4'    -> '8.4'
    """
    version = version.strip()
    if version.isdigit() and len(version) == 2:
        return f"{version[0]}.{version[1]}"
    parts = version.split(".")
    if len(parts) >= 2 and all(p.isdigit() for p in parts[:2]):
        return f"{parts[0]}.{parts[1]}"
    raise ValueError(f"Ungültige Versionsangabe: {version!r}")


def versions_dir(prefix: Path) -> Path:
    return prefix / "versions"


def version_dir(prefix: Path, version: str) -> Path:
    return versions_dir(prefix) / version


def etc_dir(prefix: Path) -> Path:
    return prefix / "etc"


def cli_ini_dir(prefix: Path, family: str) -> Path:
    return etc_dir(prefix) / "cli" / family


def fpm_ini_dir(prefix: Path, family: str) -> Path:
    return etc_dir(prefix) / "fpm" / family


def confd_dir(prefix: Path, family: str) -> Path:
    return etc_dir(prefix) / "conf.d" / family


def configs_dir(prefix: Path) -> Path:
    return prefix / "configs"


def state_dir(prefix: Path) -> Path:
    return prefix / "state"


def state_file(prefix: Path, family: str) -> Path:
    return state_dir(prefix) / f"{family}.json"


def global_state_file(prefix: Path) -> Path:
    return state_dir(prefix) / "global.json"


def bin_dir(prefix: Path) -> Path:
    return prefix / "bin"


def logs_dir(prefix: Path) -> Path:
    return state_dir(prefix) / "logs"


def build_log(prefix: Path, version: str) -> Path:
    return logs_dir(prefix) / f"{version}-build.log"


def version_bin(prefix: Path, version: str, binary: str) -> Path:
    return version_dir(prefix, version) / "bin" / binary
