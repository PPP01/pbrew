import os
from pathlib import Path

import tomlkit


def _config_home() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    return Path(xdg) if xdg else Path.home() / ".config"


def global_config_file() -> Path:
    return _config_home() / "pbrew" / "config.toml"


def read_configured_prefix() -> "Path | None":
    f = global_config_file()
    if not f.exists():
        return None
    data = tomlkit.parse(f.read_text())
    val = data.get("core", {}).get("prefix")
    return Path(val) if val else None


def write_prefix(prefix: Path) -> None:
    f = global_config_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    doc = tomlkit.document()
    core = tomlkit.table()
    core.add("prefix", str(prefix))
    doc.add("core", core)
    f.write_text(tomlkit.dumps(doc))
