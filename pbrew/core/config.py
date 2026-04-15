from pathlib import Path
import tomlkit

DEFAULT_CONFIG: dict = {
    "build": {
        "jobs": "auto",
        "variants": [
            "default", "exif", "fpm", "intl", "mysql", "sqlite",
            "ftp", "soap", "tidy", "iconv", "gettext", "openssl", "opcache",
        ],
        "extra": {},
    },
    "xdebug": {"enabled": False},
    "fpm": {
        "pools_dir": "managed",
        "pool_defaults": {
            "pm": "dynamic",
            "pm_max_children": 5,
            "pm_start_servers": 2,
            "pm_min_spare_servers": 1,
            "pm_max_spare_servers": 3,
        },
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _load_toml(path: Path) -> dict:
    if not path.exists():
        return {}
    return dict(tomlkit.loads(path.read_text()))


def load_config(
    configs_dir: Path,
    family: str,
    named: str | None = None,
) -> dict:
    """Lädt Config mit Cascade: DEFAULT < default.toml < {family}.toml < {named}.toml."""
    import copy
    config = copy.deepcopy(DEFAULT_CONFIG)
    config = _deep_merge(config, _load_toml(configs_dir / "default.toml"))
    config = _deep_merge(config, _load_toml(configs_dir / f"{family}.toml"))
    if named:
        config = _deep_merge(config, _load_toml(configs_dir / f"{named}.toml"))
    return config


def save_config(configs_dir: Path, name: str, data: dict) -> None:
    configs_dir.mkdir(parents=True, exist_ok=True)
    path = configs_dir / f"{name}.toml"
    path.write_text(tomlkit.dumps(data))


def init_default_config(configs_dir: Path) -> None:
    """Schreibt default.toml wenn sie noch nicht existiert."""
    path = configs_dir / "default.toml"
    if path.exists():
        return
    save_config(configs_dir, "default", DEFAULT_CONFIG)
