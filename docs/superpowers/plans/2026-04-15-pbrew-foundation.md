# pbrew Foundation & Core — Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eigenständiges Python-Paket `pbrew` das PHP aus dem Quellcode baut, mit TOML-Config, State-Management und Health-Checks. Ergebnis: funktionsfähige Commands `pbrew install 84`, `pbrew list`, `pbrew use`, `pbrew switch`, `pbrew known`, `pbrew clean`, `pbrew log`, `pbrew shell-init`, `pbrew doctor`.

**Architecture:** Monolithisches Python-Paket (`click` + `tomlkit`). Module mit klaren Grenzen: `core/` (Config, State, Paths, Resolver, Builder), `utils/` (Download, Health), `cli/` (je Command eine Datei). TDD durchgängig — erst Test, dann Implementation.

**Tech Stack:** Python 3.11+, click 8.x, tomlkit 0.12+, pytest 8.x. Kein weiterer externer Code.

**Scope:** Dieses Projekt ist ein **neues eigenständiges Repository** (PPP01/pbrew). Nicht Teil von phpbrew. FPM-Management und Extension-Management kommen in separaten Plänen (Plan 2 + Plan 3).

---

## Dateistruktur

```
pbrew/                              ← repo root
├── pyproject.toml
├── pytest.ini
├── pbrew/                          ← Python-Paket
│   ├── __init__.py
│   ├── cli/
│   │   ├── __init__.py             ← click group + Entry Point main()
│   │   ├── install.py              ← pbrew install
│   │   ├── list_.py                ← pbrew list
│   │   ├── use.py                  ← pbrew use / pbrew switch
│   │   ├── known.py                ← pbrew known
│   │   ├── clean.py                ← pbrew clean
│   │   ├── log_.py                 ← pbrew log
│   │   ├── shell_init.py           ← pbrew shell-init
│   │   └── doctor.py               ← pbrew doctor
│   ├── core/
│   │   ├── __init__.py
│   │   ├── paths.py                ← PREFIX-basierte Pfadberechnungen
│   │   ├── config.py               ← TOML Config laden/mergen/schreiben
│   │   ├── state.py                ← JSON State lesen/schreiben
│   │   ├── resolver.py             ← PHP-Versionen via php.net API abfragen
│   │   └── builder.py              ← configure/make/install Wrapper
│   └── utils/
│       ├── __init__.py
│       ├── download.py             ← HTTP Download mit Fortschrittsbalken + SHA256
│       └── health.py               ← Post-Build Health-Checks
└── tests/
    ├── conftest.py
    ├── test_paths.py
    ├── test_config.py
    ├── test_state.py
    ├── test_resolver.py
    ├── test_builder.py
    ├── test_download.py
    └── test_health.py
```

---

## Task 1: Projekt-Setup

**Files:**
- Create: `pyproject.toml`
- Create: `pytest.ini`
- Create: `pbrew/__init__.py`
- Create: `pbrew/cli/__init__.py`
- Create: `pbrew/core/__init__.py`
- Create: `pbrew/utils/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Schritt 1: Git-Repository anlegen**

```bash
mkdir pbrew && cd pbrew
git init
git remote add origin git@github.com:PPP01/pbrew.git
echo "__pycache__/" > .gitignore
echo "*.egg-info/" >> .gitignore
echo "dist/" >> .gitignore
echo ".pytest_cache/" >> .gitignore
echo "*.pyc" >> .gitignore
```

- [ ] **Schritt 2: `pyproject.toml` anlegen**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "pbrew"
version = "0.1.0"
description = "Python-based PHP version manager"
requires-python = ">=3.11"
dependencies = [
    "click>=8.1",
    "tomlkit>=0.12",
]

[project.scripts]
pbrew = "pbrew.cli:main"

[tool.setuptools.packages.find]
where = ["."]
include = ["pbrew*"]
```

- [ ] **Schritt 3: `pytest.ini` anlegen**

```ini
[pytest]
testpaths = tests
```

- [ ] **Schritt 4: Paket-Struktur anlegen**

```bash
mkdir -p pbrew/cli pbrew/core pbrew/utils tests
touch pbrew/__init__.py pbrew/cli/__init__.py pbrew/core/__init__.py pbrew/utils/__init__.py
touch tests/conftest.py
```

- [ ] **Schritt 5: Virtuelle Umgebung + Dependencies installieren**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]" 2>/dev/null || pip install -e .
pip install pytest click tomlkit
```

- [ ] **Schritt 6: Placeholder Entry Point — damit `pbrew` aufrufbar ist**

Inhalt `pbrew/cli/__init__.py`:

```python
import click

@click.group()
def main():
    """pbrew — PHP Version Manager"""

```

- [ ] **Schritt 7: Smoke-Test**

```bash
pbrew --help
```

Erwartete Ausgabe:
```
Usage: pbrew [OPTIONS] COMMAND [ARGS]...

  pbrew — PHP Version Manager

Options:
  --help  Show this message and exit.
```

- [ ] **Schritt 8: Initial Commit**

```bash
git add pyproject.toml pytest.ini pbrew/ tests/ .gitignore
git commit -m "Initialisiere pbrew-Projektstruktur"
```

---

## Task 2: Paths-Modul

**Files:**
- Create: `pbrew/core/paths.py`
- Create: `tests/test_paths.py`

`★ Insight ─────────────────────────────────────`
Alle Pfadberechnungen in einem Modul zentralisieren verhindert, dass dieselbe Logik (z.B. `family_from_version`) in mehreren Dateien dupliziert wird. Alle anderen Module importieren ausschließlich von hier — nie `prefix / "etc" / family` direkt hinschreiben.
`─────────────────────────────────────────────────`

- [ ] **Schritt 1: Tests schreiben**

Datei `tests/test_paths.py`:

```python
import pytest
from pathlib import Path
from pbrew.core.paths import (
    family_from_version,
    version_dir,
    cli_ini_dir,
    confd_dir,
    state_file,
    bin_dir,
    build_log,
    version_bin,
)

PREFIX = Path("/opt/pbrew")


def test_family_from_version_full():
    assert family_from_version("8.4.22") == "8.4"


def test_family_from_version_short_digits():
    assert family_from_version("84") == "8.4"


def test_family_from_version_two_part():
    assert family_from_version("8.4") == "8.4"


def test_family_from_version_invalid():
    with pytest.raises(ValueError):
        family_from_version("abc")


def test_version_dir():
    assert version_dir(PREFIX, "8.4.22") == Path("/opt/pbrew/versions/8.4.22")


def test_cli_ini_dir():
    assert cli_ini_dir(PREFIX, "8.4") == Path("/opt/pbrew/etc/cli/8.4")


def test_confd_dir():
    assert confd_dir(PREFIX, "8.4") == Path("/opt/pbrew/etc/conf.d/8.4")


def test_state_file():
    assert state_file(PREFIX, "8.4") == Path("/opt/pbrew/state/8.4.json")


def test_bin_dir():
    assert bin_dir(PREFIX) == Path("/opt/pbrew/bin")


def test_build_log():
    assert build_log(PREFIX, "8.4.22") == Path("/opt/pbrew/state/logs/8.4.22-build.log")


def test_version_bin():
    assert version_bin(PREFIX, "8.4.22", "php") == Path("/opt/pbrew/versions/8.4.22/bin/php")
```

- [ ] **Schritt 2: Tests ausführen — müssen fehlschlagen**

```bash
pytest tests/test_paths.py -v
```

Erwartete Ausgabe: `ImportError` (Modul existiert noch nicht)

- [ ] **Schritt 3: Implementation**

Datei `pbrew/core/paths.py`:

```python
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
```

- [ ] **Schritt 4: Tests ausführen — müssen grün sein**

```bash
pytest tests/test_paths.py -v
```

Erwartete Ausgabe: Alle 10 Tests PASSED

- [ ] **Schritt 5: Commit**

```bash
git add pbrew/core/paths.py tests/test_paths.py
git commit -m "Füge paths-Modul mit Pfadberechnungen hinzu"
```

---

## Task 3: Config-Modul (TOML)

**Files:**
- Create: `pbrew/core/config.py`
- Create: `tests/test_config.py`

- [ ] **Schritt 1: Tests schreiben**

Datei `tests/test_config.py`:

```python
import pytest
import tomlkit
from pathlib import Path
from pbrew.core.config import load_config, save_config, init_default_config, DEFAULT_CONFIG


def test_load_config_returns_defaults_when_no_files(tmp_path):
    cfg = load_config(tmp_path / "configs", "8.4")
    assert cfg["build"]["jobs"] == "auto"
    assert "fpm" in cfg["build"]["variants"]
    assert cfg["xdebug"]["enabled"] is False


def test_load_config_merges_family_override(tmp_path):
    configs = tmp_path / "configs"
    configs.mkdir()
    family_conf = {"build": {"extra": {"with-config-file-scan-dir": "/custom/scan"}}}
    (configs / "8.4.toml").write_text(tomlkit.dumps(family_conf))

    cfg = load_config(configs, "8.4")
    assert cfg["build"]["extra"]["with-config-file-scan-dir"] == "/custom/scan"
    # Default variants should still be present
    assert "fpm" in cfg["build"]["variants"]


def test_load_config_named_overrides_family(tmp_path):
    configs = tmp_path / "configs"
    configs.mkdir()
    (configs / "8.4.toml").write_text(tomlkit.dumps({"build": {"jobs": 4}}))
    (configs / "production.toml").write_text(tomlkit.dumps({"build": {"jobs": 2}}))

    cfg = load_config(configs, "8.4", named="production")
    assert cfg["build"]["jobs"] == 2


def test_load_config_named_missing_falls_back_to_family(tmp_path):
    configs = tmp_path / "configs"
    configs.mkdir()
    (configs / "8.4.toml").write_text(tomlkit.dumps({"build": {"jobs": 6}}))

    cfg = load_config(configs, "8.4", named="nonexistent")
    assert cfg["build"]["jobs"] == 6


def test_save_config_writes_toml(tmp_path):
    configs = tmp_path / "configs"
    save_config(configs, "test", {"build": {"jobs": 3}})
    loaded = tomlkit.loads((configs / "test.toml").read_text())
    assert loaded["build"]["jobs"] == 3


def test_init_default_config_creates_file(tmp_path):
    configs = tmp_path / "configs"
    init_default_config(configs)
    assert (configs / "default.toml").exists()


def test_init_default_config_does_not_overwrite(tmp_path):
    configs = tmp_path / "configs"
    configs.mkdir()
    (configs / "default.toml").write_text(tomlkit.dumps({"build": {"jobs": 99}}))
    init_default_config(configs)
    loaded = tomlkit.loads((configs / "default.toml").read_text())
    assert loaded["build"]["jobs"] == 99
```

- [ ] **Schritt 2: Tests ausführen — müssen fehlschlagen**

```bash
pytest tests/test_config.py -v
```

Erwartete Ausgabe: `ImportError`

- [ ] **Schritt 3: Implementation**

Datei `pbrew/core/config.py`:

```python
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
```

- [ ] **Schritt 4: Tests ausführen — müssen grün sein**

```bash
pytest tests/test_config.py -v
```

Erwartete Ausgabe: Alle 7 Tests PASSED

- [ ] **Schritt 5: Commit**

```bash
git add pbrew/core/config.py tests/test_config.py
git commit -m "Füge config-Modul mit TOML-Cascade hinzu"
```

---

## Task 4: State-Modul (JSON)

**Files:**
- Create: `pbrew/core/state.py`
- Create: `tests/test_state.py`

`★ Insight ─────────────────────────────────────`
State-Dateien sind intern und werden nie manuell bearbeitet → JSON statt TOML ist völlig ausreichend und kommt ohne externe Bibliothek aus. Für user-editierte Config (default.toml, 8.4.toml) bleibt TOML die richtige Wahl.
`─────────────────────────────────────────────────`

- [ ] **Schritt 1: Tests schreiben**

Datei `tests/test_state.py`:

```python
from pathlib import Path
from pbrew.core.state import (
    get_family_state,
    set_active_version,
    set_build_duration,
    add_extension,
    get_global_state,
    set_global_default,
)


def test_get_family_state_returns_empty_for_missing(tmp_path):
    assert get_family_state(tmp_path / "8.4.json") == {}


def test_set_active_version_creates_file(tmp_path):
    sf = tmp_path / "8.4.json"
    set_active_version(sf, "8.4.22")
    state = get_family_state(sf)
    assert state["active"] == "8.4.22"
    assert "8.4.22" in state["installed"]


def test_set_active_version_tracks_previous(tmp_path):
    sf = tmp_path / "8.4.json"
    set_active_version(sf, "8.4.20")
    set_active_version(sf, "8.4.22")
    state = get_family_state(sf)
    assert state["active"] == "8.4.22"
    assert state["previous"] == "8.4.20"


def test_set_active_version_stores_config_name(tmp_path):
    sf = tmp_path / "8.4.json"
    set_active_version(sf, "8.4.22", config="production")
    assert get_family_state(sf)["config"] == "production"


def test_set_build_duration(tmp_path):
    sf = tmp_path / "8.4.json"
    set_active_version(sf, "8.4.22")
    set_build_duration(sf, "8.4.22", 134.7)
    state = get_family_state(sf)
    assert state["installed"]["8.4.22"]["build_duration_seconds"] == 135


def test_add_extension(tmp_path):
    sf = tmp_path / "8.4.json"
    add_extension(sf, "apcu")
    add_extension(sf, "redis")
    add_extension(sf, "apcu")  # duplicate
    state = get_family_state(sf)
    assert state["extensions"] == ["apcu", "redis"]


def test_set_global_default(tmp_path):
    gsf = tmp_path / "global.json"
    set_global_default(gsf, "8.4")
    assert get_global_state(gsf)["default_family"] == "8.4"
```

- [ ] **Schritt 2: Tests ausführen — müssen fehlschlagen**

```bash
pytest tests/test_state.py -v
```

Erwartete Ausgabe: `ImportError`

- [ ] **Schritt 3: Implementation**

Datei `pbrew/core/state.py`:

```python
import json
from datetime import datetime, timezone
from pathlib import Path


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


def get_family_state(state_file: Path) -> dict:
    return _load(state_file)


def set_active_version(
    state_file: Path,
    version: str,
    config: str = "default",
) -> None:
    state = _load(state_file)
    if "active" in state and state["active"] != version:
        state["previous"] = state["active"]
    state["active"] = version
    state["config"] = config
    state.setdefault("installed", {})[version] = {
        "installed_at": datetime.now(timezone.utc).isoformat(),
    }
    _save(state_file, state)


def set_build_duration(state_file: Path, version: str, seconds: float) -> None:
    state = _load(state_file)
    state.setdefault("installed", {}).setdefault(version, {})
    state["installed"][version]["build_duration_seconds"] = round(seconds)
    _save(state_file, state)


def add_extension(state_file: Path, extension: str) -> None:
    state = _load(state_file)
    extensions: list = state.get("extensions", [])
    if extension not in extensions:
        extensions.append(extension)
    state["extensions"] = extensions
    _save(state_file, state)


def get_global_state(global_state_file: Path) -> dict:
    return _load(global_state_file)


def set_global_default(global_state_file: Path, family: str) -> None:
    state = _load(global_state_file)
    state["default_family"] = family
    _save(global_state_file, state)
```

- [ ] **Schritt 4: Tests ausführen — müssen grün sein**

```bash
pytest tests/test_state.py -v
```

Erwartete Ausgabe: Alle 7 Tests PASSED

- [ ] **Schritt 5: Commit**

```bash
git add pbrew/core/state.py tests/test_state.py
git commit -m "Füge state-Modul mit JSON-Persistenz hinzu"
```

---

## Task 5: Resolver-Modul (PHP.net API)

**Files:**
- Create: `pbrew/core/resolver.py`
- Create: `tests/test_resolver.py`

- [ ] **Schritt 1: Tests schreiben**

Datei `tests/test_resolver.py`:

```python
import json
from io import BytesIO
from unittest.mock import patch, MagicMock
from pbrew.core.resolver import fetch_latest, fetch_known, PhpRelease


MOCK_SINGLE = {
    "8.4.22": {
        "announcement": {},
        "tags": [],
        "date": "14 Apr 2026",
        "source": [
            {
                "filename": "php-8.4.22.tar.gz",
                "name": "PHP 8.4.22 (tar.gz)",
                "sha256": "aaa",
                "md5": "bbb",
            },
            {
                "filename": "php-8.4.22.tar.bz2",
                "name": "PHP 8.4.22 (tar.bz2)",
                "sha256": "ccc111",
                "md5": "ddd",
            },
        ],
    }
}

MOCK_ALL = {
    "8.4.22": MOCK_SINGLE["8.4.22"],
    "8.4.20": {
        "source": [
            {"filename": "php-8.4.20.tar.bz2", "sha256": "eee", "md5": "fff"}
        ]
    },
    "8.3.10": {
        "source": [
            {"filename": "php-8.3.10.tar.bz2", "sha256": "ggg", "md5": "hhh"}
        ]
    },
}


def _mock_urlopen(data: dict):
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(data).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def test_fetch_latest_returns_release():
    with patch("pbrew.core.resolver.urllib.request.urlopen", return_value=_mock_urlopen(MOCK_SINGLE)):
        release = fetch_latest("8.4")
    assert release.version == "8.4.22"
    assert release.family == "8.4"
    assert release.sha256 == "ccc111"
    assert "php-8.4.22.tar.bz2" in release.tarball_url


def test_fetch_latest_selects_bz2_over_gz():
    with patch("pbrew.core.resolver.urllib.request.urlopen", return_value=_mock_urlopen(MOCK_SINGLE)):
        release = fetch_latest("8.4")
    assert release.tarball_url.endswith(".tar.bz2")


def test_fetch_known_returns_all_releases():
    with patch("pbrew.core.resolver.urllib.request.urlopen", return_value=_mock_urlopen(MOCK_ALL)):
        releases = fetch_known(8)
    assert len(releases) == 3


def test_fetch_known_sorted_descending():
    with patch("pbrew.core.resolver.urllib.request.urlopen", return_value=_mock_urlopen(MOCK_ALL)):
        releases = fetch_known(8)
    versions = [r.version for r in releases]
    assert versions == sorted(versions, reverse=True)
```

- [ ] **Schritt 2: Tests ausführen — müssen fehlschlagen**

```bash
pytest tests/test_resolver.py -v
```

Erwartete Ausgabe: `ImportError`

- [ ] **Schritt 3: Implementation**

Datei `pbrew/core/resolver.py`:

```python
import json
import urllib.request
from dataclasses import dataclass

PHP_RELEASES_URL = "https://www.php.net/releases/index.php"


@dataclass
class PhpRelease:
    version: str        # "8.4.22"
    family: str         # "8.4"
    tarball_url: str    # "https://www.php.net/distributions/php-8.4.22.tar.bz2"
    sha256: str


def _fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read())


def _parse_release(version: str, release_data: dict) -> PhpRelease | None:
    parts = version.split(".")
    if len(parts) < 3:
        return None
    sources = release_data.get("source", [])
    bz2 = next((s for s in sources if s.get("filename", "").endswith(".tar.bz2")), None)
    if not bz2:
        return None
    return PhpRelease(
        version=version,
        family=f"{parts[0]}.{parts[1]}",
        tarball_url=f"https://www.php.net/distributions/{bz2['filename']}",
        sha256=bz2.get("sha256", ""),
    )


def fetch_latest(family: str) -> PhpRelease:
    """Gibt die neueste Version einer PHP-Family zurück (z.B. '8.4')."""
    url = f"{PHP_RELEASES_URL}?json=1&version={family}&max=1"
    data = _fetch_json(url)
    version = next(iter(data))
    release = _parse_release(version, data[version])
    if release is None:
        raise RuntimeError(f"Keine .tar.bz2 Quelle für PHP {version} gefunden")
    return release


def fetch_known(major: int = 8) -> list[PhpRelease]:
    """Gibt alle bekannten Releases für eine Major-Version zurück."""
    url = f"{PHP_RELEASES_URL}?json=1&version={major}"
    data = _fetch_json(url)
    releases = []
    for version, release_data in data.items():
        release = _parse_release(version, release_data)
        if release:
            releases.append(release)
    return sorted(releases, key=lambda r: r.version, reverse=True)
```

- [ ] **Schritt 4: Tests ausführen — müssen grün sein**

```bash
pytest tests/test_resolver.py -v
```

Erwartete Ausgabe: Alle 4 Tests PASSED

- [ ] **Schritt 5: Commit**

```bash
git add pbrew/core/resolver.py tests/test_resolver.py
git commit -m "Füge resolver-Modul für PHP.net API hinzu"
```

---

## Task 6: Download-Utility

**Files:**
- Create: `pbrew/utils/download.py`
- Create: `tests/test_download.py`

- [ ] **Schritt 1: Tests schreiben**

Datei `tests/test_download.py`:

```python
import hashlib
from io import BytesIO
from unittest.mock import patch, MagicMock
import pytest
from pbrew.utils.download import download


CONTENT = b"fake tarball content " * 100


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _mock_response(content: bytes):
    mock_resp = MagicMock()
    mock_resp.headers.get.return_value = str(len(content))
    mock_resp.read.side_effect = [content[:1024], content[1024:], b""]
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def test_download_writes_file(tmp_path):
    dest = tmp_path / "php-8.4.22.tar.bz2"
    with patch("pbrew.utils.download.urllib.request.urlopen", return_value=_mock_response(CONTENT)):
        download("https://example.com/php.tar.bz2", dest)
    assert dest.exists()
    assert dest.read_bytes() == CONTENT


def test_download_verifies_sha256(tmp_path):
    dest = tmp_path / "php.tar.bz2"
    correct_sha = _sha256(CONTENT)
    with patch("pbrew.utils.download.urllib.request.urlopen", return_value=_mock_response(CONTENT)):
        download("https://example.com/php.tar.bz2", dest, expected_sha256=correct_sha)
    assert dest.exists()


def test_download_raises_on_wrong_sha256(tmp_path):
    dest = tmp_path / "php.tar.bz2"
    with patch("pbrew.utils.download.urllib.request.urlopen", return_value=_mock_response(CONTENT)):
        with pytest.raises(ValueError, match="SHA-256"):
            download("https://example.com/php.tar.bz2", dest, expected_sha256="wrong")
    assert not dest.exists()


def test_download_creates_parent_dirs(tmp_path):
    dest = tmp_path / "sub" / "dir" / "file.tar.bz2"
    with patch("pbrew.utils.download.urllib.request.urlopen", return_value=_mock_response(CONTENT)):
        download("https://example.com/php.tar.bz2", dest)
    assert dest.exists()
```

- [ ] **Schritt 2: Tests ausführen — müssen fehlschlagen**

```bash
pytest tests/test_download.py -v
```

- [ ] **Schritt 3: Implementation**

Datei `pbrew/utils/download.py`:

```python
import hashlib
import sys
import urllib.request
from pathlib import Path

_CHUNK = 65536  # 64 KB


def download(url: str, dest: Path, expected_sha256: str = "") -> None:
    """Lädt url nach dest herunter. Prüft SHA-256 wenn angegeben."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    sha256 = hashlib.sha256()

    with urllib.request.urlopen(url, timeout=60) as response:
        total = int(response.headers.get("Content-Length", 0))
        downloaded = 0

        with open(dest, "wb") as f:
            while True:
                chunk = response.read(_CHUNK)
                if not chunk:
                    break
                f.write(chunk)
                sha256.update(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded * 100 // total
                    mb = downloaded / 1_048_576
                    total_mb = total / 1_048_576
                    print(f"\r  {mb:.1f} / {total_mb:.1f} MB ({pct}%)", end="", flush=True)

    print()

    if expected_sha256 and sha256.hexdigest() != expected_sha256:
        dest.unlink(missing_ok=True)
        raise ValueError(
            f"SHA-256 Prüfung fehlgeschlagen: erwartet {expected_sha256}, erhalten {sha256.hexdigest()}"
        )
```

- [ ] **Schritt 4: Tests ausführen — müssen grün sein**

```bash
pytest tests/test_download.py -v
```

Erwartete Ausgabe: Alle 4 Tests PASSED

- [ ] **Schritt 5: Commit**

```bash
git add pbrew/utils/download.py tests/test_download.py
git commit -m "Füge download-Utility mit SHA-256-Prüfung hinzu"
```

---

## Task 7: Builder-Modul

**Files:**
- Create: `pbrew/core/builder.py`
- Create: `tests/test_builder.py`

`★ Insight ─────────────────────────────────────`
Der Builder testet nur die Argument-Generierung (pure function, kein I/O) und die Subprocess-Aufrufe mit gemockten Prozessen. Die tatsächliche Kompilierung kann nicht sinnvoll unit-getestet werden — das ist Aufgabe von Integrationstests auf echter Hardware.
`─────────────────────────────────────────────────`

- [ ] **Schritt 1: Tests schreiben**

Datei `tests/test_builder.py`:

```python
from pathlib import Path
from unittest.mock import patch, MagicMock
import subprocess
import pytest
from pbrew.core.builder import build_configure_args, get_jobs


PREFIX = Path("/opt/pbrew")


def test_configure_args_contains_prefix():
    args = build_configure_args(PREFIX, "8.4.22", "8.4", {})
    assert any("--prefix=" in a for a in args)
    assert any("versions/8.4.22" in a for a in args)


def test_configure_args_contains_cli_and_fpm():
    args = build_configure_args(PREFIX, "8.4.22", "8.4", {})
    assert "--enable-cli" in args
    assert "--enable-fpm" in args


def test_configure_args_sets_config_file_path():
    args = build_configure_args(PREFIX, "8.4.22", "8.4", {})
    assert any("--with-config-file-path=" in a and "etc/cli/8.4" in a for a in args)


def test_configure_args_sets_scan_dir():
    args = build_configure_args(PREFIX, "8.4.22", "8.4", {})
    assert any("--with-config-file-scan-dir=" in a and "conf.d/8.4" in a for a in args)


def test_configure_args_extra_option_overrides_scan_dir():
    config = {"build": {"extra": {"with-config-file-scan-dir": "/custom/scan"}}}
    args = build_configure_args(PREFIX, "8.4.22", "8.4", config)
    scan_args = [a for a in args if "--with-config-file-scan-dir" in a]
    assert len(scan_args) == 1
    assert scan_args[0] == "--with-config-file-scan-dir=/custom/scan"


def test_configure_args_bool_extra_option():
    config = {"build": {"extra": {"with-password-argon2": True}}}
    args = build_configure_args(PREFIX, "8.4.22", "8.4", config)
    assert "--with-password-argon2" in args


def test_configure_args_false_extra_option_omitted():
    config = {"build": {"extra": {"enable-gd": False}}}
    args = build_configure_args(PREFIX, "8.4.22", "8.4", config)
    assert "--enable-gd" not in args


def test_get_jobs_auto_returns_int():
    jobs = get_jobs({"build": {"jobs": "auto"}})
    assert isinstance(jobs, int)
    assert jobs >= 1


def test_get_jobs_fixed():
    assert get_jobs({"build": {"jobs": 4}}) == 4


def test_get_jobs_override():
    assert get_jobs({"build": {"jobs": "auto"}}, override=2) == 2
```

- [ ] **Schritt 2: Tests ausführen — müssen fehlschlagen**

```bash
pytest tests/test_builder.py -v
```

- [ ] **Schritt 3: Implementation**

Datei `pbrew/core/builder.py`:

```python
import os
import subprocess
from pathlib import Path
from typing import IO

from pbrew.core.paths import version_dir, cli_ini_dir, confd_dir

# Variants die --enable-X statt --with-X verwenden
_ENABLE_VARIANTS = frozenset({
    "cli", "fpm", "opcache", "exif", "intl", "gettext",
    "ftp", "soap", "tidy", "iconv",
})


def build_configure_args(
    prefix: Path,
    version: str,
    family: str,
    config: dict,
) -> list[str]:
    """Baut die ./configure Argumentliste aus der Config."""
    vdir = version_dir(prefix, version)
    cli_ini = cli_ini_dir(prefix, family)
    scan_dir = confd_dir(prefix, family)

    # Basis-Argumente (können durch build.extra überschrieben werden)
    base = {
        "prefix": str(vdir),
        "with-config-file-path": str(cli_ini),
        "with-config-file-scan-dir": str(scan_dir),
    }

    extra = config.get("build", {}).get("extra", {})
    # Explizite extra-Optionen überschreiben unsere Defaults
    for key in ("with-config-file-path", "with-config-file-scan-dir"):
        if key in extra:
            base[key] = extra[key]

    args = [
        f"--prefix={base['prefix']}",
        "--enable-cli",
        "--enable-fpm",
        "--with-fpm-systemd",
        f"--with-config-file-path={base['with-config-file-path']}",
        f"--with-config-file-scan-dir={base['with-config-file-scan-dir']}",
    ]

    # Variants
    variants = config.get("build", {}).get("variants", [])
    for variant in variants:
        if variant in ("default", "fpm", "cli"):
            continue
        flag = "--enable-" if variant in _ENABLE_VARIANTS else "--with-"
        args.append(f"{flag}{variant}")

    # Extra-Optionen (außer bereits verarbeitete)
    skip = {"with-config-file-path", "with-config-file-scan-dir"}
    for key, value in extra.items():
        if key in skip:
            continue
        if value is True:
            args.append(f"--{key}")
        elif value is not False and value is not None:
            args.append(f"--{key}={value}")

    return args


def get_jobs(config: dict, override: int | None = None) -> int:
    if override is not None:
        return override
    jobs = config.get("build", {}).get("jobs", "auto")
    if jobs == "auto":
        return os.cpu_count() or 1
    return int(jobs)


def run_configure(src_dir: Path, args: list[str], log_file: IO[str]) -> None:
    _run([str(src_dir / "configure")] + args, cwd=src_dir, log_file=log_file)


def run_make(src_dir: Path, jobs: int, log_file: IO[str]) -> None:
    _run(["make", f"-j{jobs}"], cwd=src_dir, log_file=log_file)


def run_make_install(src_dir: Path, log_file: IO[str]) -> None:
    _run(["make", "install"], cwd=src_dir, log_file=log_file)


def _run(cmd: list[str], cwd: Path, log_file: IO[str]) -> None:
    process = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    for line in process.stdout:
        log_file.write(line)
        log_file.flush()
    process.wait()
    if process.returncode != 0:
        raise subprocess.CalledProcessError(process.returncode, cmd)
```

- [ ] **Schritt 4: Tests ausführen — müssen grün sein**

```bash
pytest tests/test_builder.py -v
```

Erwartete Ausgabe: Alle 10 Tests PASSED

- [ ] **Schritt 5: Commit**

```bash
git add pbrew/core/builder.py tests/test_builder.py
git commit -m "Füge builder-Modul für configure/make/install hinzu"
```

---

## Task 8: Health-Check-Modul

**Files:**
- Create: `pbrew/utils/health.py`
- Create: `tests/test_health.py`

> **Hinweis – scan-dir-Verifikation:** Der scan-dir-Pfad wird beim Build fest ins Binary kompiliert (`--with-config-file-scan-dir`). `check_scan_dir` prüft via `php --ini`, ob der kompilierte Pfad mit dem erwarteten Pfad übereinstimmt – damit wird sichergestellt, dass keine falschen/gequoteten Pfade ins Binary gelangen.

- [ ] **Schritt 0: Test für scan-dir-Verifikation schreiben** (Ergänzung zu `test_health.py`)

```python
def test_check_scan_dir_matches_expected():
    expected = Path("/opt/pbrew/etc/conf.d/8.4")
    ini_output = (
        "Configuration File (php.ini) Path: /opt/pbrew/etc/cli/8.4\n"
        "Loaded Configuration File: /opt/pbrew/etc/cli/8.4/php.ini\n"
        "Scan for additional .ini files in: /opt/pbrew/etc/conf.d/8.4\n"
        "Additional .ini files parsed: (none)\n"
    )
    with patch("pbrew.utils.health.subprocess.run",
               return_value=_mock_run(0, ini_output)):
        result = check_scan_dir(PHP_BIN, expected)
    assert result.ok is True


def test_check_scan_dir_detects_mismatch():
    expected = Path("/opt/pbrew/etc/conf.d/8.4")
    ini_output = (
        'Scan for additional .ini files in: "/opt/pbrew/etc/conf.d/8.4"\n'
    )
    with patch("pbrew.utils.health.subprocess.run",
               return_value=_mock_run(0, ini_output)):
        result = check_scan_dir(PHP_BIN, expected)
    # Anführungszeichen im Pfad → Mismatch → Fehler erkannt
    assert result.ok is False
    assert "Anführungszeichen" in result.message or "quote" in result.message.lower()


def test_check_scan_dir_none_reported():
    expected = Path("/opt/pbrew/etc/conf.d/8.4")
    ini_output = "Scan for additional .ini files in: (none)\n"
    with patch("pbrew.utils.health.subprocess.run",
               return_value=_mock_run(0, ini_output)):
        result = check_scan_dir(PHP_BIN, expected)
    assert result.ok is False
    assert "(none)" in result.message
```

Und die zugehörige Funktion in `health.py`:

```python
def check_scan_dir(php_bin: Path, expected: Path) -> CheckResult:
    """Prüft ob der kompilierte scan-dir mit dem erwarteten Pfad übereinstimmt.

    Fängt den häufigen Fehler ab, dass Anführungszeichen mit ins Binary
    kompiliert werden (z.B. '"/opt/pbrew/etc/conf.d/8.4"' statt
    '/opt/pbrew/etc/conf.d/8.4').
    """
    try:
        result = subprocess.run(
            [str(php_bin), "--ini"],
            capture_output=True, text=True, timeout=10,
        )
        for line in result.stdout.splitlines():
            if "Scan for additional" in line:
                parts = line.split(":", 1)
                if len(parts) < 2:
                    continue
                raw = parts[1].strip()
                if raw == "(none)":
                    return CheckResult(
                        "scan-dir",
                        False,
                        f"PHP meldet scan-dir als (none), erwartet: {expected}",
                    )
                # Anführungszeichen erkennen — das ist der bekannte Bug
                if raw.startswith('"') or raw.startswith("'"):
                    return CheckResult(
                        "scan-dir",
                        False,
                        f"scan-dir enthält Anführungszeichen im Pfad: {raw!r} "
                        f"(erwartet: {expected})",
                    )
                actual = Path(raw)
                ok = actual == expected
                msg = "" if ok else f"erwartet {expected}, Binary hat {actual}"
                return CheckResult("scan-dir", ok, msg)
        return CheckResult("scan-dir", False, "scan-dir-Zeile nicht in php --ini gefunden")
    except Exception as exc:
        return CheckResult("scan-dir", False, str(exc))
```

`check_scan_dir` in `run_basic_checks()` aufrufen:

```python
# Nach check_php_version(php_bin):
results.append(check_scan_dir(php_bin, confd_dir(prefix, family)))
```

- [ ] **Schritt 1: Tests schreiben**

Datei `tests/test_health.py`:

```python
from pathlib import Path
from unittest.mock import patch, MagicMock
from pbrew.utils.health import (
    check_php_version,
    check_extensions_loaded,
    check_fpm_config,
    CheckResult,
)


def _mock_run(returncode: int, stdout: str = "", stderr: str = ""):
    result = MagicMock()
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = stderr
    return result


PHP_BIN = Path("/opt/pbrew/versions/8.4.22/bin/php")
FPM_BIN = Path("/opt/pbrew/versions/8.4.22/sbin/php-fpm")


def test_check_php_version_ok():
    with patch("pbrew.utils.health.subprocess.run",
               return_value=_mock_run(0, "PHP 8.4.22 (cli)\n")):
        result = check_php_version(PHP_BIN)
    assert result.ok is True
    assert "PHP 8.4.22" in result.message


def test_check_php_version_fail():
    with patch("pbrew.utils.health.subprocess.run",
               return_value=_mock_run(1, stderr="command not found")):
        result = check_php_version(PHP_BIN)
    assert result.ok is False


def test_check_extensions_loaded_all_present():
    output = "[PHP Modules]\napcu\nopcache\nintl\n"
    with patch("pbrew.utils.health.subprocess.run",
               return_value=_mock_run(0, output)):
        results = check_extensions_loaded(PHP_BIN, ["apcu", "opcache", "intl"])
    assert all(r.ok for r in results)


def test_check_extensions_loaded_missing():
    output = "[PHP Modules]\napcu\n"
    with patch("pbrew.utils.health.subprocess.run",
               return_value=_mock_run(0, output)):
        results = check_extensions_loaded(PHP_BIN, ["apcu", "redis"])
    ok_map = {r.name: r.ok for r in results}
    assert ok_map["ext:apcu"] is True
    assert ok_map["ext:redis"] is False


def test_check_fpm_config_ok():
    with patch("pbrew.utils.health.subprocess.run",
               return_value=_mock_run(0)):
        result = check_fpm_config(
            FPM_BIN,
            Path("/opt/pbrew/etc/fpm/8.4/php.ini"),
            Path("/opt/pbrew/etc/fpm/8.4/php-fpm.conf"),
        )
    assert result.ok is True


def test_check_fpm_config_fail():
    with patch("pbrew.utils.health.subprocess.run",
               return_value=_mock_run(1, stderr="syntax error")):
        result = check_fpm_config(
            FPM_BIN,
            Path("/opt/pbrew/etc/fpm/8.4/php.ini"),
            Path("/opt/pbrew/etc/fpm/8.4/php-fpm.conf"),
        )
    assert result.ok is False
    assert "syntax error" in result.message
```

- [ ] **Schritt 2: Tests ausführen — müssen fehlschlagen**

```bash
pytest tests/test_health.py -v
```

- [ ] **Schritt 3: Implementation**

Datei `pbrew/utils/health.py`:

```python
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CheckResult:
    name: str
    ok: bool
    message: str = ""


def check_php_version(php_bin: Path) -> CheckResult:
    try:
        result = subprocess.run(
            [str(php_bin), "-v"],
            capture_output=True, text=True, timeout=10,
        )
        ok = result.returncode == 0 and "PHP" in result.stdout
        msg = result.stdout.splitlines()[0] if ok else result.stderr.strip()
        return CheckResult("php -v", ok, msg)
    except Exception as exc:
        return CheckResult("php -v", False, str(exc))


def check_extensions_loaded(php_bin: Path, expected: list[str]) -> list[CheckResult]:
    try:
        result = subprocess.run(
            [str(php_bin), "-m"],
            capture_output=True, text=True, timeout=10,
        )
        loaded = {line.strip().lower() for line in result.stdout.splitlines()}
        return [
            CheckResult(
                f"ext:{ext}",
                ext.lower() in loaded,
                "" if ext.lower() in loaded else f"{ext} nicht geladen",
            )
            for ext in expected
        ]
    except Exception as exc:
        return [CheckResult("php -m", False, str(exc))]


def check_fpm_config(fpm_bin: Path, ini: Path, fpm_conf: Path) -> CheckResult:
    try:
        result = subprocess.run(
            [str(fpm_bin), f"--php-ini={ini}", f"--fpm-config={fpm_conf}", "-t"],
            capture_output=True, text=True, timeout=10,
        )
        ok = result.returncode == 0
        return CheckResult("php-fpm -t", ok, result.stderr.strip())
    except Exception as exc:
        return CheckResult("php-fpm -t", False, str(exc))


def run_basic_checks(prefix: "Path", version: str, family: str, config: dict) -> list[CheckResult]:
    """Führt alle Health-Checks nach einem Build aus."""
    from pbrew.core.paths import version_bin, fpm_ini_dir

    php_bin = version_bin(prefix, version, "php")
    results = [check_php_version(php_bin)]

    # Bundled Extensions aus Variants
    _bundled_map = {
        "intl": "intl", "opcache": "Zend OPcache",
        "exif": "exif", "gd": "gd",
    }
    variants = config.get("build", {}).get("variants", [])
    expected = [_bundled_map[v] for v in variants if v in _bundled_map]
    if expected:
        results.extend(check_extensions_loaded(php_bin, expected))

    # Feature-spezifische Checks
    extra = config.get("build", {}).get("extra", {})
    if extra.get("with-password-argon2"):
        results.append(_feature_check(php_bin, "argon2",
            "password_hash('x', PASSWORD_ARGON2ID); echo 'ok';"))
    if extra.get("with-sodium"):
        results.append(_feature_check(php_bin, "sodium",
            "sodium_crypto_secretbox_keygen(); echo 'ok';"))
    if extra.get("enable-gd") and extra.get("with-jpeg"):
        results.append(_feature_check(php_bin, "gd:jpeg",
            "var_dump(gd_info()['JPEG Support'] === true);"))

    return results


def _feature_check(php_bin: Path, name: str, code: str) -> CheckResult:
    try:
        result = subprocess.run(
            [str(php_bin), "-r", code],
            capture_output=True, text=True, timeout=10,
        )
        ok = result.returncode == 0
        return CheckResult(f"feature:{name}", ok, result.stderr.strip() if not ok else "")
    except Exception as exc:
        return CheckResult(f"feature:{name}", False, str(exc))
```

- [ ] **Schritt 4: Tests ausführen — müssen grün sein**

```bash
pytest tests/test_health.py -v
```

Erwartete Ausgabe: Alle 6 Tests PASSED

- [ ] **Schritt 5: Commit**

```bash
git add pbrew/utils/health.py tests/test_health.py
git commit -m "Füge health-Modul für Post-Build-Checks hinzu"
```

---

## Task 9: CLI — `pbrew install`

**Files:**
- Modify: `pbrew/cli/__init__.py`
- Create: `pbrew/cli/install.py`

- [ ] **Schritt 1: `install.py` implementieren**

Datei `pbrew/cli/install.py`:

```python
import shutil
import sys
import tarfile
import time
from pathlib import Path

import click

from pbrew.core import builder, config as cfg_mod, resolver, state as state_mod
from pbrew.core.paths import (
    bin_dir, build_log, cli_ini_dir, configs_dir,
    confd_dir, family_from_version, logs_dir,
    state_file, version_dir,
)
from pbrew.utils import download as dl_mod
from pbrew.utils.health import run_basic_checks


@click.command("install")
@click.argument("version_spec")
@click.option("--config", "config_name", default=None, help="Benannte Config (z.B. production)")
@click.option("--save", is_flag=True, help="Config nach dem Build speichern")
@click.option("-j", "--jobs", type=int, default=None, help="Parallele Build-Jobs")
@click.pass_context
def install_cmd(ctx, version_spec, config_name, save, jobs):
    """PHP aus dem Quellcode bauen und installieren."""
    prefix: Path = ctx.obj["prefix"]
    family = family_from_version(version_spec)

    click.echo(f"Prüfe verfügbare Versionen für PHP {family}...")
    release = resolver.fetch_latest(family)
    version = release.version
    click.echo(f"  Neueste Version: {version}")

    vdir = version_dir(prefix, version)
    if vdir.exists():
        click.echo(f"  PHP {version} ist bereits installiert: {vdir}")
        return

    # Config laden
    cfgs_dir = configs_dir(prefix)
    cfg_mod.init_default_config(cfgs_dir)
    config = cfg_mod.load_config(cfgs_dir, family, named=config_name)
    num_jobs = builder.get_jobs(config, override=jobs)

    # Config speichern wenn --save
    if save and config_name:
        cfg_mod.save_config(cfgs_dir, config_name, config)
        click.echo(f"  Config als '{config_name}' gespeichert.")

    # Download
    dist_dir = prefix / "distfiles"
    tarball = dist_dir / f"php-{version}.tar.bz2"
    if not tarball.exists():
        click.echo(f"  Lade php-{version}.tar.bz2 herunter...")
        dl_mod.download(release.tarball_url, tarball, expected_sha256=release.sha256)
    else:
        click.echo(f"  Nutze gecachten Tarball: {tarball}")

    # Entpacken
    build_dir = prefix / "build" / version
    if not build_dir.exists():
        click.echo(f"  Entpacke nach {build_dir}...")
        build_dir.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(tarball, "r:bz2") as tar:
            tar.extractall(build_dir.parent)
        # PHP entpackt in php-8.4.22/, umbenennen
        extracted = build_dir.parent / f"php-{version}"
        if extracted.exists() and not build_dir.exists():
            extracted.rename(build_dir)

    # Build-Log vorbereiten
    log_path = build_log(prefix, version)
    logs_dir(prefix).mkdir(parents=True, exist_ok=True)

    # Verzeichnisse anlegen
    cli_ini_dir(prefix, family).mkdir(parents=True, exist_ok=True)
    confd_dir(prefix, family).mkdir(parents=True, exist_ok=True)

    click.echo(f"  Baue PHP {version} mit {num_jobs} Jobs...")
    start = time.monotonic()

    with open(log_path, "w") as log:
        try:
            args = builder.build_configure_args(prefix, version, family, config)
            builder.run_configure(build_dir, args, log)
            builder.run_make(build_dir, num_jobs, log)
            builder.run_make_install(build_dir, log)
        except Exception as exc:
            click.echo(f"\n  Fehler beim Build. Log: {log_path}", err=True)
            click.echo(f"  {exc}", err=True)
            sys.exit(1)

    duration = time.monotonic() - start
    click.echo(f"  Build abgeschlossen ({duration:.0f}s)")

    # php.ini aus php.ini-production kopieren
    _init_php_ini(prefix, version, family)

    # State aktualisieren
    sf = state_file(prefix, family)
    state_mod.set_active_version(sf, version, config=config_name or "default")
    state_mod.set_build_duration(sf, version, duration)

    # Symlinks / Wrapper
    _update_wrappers(prefix, version, family)

    # Health-Check
    click.echo("  Health-Check...")
    results = run_basic_checks(prefix, version, family, config)
    for r in results:
        icon = "✓" if r.ok else "✗"
        msg = f" — {r.message}" if r.message else ""
        click.echo(f"    {icon} {r.name}{msg}")

    if any(not r.ok for r in results):
        click.echo("  Warnung: Einige Checks fehlgeschlagen. Log: " + str(log_path), err=True)

    click.echo(f"✓ PHP {version} installiert.")


def _init_php_ini(prefix: Path, version: str, family: str) -> None:
    """Kopiert php.ini-production als Basis — nur wenn noch nicht vorhanden."""
    src = version_dir(prefix, version) / "lib" / "php.ini-production"
    for dest_dir in (cli_ini_dir(prefix, family), prefix / "etc" / "fpm" / family):
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / "php.ini"
        if not dest.exists() and src.exists():
            shutil.copy2(src, dest)

    # 00-base.ini
    base_ini = confd_dir(prefix, family) / "00-base.ini"
    if not base_ini.exists():
        base_ini.write_text(
            "[Date]\ndate.timezone = Europe/Berlin\n\n"
            "[opcache]\nopcache.enable = 1\nopcache.memory_consumption = 128\n"
        )


def _update_wrappers(prefix: Path, version: str, family: str) -> None:
    """Erstellt php84, phpize84, php-config84 Wrapper in PREFIX/bin/."""
    bdir = bin_dir(prefix)
    bdir.mkdir(parents=True, exist_ok=True)

    suffix = family.replace(".", "")  # "8.4" -> "84"
    php_bin = version_dir(prefix, version) / "bin" / "php"
    phpize_bin = version_dir(prefix, version) / "bin" / "phpize"
    php_config_bin = version_dir(prefix, version) / "bin" / "php-config"

    for name, target in [
        (f"php{suffix}", php_bin),
        (f"phpize{suffix}", phpize_bin),
        (f"php-config{suffix}", php_config_bin),
    ]:
        wrapper = bdir / name
        wrapper.write_text(f"#!/bin/bash\nexec {target} \"$@\"\n")
        wrapper.chmod(0o755)
```

- [ ] **Schritt 2: Entry Point erweitern**

Datei `pbrew/cli/__init__.py` ersetzen:

```python
import click
from pbrew.cli.install import install_cmd


@click.group()
@click.option("--prefix", envvar="PBREW_ROOT", help="pbrew Prefix-Verzeichnis")
@click.pass_context
def main(ctx, prefix):
    """pbrew — PHP Version Manager"""
    ctx.ensure_object(dict)
    from pbrew.core.paths import get_prefix
    from pathlib import Path
    ctx.obj["prefix"] = Path(prefix) if prefix else get_prefix()


main.add_command(install_cmd, name="install")
```

- [ ] **Schritt 3: Manueller Smoke-Test (ohne echten Build)**

```bash
pbrew install --help
```

Erwartete Ausgabe:
```
Usage: pbrew install [OPTIONS] VERSION_SPEC

  PHP aus dem Quellcode bauen und installieren.

Options:
  --config TEXT  Benannte Config (z.B. production)
  --save         Config nach dem Build speichern
  -j, --jobs INTEGER  Parallele Build-Jobs
  --help         Show this message and exit.
```

- [ ] **Schritt 4: Commit**

```bash
git add pbrew/cli/__init__.py pbrew/cli/install.py
git commit -m "Füge pbrew-install-Command hinzu"
```

---

## Task 10: CLI — `pbrew list`, `pbrew use`, `pbrew switch`

**Files:**
- Create: `pbrew/cli/list_.py`
- Create: `pbrew/cli/use.py`
- Modify: `pbrew/cli/__init__.py`

- [ ] **Schritt 1: `list_.py` implementieren**

Datei `pbrew/cli/list_.py`:

```python
from pathlib import Path

import click

from pbrew.core.paths import get_prefix, state_file, versions_dir
from pbrew.core.state import get_family_state, get_global_state, global_state_file


@click.command("list")
@click.pass_context
def list_cmd(ctx):
    """Zeigt alle installierten PHP-Versionen."""
    prefix: Path = ctx.obj["prefix"]
    vdir = versions_dir(prefix)

    if not vdir.exists():
        click.echo("Keine PHP-Versionen installiert.")
        return

    # Families aus installierten Versions-Verzeichnissen ableiten
    installed_versions: dict[str, list[str]] = {}
    for entry in sorted(vdir.iterdir()):
        if not entry.is_dir():
            continue
        parts = entry.name.split(".")
        if len(parts) >= 2:
            family = f"{parts[0]}.{parts[1]}"
            installed_versions.setdefault(family, []).append(entry.name)

    global_state = get_global_state(global_state_file(prefix))
    default_family = global_state.get("default_family", "")

    click.echo(f"\n{'Family':<8} {'Aktiv':<12} {'Vorherige':<12} {'Wrapper':<10} {'Extensions'}")
    click.echo("─" * 70)

    for family in sorted(installed_versions):
        sf = state_file(prefix, family)
        state = get_family_state(sf)
        active = state.get("active", "—")
        previous = state.get("previous", "—")
        suffix = family.replace(".", "")
        extensions = ", ".join(state.get("extensions", [])) or "—"
        default_mark = " *" if family == default_family else ""
        click.echo(f"  {family:<8} {active:<12} {previous:<12} php{suffix:<7} {extensions}{default_mark}")

    if default_family:
        click.echo(f"\n  * php{default_family.replace('.', '')} ist der aktuelle Default")
    click.echo()
```

- [ ] **Schritt 2: `use.py` implementieren**

Datei `pbrew/cli/use.py`:

```python
from pathlib import Path

import click

from pbrew.core.paths import family_from_version, state_file, global_state_file
from pbrew.core.state import get_family_state, set_global_default


@click.command("use")
@click.argument("version_spec")
@click.pass_context
def use_cmd(ctx, version_spec):
    """Setzt PHP-Version für die aktuelle Shell-Session (via Shell-Funktion)."""
    prefix: Path = ctx.obj["prefix"]
    family = family_from_version(version_spec)
    sf = state_file(prefix, family)
    state = get_family_state(sf)

    if not state.get("active"):
        click.echo(f"PHP {family} ist nicht installiert. Zuerst: pbrew install {family}", err=True)
        raise SystemExit(1)

    # 'pbrew use' muss als Shell-Funktion implementiert werden (kann ENV nicht setzen)
    # Dieses Kommando gibt den Shell-Code aus, der von der Shell-Funktion ausgeführt wird
    suffix = family.replace(".", "")
    click.echo(f"export PBREW_PHP={family}")
    click.echo(f"export PATH={prefix / 'bin'}:$PATH")
    click.echo(f"hash -r")


@click.command("switch")
@click.argument("version_spec")
@click.pass_context
def switch_cmd(ctx, version_spec):
    """Setzt PHP-Version permanent als Default."""
    prefix: Path = ctx.obj["prefix"]
    family = family_from_version(version_spec)
    sf = state_file(prefix, family)
    state = get_family_state(sf)

    if not state.get("active"):
        click.echo(f"PHP {family} ist nicht installiert. Zuerst: pbrew install {family}", err=True)
        raise SystemExit(1)

    set_global_default(global_state_file(prefix), family)
    suffix = family.replace(".", "")
    click.echo(f"✓ php{suffix} ist jetzt der permanente Default (pbrew switch)")
```

- [ ] **Schritt 3: Commands registrieren**

Datei `pbrew/cli/__init__.py` erweitern:

```python
import click
from pbrew.cli.install import install_cmd
from pbrew.cli.list_ import list_cmd
from pbrew.cli.use import use_cmd, switch_cmd


@click.group()
@click.option("--prefix", envvar="PBREW_ROOT", help="pbrew Prefix-Verzeichnis")
@click.pass_context
def main(ctx, prefix):
    """pbrew — PHP Version Manager"""
    ctx.ensure_object(dict)
    from pbrew.core.paths import get_prefix
    from pathlib import Path
    ctx.obj["prefix"] = Path(prefix) if prefix else get_prefix()


main.add_command(install_cmd, name="install")
main.add_command(list_cmd, name="list")
main.add_command(use_cmd, name="use")
main.add_command(switch_cmd, name="switch")
```

- [ ] **Schritt 4: Smoke-Test**

```bash
pbrew list --help
pbrew use --help
pbrew switch --help
```

- [ ] **Schritt 5: Commit**

```bash
git add pbrew/cli/list_.py pbrew/cli/use.py pbrew/cli/__init__.py
git commit -m "Füge list/use/switch-Commands hinzu"
```

---

## Task 11: CLI — `pbrew known`, `pbrew clean`, `pbrew log`

**Files:**
- Create: `pbrew/cli/known.py`
- Create: `pbrew/cli/clean.py`
- Create: `pbrew/cli/log_.py`
- Modify: `pbrew/cli/__init__.py`

- [ ] **Schritt 1: `known.py` implementieren**

Datei `pbrew/cli/known.py`:

```python
import click
from pbrew.core.resolver import fetch_known


@click.command("known")
@click.option("--major", default=8, show_default=True, help="PHP Major-Version")
def known_cmd(major):
    """Listet verfügbare PHP-Versionen von php.net."""
    click.echo(f"Verfügbare PHP {major}.x Versionen...")
    releases = fetch_known(major)

    current_family = None
    for r in releases:
        if r.family != current_family:
            current_family = r.family
            click.echo(f"\n  PHP {r.family}:")
        click.echo(f"    {r.version}")
    click.echo()
```

- [ ] **Schritt 2: `clean.py` implementieren**

Datei `pbrew/cli/clean.py`:

```python
import shutil
from pathlib import Path

import click

from pbrew.core.paths import family_from_version, version_dir, state_file
from pbrew.core.state import get_family_state


@click.command("clean")
@click.argument("version")
@click.option("--yes", "-y", is_flag=True, help="Ohne Bestätigung löschen")
@click.pass_context
def clean_cmd(ctx, version, yes):
    """Entfernt eine alte PHP-Patch-Version (Build-Verzeichnis)."""
    prefix: Path = ctx.obj["prefix"]
    family = family_from_version(version)
    sf = state_file(prefix, family)
    state = get_family_state(sf)

    if state.get("active") == version:
        click.echo(f"Fehler: {version} ist die aktive Version. Erst auf andere wechseln.", err=True)
        raise SystemExit(1)

    vdir = version_dir(prefix, version)
    if not vdir.exists():
        click.echo(f"{version} ist nicht installiert.")
        return

    size_mb = sum(f.stat().st_size for f in vdir.rglob("*") if f.is_file()) / 1_048_576
    click.echo(f"Lösche PHP {version} ({size_mb:.0f} MB): {vdir}")

    if not yes and not click.confirm("Fortfahren?"):
        click.echo("Abgebrochen.")
        return

    shutil.rmtree(vdir)
    click.echo(f"✓ PHP {version} entfernt.")
```

- [ ] **Schritt 3: `log_.py` implementieren**

Datei `pbrew/cli/log_.py`:

```python
import subprocess
import sys
from pathlib import Path

import click

from pbrew.core.paths import build_log, family_from_version


@click.command("log")
@click.argument("version_spec")
@click.option("--tail", "-f", is_flag=True, help="Log live verfolgen")
@click.pass_context
def log_cmd(ctx, version_spec, tail):
    """Zeigt das Build-Log einer PHP-Version."""
    prefix: Path = ctx.obj["prefix"]
    family = family_from_version(version_spec)

    from pbrew.core.state import get_family_state
    from pbrew.core.paths import state_file
    sf = state_file(prefix, family)
    state = get_family_state(sf)
    version = state.get("active", version_spec)

    log = build_log(prefix, version)
    if not log.exists():
        click.echo(f"Kein Build-Log für {version} gefunden: {log}", err=True)
        raise SystemExit(1)

    if tail:
        subprocess.run(["tail", "-f", str(log)])
    else:
        click.echo(log.read_text())
```

- [ ] **Schritt 4: Commands registrieren**

Datei `pbrew/cli/__init__.py`:

```python
import click
from pbrew.cli.install import install_cmd
from pbrew.cli.list_ import list_cmd
from pbrew.cli.use import use_cmd, switch_cmd
from pbrew.cli.known import known_cmd
from pbrew.cli.clean import clean_cmd
from pbrew.cli.log_ import log_cmd


@click.group()
@click.option("--prefix", envvar="PBREW_ROOT", help="pbrew Prefix-Verzeichnis")
@click.pass_context
def main(ctx, prefix):
    """pbrew — PHP Version Manager"""
    ctx.ensure_object(dict)
    from pbrew.core.paths import get_prefix
    from pathlib import Path
    ctx.obj["prefix"] = Path(prefix) if prefix else get_prefix()


main.add_command(install_cmd, name="install")
main.add_command(list_cmd, name="list")
main.add_command(use_cmd, name="use")
main.add_command(switch_cmd, name="switch")
main.add_command(known_cmd, name="known")
main.add_command(clean_cmd, name="clean")
main.add_command(log_cmd, name="log")
```

- [ ] **Schritt 5: Commit**

```bash
git add pbrew/cli/known.py pbrew/cli/clean.py pbrew/cli/log_.py pbrew/cli/__init__.py
git commit -m "Füge known/clean/log-Commands hinzu"
```

---

## Task 12: Shell-Integration

**Files:**
- Create: `pbrew/cli/shell_init.py`
- Modify: `pbrew/cli/__init__.py`

`★ Insight ─────────────────────────────────────`
`pbrew use` kann die ENV-Variable der übergeordneten Shell nicht setzen (Prozess-Isolation). Die Shell-Funktion ist der Standard-Workaround: `pbrew use 84` evaluiert `$(pbrew use 84)` oder die Shell-Funktion ruft pbrew auf und führt seinen Output als Shell-Code aus.
`─────────────────────────────────────────────────`

- [ ] **Schritt 1: `shell_init.py` implementieren**

Datei `pbrew/cli/shell_init.py`:

```python
import click
from pbrew.core.paths import get_prefix, bin_dir


_BASH_INIT = '''\
# pbrew shell integration — automatisch generiert von "pbrew shell-init bash"
export PBREW_ROOT="{prefix}"
export PATH="{bin_dir}:$PATH"

# pbrew use: setzt PBREW_PHP in der aktuellen Shell
pbrew() {{
    local cmd="$1"
    if [ "$cmd" = "use" ] || [ "$cmd" = "switch" ]; then
        eval "$(command pbrew "$@")"
    else
        command pbrew "$@"
    fi
}}
'''

_ZSH_INIT = '''\
# pbrew shell integration — automatisch generiert von "pbrew shell-init zsh"
export PBREW_ROOT="{prefix}"
export PATH="{bin_dir}:$PATH"

pbrew() {{
    local cmd="$1"
    if [[ "$cmd" == "use" || "$cmd" == "switch" ]]; then
        eval "$(command pbrew $@)"
    else
        command pbrew "$@"
    fi
}}
'''


@click.command("shell-init")
@click.argument("shell", type=click.Choice(["bash", "zsh"]))
@click.pass_context
def shell_init_cmd(ctx, shell):
    """Gibt Shell-Integration aus (in ~/.bashrc oder ~/.zshrc einbinden)."""
    prefix = ctx.obj["prefix"]
    template = _BASH_INIT if shell == "bash" else _ZSH_INIT
    click.echo(template.format(
        prefix=prefix,
        bin_dir=bin_dir(prefix),
    ))
```

- [ ] **Schritt 2: Command registrieren**

In `pbrew/cli/__init__.py` ergänzen (nach `log_cmd` import und `add_command`):

```python
from pbrew.cli.shell_init import shell_init_cmd
# ...
main.add_command(shell_init_cmd, name="shell-init")
```

- [ ] **Schritt 3: Smoke-Test**

```bash
pbrew shell-init bash
```

Erwartete Ausgabe:
```bash
# pbrew shell integration — automatisch generiert von "pbrew shell-init bash"
export PBREW_ROOT="/home/user/.pbrew"
export PATH="/home/user/.pbrew/bin:$PATH"

pbrew() {
    ...
}
```

- [ ] **Schritt 4: Commit**

```bash
git add pbrew/cli/shell_init.py pbrew/cli/__init__.py
git commit -m "Füge shell-init für bash/zsh-Integration hinzu"
```

---

## Task 13: `pbrew doctor`

**Files:**
- Create: `pbrew/cli/doctor.py`
- Modify: `pbrew/cli/__init__.py`

- [ ] **Schritt 1: `doctor.py` implementieren**

Datei `pbrew/cli/doctor.py`:

```python
import shutil
import subprocess
from pathlib import Path

import click

from pbrew.core.paths import bin_dir, get_prefix, state_file, versions_dir
from pbrew.core.state import get_family_state


# apt-Pakete die für den Build benötigt werden
_REQUIRED_PACKAGES = [
    "gcc", "g++", "make", "autoconf", "bison", "re2c",
    "libxml2-dev", "libssl-dev", "libsqlite3-dev", "libcurl4-openssl-dev",
    "libpng-dev", "libjpeg-dev", "libfreetype6-dev", "libwebp-dev",
    "libgmp-dev", "libtidy-dev", "libsodium-dev", "libargon2-dev",
    "libonig-dev", "libzip-dev", "libintl-perl",
    "libsystemd-dev",  # für --with-fpm-systemd
]

_REQUIRED_BINS = ["gcc", "make", "autoconf", "bison", "re2c", "pkg-config"]


@click.command("doctor")
@click.pass_context
def doctor_cmd(ctx):
    """Systemweite Prüfung der pbrew-Installation und Build-Voraussetzungen."""
    prefix: Path = ctx.obj["prefix"]
    ok_all = True

    click.echo("Prüfe pbrew-Installation...\n")

    # Python-Version
    import sys
    py_ok = sys.version_info >= (3, 11)
    _show("Python " + sys.version.split()[0], py_ok)
    ok_all = ok_all and py_ok

    # Binary-Dependencies
    click.echo("\nBinaries:")
    for binary in _REQUIRED_BINS:
        found = shutil.which(binary) is not None
        _show(binary, found)
        ok_all = ok_all and found

    # Installierte Versionen vs. State-Konsistenz
    vdir = versions_dir(prefix)
    if vdir.exists():
        click.echo("\nInstallierte Versionen:")
        for entry in sorted(vdir.iterdir()):
            if not entry.is_dir():
                continue
            parts = entry.name.split(".")
            if len(parts) >= 3:
                family = f"{parts[0]}.{parts[1]}"
                sf = state_file(prefix, family)
                state = get_family_state(sf)
                active = state.get("active") == entry.name
                _show(f"{entry.name} {'(aktiv)' if active else ''}", True)
    else:
        click.echo("\n  Keine Versionen installiert.")

    # Symlinks in bin/
    bdir = bin_dir(prefix)
    if bdir.exists():
        click.echo("\nWrapper in " + str(bdir) + ":")
        for wrapper in sorted(bdir.iterdir()):
            ok = wrapper.is_file() and wrapper.stat().st_mode & 0o111
            _show(str(wrapper.name), ok)

    click.echo()
    if ok_all:
        click.echo("✓ Alles in Ordnung.")
    else:
        click.echo("✗ Einige Prüfungen fehlgeschlagen.", err=True)
        raise SystemExit(1)


def _show(name: str, ok: bool) -> None:
    icon = "✓" if ok else "✗"
    click.echo(f"  {icon} {name}")
```

- [ ] **Schritt 2: Command registrieren**

Finaler Stand `pbrew/cli/__init__.py`:

```python
import click
from pbrew.cli.install import install_cmd
from pbrew.cli.list_ import list_cmd
from pbrew.cli.use import use_cmd, switch_cmd
from pbrew.cli.known import known_cmd
from pbrew.cli.clean import clean_cmd
from pbrew.cli.log_ import log_cmd
from pbrew.cli.shell_init import shell_init_cmd
from pbrew.cli.doctor import doctor_cmd


@click.group()
@click.option("--prefix", envvar="PBREW_ROOT", help="pbrew Prefix-Verzeichnis")
@click.pass_context
def main(ctx, prefix):
    """pbrew — PHP Version Manager"""
    ctx.ensure_object(dict)
    from pbrew.core.paths import get_prefix
    from pathlib import Path
    ctx.obj["prefix"] = Path(prefix) if prefix else get_prefix()


main.add_command(install_cmd, name="install")
main.add_command(list_cmd, name="list")
main.add_command(use_cmd, name="use")
main.add_command(switch_cmd, name="switch")
main.add_command(known_cmd, name="known")
main.add_command(clean_cmd, name="clean")
main.add_command(log_cmd, name="log")
main.add_command(shell_init_cmd, name="shell-init")
main.add_command(doctor_cmd, name="doctor")
```

- [ ] **Schritt 3: Smoke-Test**

```bash
pbrew doctor
```

Erwartete Ausgabe (ohne vollständige Umgebung):
```
Prüfe pbrew-Installation...

  ✓ Python 3.12.3

Binaries:
  ✓ gcc
  ✓ make
  ...
```

- [ ] **Schritt 4: Alle Tests ausführen**

```bash
pytest -v
```

Erwartete Ausgabe: Alle Tests PASSED (kein FAILED, keine ERROR)

- [ ] **Schritt 5: Commit**

```bash
git add pbrew/cli/doctor.py pbrew/cli/__init__.py
git commit -m "Füge doctor-Command für Systemprüfung hinzu"
```

---

## Task 14: Packaging & README

**Files:**
- Modify: `pyproject.toml`
- Create: `README.md`

- [ ] **Schritt 1: `pyproject.toml` finalisieren**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "pbrew"
version = "0.1.0"
description = "Python-based PHP version manager — phpbrew successor"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.11"
dependencies = [
    "click>=8.1",
    "tomlkit>=0.12",
]

[project.scripts]
pbrew = "pbrew.cli:main"

[tool.setuptools.packages.find]
where = ["."]
include = ["pbrew*"]

[project.optional-dependencies]
dev = ["pytest>=8.0"]
```

- [ ] **Schritt 2: Installations-Anleitung in README**

Datei `README.md`:

```markdown
# pbrew — PHP Version Manager

Python-basierter PHP-Versionsmanager. Baut PHP aus dem Quellcode, kein PHP zum Starten benötigt.

## Voraussetzungen

- Python 3.11+
- Ubuntu 22.04 / 24.04

## Installation

```bash
git clone git@github.com:PPP01/pbrew.git
cd pbrew
pip install -e .
```

## Shell-Integration

In `~/.bashrc` oder `~/.zshrc` einfügen:

```bash
eval "$(pbrew shell-init bash)"
```

## Erste PHP-Version installieren

```bash
pbrew install 84          # Neueste PHP 8.4.x bauen
pbrew list                # Installierte Versionen anzeigen
pbrew use 84              # PHP 8.4 für diese Session
pbrew switch 84           # PHP 8.4 als permanenten Default
```
```

- [ ] **Schritt 3: Installierbarkeit prüfen**

```bash
pip install -e ".[dev]"
pbrew --help
```

- [ ] **Schritt 4: Final Commit + Tag**

```bash
git add pyproject.toml README.md
git commit -m "Finalisiere Packaging und README für v0.1.0"
git tag v0.1.0
git push origin main --tags
```

---

## Self-Review

**Spec-Coverage:**

| Spec-Abschnitt | Task |
|---|---|
| Architektur / Paketstruktur | Task 1 |
| Installationsstruktur (PREFIX) | Task 2, paths.py |
| Config-Format TOML + Cascade | Task 3 |
| State-Datei | Task 4 |
| Versions-Auflösung | Task 2 (`family_from_version`) |
| Build-System (Single-Build) | Task 7 |
| Post-Build-Schritte (php.ini, symlinks) | Task 9 (`_init_php_ini`, `_update_wrappers`) |
| Build-Jobs | Task 7 (`get_jobs`) |
| CLI install | Task 9 |
| CLI list | Task 10 |
| CLI use / switch | Task 10 |
| CLI known | Task 11 |
| CLI clean | Task 11 |
| CLI log | Task 11 |
| Shell-Integration | Task 12 |
| Doctor | Task 13 |
| Health-Check inkl. scan-dir-Verifikation | Task 8 |
| Download + SHA256 | Task 6 |
| Dependency-Check (doctor) | Task 13 |

**Nicht in diesem Plan (separate Pläne):**
- Upgrade-Workflow + Rollback → Plan 3
- FPM-Management (pools, systemd, Xdebug) → Plan 2
- Extension-Management (phpize, PECL, INI) → Plan 3
- `pbrew fpm *`, `pbrew ext *` Commands → Plan 2 / Plan 3
- `pbrew config edit/show` → Plan 3
- `pbrew info`, `pbrew rollback` → Plan 3

**Placeholder-Scan:** Keine "TBD" oder "implement later" gefunden. Alle Schritte enthalten konkreten Code.

**Typ-Konsistenz:**
- `PhpRelease` (resolver.py) → verwendet in `install.py` ✓
- `CheckResult` (health.py) → verwendet in `install.py` ✓
- `family_from_version` (paths.py) → verwendet in `install.py`, `use.py`, `clean.py`, `log_.py` ✓
- `state_file` (paths.py) → verwendet in `install.py`, `list_.py`, `use.py` ✓
