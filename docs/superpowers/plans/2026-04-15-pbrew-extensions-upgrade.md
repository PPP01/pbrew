# pbrew Extensions & Upgrade — Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** PECL-Extension-Installation, INI-Management, Upgrade-Workflow mit Config-Diff und Rollback. Ergebnis: `pbrew ext install/remove/enable/disable/list`, `pbrew upgrade`, `pbrew rollback`, `pbrew config edit/show`, `pbrew info`.

**Architecture:** Neues Modul `pbrew/extensions/` (pecl.py, installer.py). Upgrade-Logik in `pbrew/cli/upgrade.py` nutzt die bestehenden `resolver`, `builder`, `health`-Module aus Plan 1 und die FPM-Funktionen aus Plan 2. Config-Diff per `difflib` (stdlib).

**Tech Stack:** Python 3.11+, click 8.x, xml.etree.ElementTree (stdlib), difflib (stdlib), subprocess. Keine neuen externen Packages.

**Voraussetzung:** Plan 1 (Foundation & Core) und Plan 2 (FPM Management) vollständig umgesetzt.

---

## Dateistruktur

```
pbrew/
└── extensions/
    ├── __init__.py
    ├── pecl.py         ← PECL-API-Client (XML)
    └── installer.py    ← phpize/make/install + INI-Management
pbrew/cli/
├── ext.py              ← pbrew ext Kommandogruppe
├── upgrade.py          ← pbrew upgrade + pbrew rollback
├── config_.py          ← pbrew config edit/show
└── info.py             ← pbrew info
tests/
├── test_pecl.py
└── test_installer.py
```

---

## Task 1: PECL-API-Client

**Files:**
- Create: `pbrew/extensions/__init__.py`
- Create: `pbrew/extensions/pecl.py`
- Create: `tests/test_pecl.py`

`★ Insight ─────────────────────────────────────`
Die PECL-REST-API liefert XML (nicht JSON). Python's `xml.etree.ElementTree` aus der Stdlib ist ausreichend. Der Namespace `http://pear.php.net/dtd/rest.allreleases` muss explizit angegeben werden. Download-URL: `https://pecl.php.net/get/{package}-{version}.tgz`.
`─────────────────────────────────────────────────`

- [ ] **Schritt 1: Tests schreiben**

Datei `tests/test_pecl.py`:

```python
from unittest.mock import patch, MagicMock
from pbrew.extensions.pecl import fetch_releases, fetch_latest_stable, PeclRelease

_XML = b"""<?xml version="1.0" encoding="UTF-8" ?>
<a xmlns="http://pear.php.net/dtd/rest.allreleases">
 <p>xdebug</p>
 <c>pecl.php.net</c>
 <r><v>3.3.2</v><s>stable</s></r>
 <r><v>3.3.1</v><s>stable</s></r>
 <r><v>3.4.0beta1</v><s>beta</s></r>
</a>"""


def _mock_urlopen(data: bytes):
    mock_resp = MagicMock()
    mock_resp.read.return_value = data
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def test_fetch_releases_returns_all():
    with patch("pbrew.extensions.pecl.urllib.request.urlopen",
               return_value=_mock_urlopen(_XML)):
        releases = fetch_releases("xdebug")
    assert len(releases) == 3


def test_fetch_releases_parses_version():
    with patch("pbrew.extensions.pecl.urllib.request.urlopen",
               return_value=_mock_urlopen(_XML)):
        releases = fetch_releases("xdebug")
    assert releases[0].version == "3.3.2"


def test_fetch_releases_parses_stability():
    with patch("pbrew.extensions.pecl.urllib.request.urlopen",
               return_value=_mock_urlopen(_XML)):
        releases = fetch_releases("xdebug")
    assert releases[0].stability == "stable"
    assert releases[2].stability == "beta"


def test_fetch_releases_builds_tarball_url():
    with patch("pbrew.extensions.pecl.urllib.request.urlopen",
               return_value=_mock_urlopen(_XML)):
        releases = fetch_releases("xdebug")
    assert releases[0].tarball_url == "https://pecl.php.net/get/xdebug-3.3.2.tgz"


def test_fetch_latest_stable_skips_beta():
    with patch("pbrew.extensions.pecl.urllib.request.urlopen",
               return_value=_mock_urlopen(_XML)):
        release = fetch_latest_stable("xdebug")
    assert release.version == "3.3.2"
    assert release.stability == "stable"


def test_fetch_latest_stable_raises_when_no_stable():
    xml_only_beta = b"""<?xml version="1.0" ?>
<a xmlns="http://pear.php.net/dtd/rest.allreleases">
 <r><v>1.0.0beta</v><s>beta</s></r>
</a>"""
    with patch("pbrew.extensions.pecl.urllib.request.urlopen",
               return_value=_mock_urlopen(xml_only_beta)):
        import pytest
        with pytest.raises(RuntimeError, match="kein stabiles"):
            fetch_latest_stable("myext")
```

- [ ] **Schritt 2: Tests ausführen — müssen fehlschlagen**

```bash
pytest tests/test_pecl.py -v
```

- [ ] **Schritt 3: `pbrew/extensions/__init__.py` anlegen**

```python
```

(leer)

- [ ] **Schritt 4: `pbrew/extensions/pecl.py` implementieren**

```python
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass

PECL_REST = "https://pecl.php.net/rest/r"
_NS = {"p": "http://pear.php.net/dtd/rest.allreleases"}


@dataclass
class PeclRelease:
    package: str
    version: str
    stability: str    # "stable", "beta", "alpha"
    tarball_url: str


def fetch_releases(package: str) -> list[PeclRelease]:
    """Holt alle Releases eines PECL-Pakets von pecl.php.net."""
    url = f"{PECL_REST}/{package.lower()}/allreleases.xml"
    with urllib.request.urlopen(url, timeout=30) as resp:
        xml_data = resp.read()

    root = ET.fromstring(xml_data)
    releases = []
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
```

- [ ] **Schritt 5: Tests ausführen — müssen grün sein**

```bash
pytest tests/test_pecl.py -v
```

Erwartete Ausgabe: Alle 6 Tests PASSED

- [ ] **Schritt 6: Commit**

```bash
git add pbrew/extensions/ tests/test_pecl.py
git commit -m "Füge extensions/pecl-Modul für PECL-API-Client hinzu"
```

---

## Task 2: Extension-Installer + INI-Management

**Files:**
- Create: `pbrew/extensions/installer.py`
- Create: `tests/test_installer.py`

- [ ] **Schritt 1: Tests schreiben**

Datei `tests/test_installer.py`:

```python
import tarfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch, MagicMock, call
import pytest
from pbrew.extensions.installer import (
    extract_tarball,
    install_extension,
    write_ext_ini,
)

PREFIX = Path("/opt/pbrew")


def _make_tgz(tmp_path: Path, name: str) -> Path:
    """Erstellt einen minimalen .tgz für Tests."""
    src = tmp_path / name
    src.mkdir()
    (src / "config.m4").write_text("PHP_ARG_ENABLE(myext)")
    tgz = tmp_path / f"{name}.tgz"
    with tarfile.open(tgz, "w:gz") as tar:
        tar.add(src, arcname=name)
    return tgz


def test_extract_tarball_returns_src_dir(tmp_path):
    tgz = _make_tgz(tmp_path, "xdebug-3.3.2")
    dest = tmp_path / "build"
    src_dir = extract_tarball(tgz, dest)
    assert src_dir.exists()
    assert src_dir.name == "xdebug-3.3.2"


def test_extract_tarball_creates_dest_dir(tmp_path):
    tgz = _make_tgz(tmp_path, "apcu-5.1.0")
    dest = tmp_path / "build" / "nested"
    extract_tarball(tgz, dest)
    assert dest.exists()


def test_write_ext_ini_creates_file(tmp_path):
    ini = write_ext_ini(tmp_path, "8.4", "apcu")
    assert ini.exists()
    assert ini.read_text() == "extension=apcu.so\n"


def test_write_ext_ini_zend_extension(tmp_path):
    ini = write_ext_ini(tmp_path, "8.4", "xdebug", is_zend=True)
    assert ini.read_text() == "zend_extension=xdebug.so\n"


def test_write_ext_ini_does_not_overwrite(tmp_path):
    ini = write_ext_ini(tmp_path, "8.4", "apcu")
    ini.write_text("custom=value\n")
    write_ext_ini(tmp_path, "8.4", "apcu")
    assert ini.read_text() == "custom=value\n"


def test_write_ext_ini_path(tmp_path):
    ini = write_ext_ini(tmp_path, "8.4", "redis")
    assert ini == tmp_path / "etc" / "conf.d" / "8.4" / "redis.ini"


def test_install_extension_calls_phpize(tmp_path):
    src_dir = tmp_path / "ext-src"
    src_dir.mkdir()
    (src_dir / "configure").write_text("#!/bin/bash\necho ok")
    (src_dir / "configure").chmod(0o755)

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd[0].split("/")[-1] if "/" in cmd[0] else cmd[0])
        proc = MagicMock()
        proc.stdout = iter([])
        proc.wait.return_value = None
        proc.returncode = 0
        return proc

    with patch("pbrew.extensions.installer.subprocess.Popen", side_effect=fake_run):
        install_extension(PREFIX, "8.4.22", "myext", src_dir, 4, StringIO())

    assert "phpize" in calls
    assert "make" in calls
```

- [ ] **Schritt 2: Tests ausführen — müssen fehlschlagen**

```bash
pytest tests/test_installer.py -v
```

- [ ] **Schritt 3: `pbrew/extensions/installer.py` implementieren**

```python
import subprocess
import tarfile
from pathlib import Path
from typing import IO


def extract_tarball(tarball: Path, dest_dir: Path) -> Path:
    """Entpackt Tarball nach dest_dir, gibt das Source-Verzeichnis zurück."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tarball) as tar:
        top_level = tar.getnames()[0].split("/")[0]
        tar.extractall(dest_dir)
    return dest_dir / top_level


def install_extension(
    prefix: Path,
    version: str,
    ext_name: str,
    src_dir: Path,
    jobs: int,
    log_file: IO[str],
) -> None:
    """Baut eine PHP-Extension via phpize → configure → make → make install."""
    phpize = prefix / "versions" / version / "bin" / "phpize"
    php_config = prefix / "versions" / version / "bin" / "php-config"

    _run([str(phpize)], cwd=src_dir, log_file=log_file)
    _run(
        [str(src_dir / "configure"), f"--with-php-config={php_config}"],
        cwd=src_dir,
        log_file=log_file,
    )
    _run(["make", f"-j{jobs}"], cwd=src_dir, log_file=log_file)
    _run(["make", "install"], cwd=src_dir, log_file=log_file)


def write_ext_ini(
    prefix: Path,
    family: str,
    ext_name: str,
    is_zend: bool = False,
) -> Path:
    """Schreibt Extension-INI in den shared scan-dir. Bestehende nie überschreiben."""
    ini_dir = prefix / "etc" / "conf.d" / family
    ini_dir.mkdir(parents=True, exist_ok=True)
    ini = ini_dir / f"{ext_name}.ini"
    if ini.exists():
        return ini
    directive = "zend_extension" if is_zend else "extension"
    ini.write_text(f"{directive}={ext_name}.so\n")
    return ini


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
pytest tests/test_installer.py -v
```

Erwartete Ausgabe: Alle 7 Tests PASSED

- [ ] **Schritt 5: Commit**

```bash
git add pbrew/extensions/installer.py tests/test_installer.py
git commit -m "Füge extensions/installer-Modul für phpize-Build-Workflow hinzu"
```

---

## Task 3: CLI — `pbrew ext`

**Files:**
- Create: `pbrew/cli/ext.py`
- Modify: `pbrew/cli/__init__.py`

- [ ] **Schritt 1: `pbrew/cli/ext.py` implementieren**

```python
import time
from pathlib import Path

import click

from pbrew.core.paths import (
    build_log, family_from_version, logs_dir, state_file, version_dir,
)
from pbrew.core.state import add_extension, get_family_state
from pbrew.extensions.installer import extract_tarball, install_extension, write_ext_ini
from pbrew.extensions.pecl import fetch_latest_stable, fetch_releases
from pbrew.utils.download import download

# Bekannte Zend-Extensions (brauchen zend_extension= statt extension=)
_ZEND_EXTENSIONS = {"xdebug", "opcache", "ioncube_loader"}


@click.group("ext")
def ext_cmd():
    """PHP-Extensions verwalten."""


@ext_cmd.command("install")
@click.argument("ext_name")
@click.argument("version_spec", required=False)
@click.option("-v", "--version", "ext_version", default=None, help="Exakte Extension-Version")
@click.option("-j", "--jobs", type=int, default=None)
@click.pass_context
def install_cmd(ctx, ext_name, version_spec, ext_version, jobs):
    """Installiert eine PECL-Extension für die aktive (oder angegebene) PHP-Version."""
    prefix: Path = ctx.obj["prefix"]
    family = _resolve_family(prefix, version_spec)
    php_version = _resolve_active_version(prefix, family)

    click.echo(f"Installiere {ext_name} für PHP {php_version}...")

    if ext_version:
        releases = fetch_releases(ext_name)
        release = next((r for r in releases if r.version == ext_version), None)
        if not release:
            click.echo(f"Version {ext_version} nicht gefunden.", err=True)
            raise SystemExit(1)
    else:
        click.echo(f"  Suche neueste stabile Version von {ext_name}...")
        release = fetch_latest_stable(ext_name)
        click.echo(f"  Neueste stabile Version: {release.version}")

    # Download
    dist_dir = prefix / "distfiles"
    tarball = dist_dir / f"{ext_name}-{release.version}.tgz"
    if not tarball.exists():
        click.echo(f"  Lade {ext_name}-{release.version}.tgz herunter...")
        download(release.tarball_url, tarball)

    # Entpacken
    build_dir = prefix / "build" / f"{ext_name}-{release.version}"
    if not build_dir.exists():
        src_dir = extract_tarball(tarball, build_dir.parent)
        if src_dir != build_dir:
            src_dir.rename(build_dir)

    # Build
    from pbrew.core.builder import get_jobs
    from pbrew.core.config import load_config
    from pbrew.core.paths import configs_dir
    config = load_config(configs_dir(prefix), family)
    num_jobs = get_jobs(config, override=jobs)

    log_path = logs_dir(prefix) / f"{ext_name}-{release.version}-{php_version}.log"
    logs_dir(prefix).mkdir(parents=True, exist_ok=True)

    click.echo(f"  Baue {ext_name} {release.version}...")
    with open(log_path, "w") as log:
        try:
            install_extension(prefix, php_version, ext_name, build_dir, num_jobs, log)
        except Exception as exc:
            click.echo(f"  Fehler beim Build. Log: {log_path}", err=True)
            click.echo(f"  {exc}", err=True)
            raise SystemExit(1)

    # INI schreiben
    is_zend = ext_name.lower() in _ZEND_EXTENSIONS
    ini = write_ext_ini(prefix, family, ext_name, is_zend=is_zend)
    click.echo(f"  INI: {ini}")

    # State
    sf = state_file(prefix, family)
    add_extension(sf, ext_name)
    click.echo(f"✓ {ext_name} {release.version} installiert.")


@ext_cmd.command("remove")
@click.argument("ext_name")
@click.argument("version_spec", required=False)
@click.pass_context
def remove_cmd(ctx, ext_name, version_spec):
    """Deaktiviert eine Extension (verschiebt INI zu .disabled)."""
    prefix: Path = ctx.obj["prefix"]
    family = _resolve_family(prefix, version_spec)
    ini = prefix / "etc" / "conf.d" / family / f"{ext_name}.ini"
    if not ini.exists():
        click.echo(f"{ext_name}.ini nicht gefunden für PHP {family}.", err=True)
        raise SystemExit(1)
    disabled = ini.with_suffix(".ini.disabled")
    ini.rename(disabled)
    click.echo(f"✓ {ext_name} deaktiviert (INI: {disabled})")


@ext_cmd.command("enable")
@click.argument("ext_name")
@click.argument("version_spec", required=False)
@click.pass_context
def enable_cmd(ctx, ext_name, version_spec):
    """Aktiviert eine deaktivierte Extension."""
    prefix: Path = ctx.obj["prefix"]
    family = _resolve_family(prefix, version_spec)
    disabled = prefix / "etc" / "conf.d" / family / f"{ext_name}.ini.disabled"
    ini = disabled.with_suffix("")
    if not disabled.exists():
        if ini.exists():
            click.echo(f"{ext_name} ist bereits aktiv.")
        else:
            click.echo(f"{ext_name}.ini.disabled nicht gefunden.", err=True)
            raise SystemExit(1)
        return
    disabled.rename(ini)
    click.echo(f"✓ {ext_name} aktiviert.")


@ext_cmd.command("disable")
@click.argument("ext_name")
@click.argument("version_spec", required=False)
@click.pass_context
def disable_cmd(ctx, ext_name, version_spec):
    """Deaktiviert eine Extension (Alias für remove ohne State-Änderung)."""
    prefix: Path = ctx.obj["prefix"]
    family = _resolve_family(prefix, version_spec)
    ini = prefix / "etc" / "conf.d" / family / f"{ext_name}.ini"
    if not ini.exists():
        click.echo(f"{ext_name} ist bereits deaktiviert oder nicht installiert.")
        return
    ini.rename(ini.with_suffix(".ini.disabled"))
    click.echo(f"✓ {ext_name} deaktiviert.")


@ext_cmd.command("list")
@click.argument("version_spec", required=False)
@click.pass_context
def list_cmd(ctx, version_spec):
    """Listet installierte Extensions für eine PHP-Family."""
    prefix: Path = ctx.obj["prefix"]
    family = _resolve_family(prefix, version_spec)
    confd = prefix / "etc" / "conf.d" / family
    if not confd.exists():
        click.echo(f"Kein scan-dir für PHP {family} gefunden.")
        return
    click.echo(f"\nExtensions für PHP {family} ({confd}):")
    for ini in sorted(confd.glob("*.ini")):
        click.echo(f"  [aktiv]    {ini.stem}")
    for ini in sorted(confd.glob("*.ini.disabled")):
        click.echo(f"  [inaktiv]  {ini.stem.replace('.ini', '')}")
    click.echo()


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _resolve_family(prefix: Path, version_spec: str | None) -> str:
    if version_spec:
        return family_from_version(version_spec)
    # Aus aktiver Session oder Global-State
    import os
    env = os.environ.get("PBREW_PHP")
    if env:
        return family_from_version(env)
    from pbrew.core.state import get_global_state
    from pbrew.core.paths import global_state_file
    state = get_global_state(global_state_file(prefix))
    family = state.get("default_family")
    if not family:
        raise click.UsageError(
            "Keine aktive PHP-Version. Angeben: pbrew ext install apcu 84"
        )
    return family


def _resolve_active_version(prefix: Path, family: str) -> str:
    sf = state_file(prefix, family)
    state = get_family_state(sf)
    version = state.get("active")
    if not version:
        raise click.UsageError(
            f"PHP {family} ist nicht installiert. Zuerst: pbrew install {family}"
        )
    return version
```

- [ ] **Schritt 2: `pbrew ext` registrieren**

In `pbrew/cli/__init__.py` ergänzen:

```python
from pbrew.cli.ext import ext_cmd
# ...
main.add_command(ext_cmd, name="ext")
```

- [ ] **Schritt 3: Smoke-Test**

```bash
pbrew ext --help
```

Erwartete Ausgabe:
```
Usage: pbrew ext [OPTIONS] COMMAND [ARGS]...

  PHP-Extensions verwalten.

Commands:
  disable  Deaktiviert eine Extension ...
  enable   Aktiviert eine deaktivierte Extension.
  install  Installiert eine PECL-Extension ...
  list     Listet installierte Extensions ...
  remove   Deaktiviert eine Extension ...
```

- [ ] **Schritt 4: Commit**

```bash
git add pbrew/cli/ext.py pbrew/cli/__init__.py
git commit -m "Füge pbrew-ext-Commands für Extension-Management hinzu"
```

---

## Task 4: Upgrade-Workflow

**Files:**
- Create: `pbrew/cli/upgrade.py`
- Modify: `pbrew/cli/__init__.py`

`★ Insight ─────────────────────────────────────`
Der Upgrade nutzt dieselbe Install-Logik aus Plan 1 — kein Code-Duplikat. Der Kern von `pbrew upgrade 84` ist: neue Version per Resolver suchen, `install_cmd` mit der neuen Version aufrufen, PECL-Extensions reinstallieren, FPM neustarten. Der Config-Diff (apt-Stil) vergleicht die neue `php.ini-production` mit der bestehenden.
`─────────────────────────────────────────────────`

- [ ] **Schritt 1: `pbrew/cli/upgrade.py` implementieren**

```python
import difflib
import shutil
from pathlib import Path

import click

from pbrew.core.paths import (
    cli_ini_dir, family_from_version, state_file, version_dir, versions_dir,
)
from pbrew.core.resolver import fetch_latest
from pbrew.core.state import get_family_state


@click.command("upgrade")
@click.argument("version_spec", required=False)
@click.option("--dry-run", is_flag=True, help="Nur anzeigen, nicht ausführen")
@click.pass_context
def upgrade_cmd(ctx, version_spec, dry_run):
    """Aktualisiert PHP-Versionen auf das neueste Patch-Level."""
    prefix: Path = ctx.obj["prefix"]

    families = _families_to_upgrade(prefix, version_spec)
    if not families:
        click.echo("Keine installierten PHP-Versionen gefunden.")
        return

    click.echo("Prüfe verfügbare Updates...")
    updates = []
    for family in sorted(families):
        sf = state_file(prefix, family)
        state = get_family_state(sf)
        current = state.get("active")
        if not current:
            continue
        try:
            latest = fetch_latest(family)
        except Exception as exc:
            click.echo(f"  Fehler beim Abrufen von PHP {family}: {exc}", err=True)
            continue
        if latest.version != current:
            updates.append((family, current, latest))
            click.echo(f"  {family}: {current} → {latest.version} verfügbar")
        else:
            click.echo(f"  {family}: {current} — aktuell")

    if not updates:
        click.echo("Alle Versionen sind aktuell.")
        return

    if dry_run:
        return

    for i, (family, current, latest) in enumerate(updates, 1):
        click.echo(f"\n[{i}/{len(updates)}] Aktualisiere {family}: {current} → {latest.version}...")
        _do_upgrade(ctx, prefix, family, current, latest)

    click.echo("\n✓ Upgrade abgeschlossen.")


@click.command("rollback")
@click.argument("version_spec")
@click.pass_context
def rollback_cmd(ctx, version_spec):
    """Wechselt auf die vorherige Patch-Version zurück."""
    prefix: Path = ctx.obj["prefix"]
    family = family_from_version(version_spec)
    sf = state_file(prefix, family)
    state = get_family_state(sf)

    previous = state.get("previous")
    if not previous:
        click.echo(f"Keine vorherige Version für PHP {family} gespeichert.", err=True)
        raise SystemExit(1)

    current = state.get("active")
    vdir = version_dir(prefix, previous)
    if not vdir.exists():
        click.echo(f"PHP {previous} ist nicht mehr installiert (bereits bereinigt?).", err=True)
        raise SystemExit(1)

    click.echo(f"Rollback: {current} → {previous}")
    _switch_to_version(prefix, family, previous)
    click.echo(f"✓ Rollback auf {previous} abgeschlossen.")


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _families_to_upgrade(prefix: Path, version_spec: str | None) -> list[str]:
    if version_spec:
        return [family_from_version(version_spec)]
    vdir = versions_dir(prefix)
    if not vdir.exists():
        return []
    families = set()
    for entry in vdir.iterdir():
        if entry.is_dir():
            parts = entry.name.split(".")
            if len(parts) >= 3:
                families.add(f"{parts[0]}.{parts[1]}")
    return sorted(families)


def _do_upgrade(ctx, prefix: Path, family: str, current: str, latest) -> None:
    from pbrew.cli.install import install_cmd

    # Neue Version bauen (nutzt vorhandene install-Logik)
    ctx.invoke(install_cmd, version_spec=latest.version)

    # Config-Diff prüfen
    _check_ini_diff(prefix, latest.version, family)

    # PECL-Extensions reinstallieren
    sf = state_file(prefix, family)
    state = get_family_state(sf)
    pecl_extensions = state.get("extensions", [])
    if pecl_extensions:
        click.echo(f"  Reinstalliere Extensions: {', '.join(pecl_extensions)}")
        from pbrew.cli.ext import ext_cmd, install_cmd as ext_install
        for ext_name in pecl_extensions:
            click.echo(f"    → {ext_name}...")
            ctx.invoke(ext_install, ext_name=ext_name, version_spec=family)

    # Symlinks aktualisieren
    from pbrew.cli.install import _update_wrappers
    _update_wrappers(prefix, latest.version, family)

    # FPM neustarten
    try:
        from pbrew.cli.fpm import fpm_cmd, restart_cmd
        suffix = family.replace(".", "")
        ctx.invoke(restart_cmd, target=suffix)
    except Exception as exc:
        click.echo(f"  FPM-Restart fehlgeschlagen: {exc}", err=True)

    # Health-Check
    from pbrew.core.config import load_config
    from pbrew.core.paths import configs_dir
    from pbrew.utils.health import run_basic_checks
    config = load_config(configs_dir(prefix), family)
    results = run_basic_checks(prefix, latest.version, family, config)
    for r in results:
        icon = "✓" if r.ok else "✗"
        click.echo(f"    {icon} {r.name}" + (f" — {r.message}" if r.message else ""))

    # Alte Versionen bereinigen
    _offer_cleanup(prefix, family, current, latest.version)


def _check_ini_diff(prefix: Path, version: str, family: str) -> None:
    """Vergleicht neue php.ini-production mit bestehender php.ini (apt-Stil)."""
    new_production = version_dir(prefix, version) / "lib" / "php.ini-production"
    existing_ini = cli_ini_dir(prefix, family) / "php.ini"
    if not new_production.exists() or not existing_ini.exists():
        return

    old_lines = existing_ini.read_text().splitlines(keepends=True)
    new_lines = new_production.read_text().splitlines(keepends=True)
    diff = list(difflib.unified_diff(old_lines, new_lines,
                                     fromfile="php.ini (aktuell)",
                                     tofile="php.ini-production (neu)"))
    if not diff:
        return

    changed_lines = [l for l in diff if l.startswith("+") or l.startswith("-")]
    click.echo(f"\n  php.ini-production hat {len(changed_lines)} Änderungen gegenüber der aktuellen php.ini.")

    while True:
        choice = click.prompt(
            "  [J]a übernehmen (alte als .bak) / [N]ein behalten (neue als .dist) / [D]iff anzeigen",
            default="N",
        ).upper()
        if choice == "D":
            click.echo("".join(diff))
            continue
        if choice == "J":
            existing_ini.rename(existing_ini.with_suffix(".ini.bak"))
            shutil.copy2(new_production, existing_ini)
            click.echo("  → Neue php.ini übernommen (alte als .bak gesichert).")
        else:
            shutil.copy2(new_production, existing_ini.with_suffix(".ini.dist"))
            click.echo("  → Neue php.ini als .dist abgelegt, bestehende behalten.")
        break


def _offer_cleanup(prefix: Path, family: str, current: str, new: str) -> None:
    """Fragt nach dem Bereinigen älterer Versionen."""
    vdir = versions_dir(prefix)
    old_versions = sorted(
        [e.name for e in vdir.iterdir()
         if e.is_dir() and e.name.startswith(family + ".") and e.name not in (current, new)],
    )
    if not old_versions and current == new:
        return

    to_show = [current] + old_versions
    click.echo(f"\n  Alte Versionen:")
    for v in to_show:
        mb = sum(f.stat().st_size for f in (vdir / v).rglob("*") if f.is_file()) / 1_048_576
        click.echo(f"    {v} — {mb:.0f} MB")

    if not to_show:
        return

    choice = click.prompt(
        "  [B]ehalten / [V]orherige behalten, ältere löschen / [A]lle löschen",
        default="B",
    ).upper()

    if choice == "A":
        for v in to_show:
            import shutil
            shutil.rmtree(vdir / v)
            click.echo(f"  ✗ {v} entfernt.")
    elif choice == "V":
        for v in old_versions:
            import shutil
            shutil.rmtree(vdir / v)
            click.echo(f"  ✗ {v} entfernt.")
        click.echo(f"  ✓ {current} behalten (Rollback möglich).")


def _switch_to_version(prefix: Path, family: str, version: str) -> None:
    """Aktualisiert Wrapper und FPM-Services auf eine andere Patch-Version."""
    from pbrew.cli.install import _update_wrappers
    from pbrew.core.state import set_active_version
    from pbrew.core.paths import state_file as sf_path

    _update_wrappers(prefix, version, family)
    set_active_version(sf_path(prefix, family), version)

    try:
        from pbrew.fpm.services import write_service, reload_systemd
        from pbrew.core.config import load_config
        from pbrew.core.paths import configs_dir
        config = load_config(configs_dir(prefix), family)
        xdebug = config.get("xdebug", {}).get("enabled", False)
        for debug in ([False, True] if xdebug else [False]):
            write_service(prefix, version, family, debug)
        reload_systemd()
        suffix = family.replace(".", "")
        import subprocess
        subprocess.run(["sudo", "systemctl", "restart", f"php{suffix}-fpm"], check=True)
    except Exception as exc:
        click.echo(f"  FPM-Update fehlgeschlagen: {exc}", err=True)
```

- [ ] **Schritt 2: Commands registrieren**

In `pbrew/cli/__init__.py` ergänzen:

```python
from pbrew.cli.upgrade import upgrade_cmd, rollback_cmd
# ...
main.add_command(upgrade_cmd, name="upgrade")
main.add_command(rollback_cmd, name="rollback")
```

- [ ] **Schritt 3: Smoke-Test**

```bash
pbrew upgrade --help
pbrew rollback --help
```

- [ ] **Schritt 4: Commit**

```bash
git add pbrew/cli/upgrade.py pbrew/cli/__init__.py
git commit -m "Füge pbrew-upgrade und pbrew-rollback hinzu"
```

---

## Task 5: `pbrew config` und `pbrew info`

**Files:**
- Create: `pbrew/cli/config_.py`
- Create: `pbrew/cli/info.py`
- Modify: `pbrew/cli/__init__.py`

- [ ] **Schritt 1: `pbrew/cli/config_.py` implementieren**

```python
import os
import subprocess
from pathlib import Path

import click

from pbrew.core.config import load_config
from pbrew.core.paths import configs_dir, family_from_version


@click.group("config")
def config_cmd():
    """Build-Config verwalten."""


@config_cmd.command("edit")
@click.argument("version_spec")
@click.option("--named", default=None, help="Benannte Config (z.B. production)")
@click.pass_context
def edit_cmd(ctx, version_spec, named):
    """Öffnet die Config im $EDITOR."""
    prefix: Path = ctx.obj["prefix"]
    family = family_from_version(version_spec)
    name = named or family
    cfgs_dir = configs_dir(prefix)
    cfgs_dir.mkdir(parents=True, exist_ok=True)
    config_file = cfgs_dir / f"{name}.toml"

    if not config_file.exists():
        # Aktuell geladene Config als Vorlage schreiben
        import tomlkit
        config = load_config(cfgs_dir, family, named=named)
        config_file.write_text(tomlkit.dumps(config))

    editor = os.environ.get("EDITOR", "nano")
    subprocess.run([editor, str(config_file)])


@config_cmd.command("show")
@click.argument("version_spec")
@click.option("--named", default=None, help="Benannte Config")
@click.pass_context
def show_cmd(ctx, version_spec, named):
    """Zeigt die aktive Config (nach Cascade-Auflösung)."""
    prefix: Path = ctx.obj["prefix"]
    family = family_from_version(version_spec)
    cfgs_dir = configs_dir(prefix)
    config = load_config(cfgs_dir, family, named=named)

    import tomlkit
    click.echo(f"\n# Aktive Config für PHP {family}" +
               (f" (Variante: {named})" if named else ""))
    click.echo(tomlkit.dumps(config))
```

- [ ] **Schritt 2: `pbrew/cli/info.py` implementieren**

```python
from pathlib import Path

import click

from pbrew.core.paths import (
    bin_dir, cli_ini_dir, confd_dir, family_from_version,
    state_file, version_dir,
)
from pbrew.core.state import get_family_state


@click.command("info")
@click.argument("version_spec", required=False)
@click.pass_context
def info_cmd(ctx, version_spec):
    """Zeigt Build-Details, Pfade und Extensions einer PHP-Version."""
    prefix: Path = ctx.obj["prefix"]

    if version_spec:
        family = family_from_version(version_spec)
    else:
        import os
        env = os.environ.get("PBREW_PHP")
        if env:
            family = family_from_version(env)
        else:
            from pbrew.core.state import get_global_state
            from pbrew.core.paths import global_state_file
            state = get_global_state(global_state_file(prefix))
            family = state.get("default_family")
            if not family:
                click.echo("Keine aktive PHP-Version.", err=True)
                raise SystemExit(1)

    sf = state_file(prefix, family)
    state = get_family_state(sf)
    version = state.get("active", "—")
    previous = state.get("previous", "—")
    config_name = state.get("config", "default")
    extensions = state.get("extensions", [])

    suffix = family.replace(".", "")
    vdir = version_dir(prefix, version)

    click.echo(f"\nPHP {family}")
    click.echo(f"  Aktive Version:   {version}")
    click.echo(f"  Vorherige:        {previous}")
    click.echo(f"  Build-Config:     {config_name}")
    click.echo(f"\nPfade:")
    click.echo(f"  Installations-Dir: {vdir}")
    click.echo(f"  Binary:            {bin_dir(prefix) / f'php{suffix}'}")
    click.echo(f"  php.ini (CLI):     {cli_ini_dir(prefix, family) / 'php.ini'}")
    click.echo(f"  scan-dir:          {confd_dir(prefix, family)}")
    click.echo(f"\nBuild-Details:")
    inst = state.get("installed", {}).get(version, {})
    click.echo(f"  Installiert:       {inst.get('installed_at', '—')}")
    duration = inst.get("build_duration_seconds")
    click.echo(f"  Build-Dauer:       {duration}s" if duration else "  Build-Dauer:       —")
    click.echo(f"\nPECL-Extensions:   {', '.join(extensions) if extensions else '—'}")

    # INI-Dateien aus scan-dir
    scan = confd_dir(prefix, family)
    if scan.exists():
        inis = sorted(scan.glob("*.ini"))
        click.echo(f"\nAktive INIs in {scan}:")
        for ini in inis:
            click.echo(f"  {ini.name}")
    click.echo()
```

- [ ] **Schritt 3: Commands registrieren**

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
from pbrew.cli.fpm import fpm_cmd
from pbrew.cli.ext import ext_cmd
from pbrew.cli.upgrade import upgrade_cmd, rollback_cmd
from pbrew.cli.config_ import config_cmd
from pbrew.cli.info import info_cmd


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
main.add_command(fpm_cmd, name="fpm")
main.add_command(ext_cmd, name="ext")
main.add_command(upgrade_cmd, name="upgrade")
main.add_command(rollback_cmd, name="rollback")
main.add_command(config_cmd, name="config")
main.add_command(info_cmd, name="info")
```

- [ ] **Schritt 4: Alle Commands smoke-testen**

```bash
pbrew --help
```

Erwartete Ausgabe zeigt alle Commands:
```
Commands:
  clean      Entfernt eine alte PHP-Patch-Version ...
  config     Build-Config verwalten.
  doctor     Systemweite Prüfung ...
  ext        PHP-Extensions verwalten.
  fpm        FPM-Services und Pools verwalten.
  info       Zeigt Build-Details, Pfade und Extensions ...
  install    PHP aus dem Quellcode bauen ...
  known      Listet verfügbare PHP-Versionen ...
  list       Zeigt alle installierten PHP-Versionen.
  log        Zeigt das Build-Log ...
  rollback   Wechselt auf die vorherige Patch-Version zurück.
  shell-init Gibt Shell-Integration aus ...
  switch     Setzt PHP-Version permanent als Default.
  upgrade    Aktualisiert PHP-Versionen ...
  use        Setzt PHP-Version für die aktuelle Shell-Session ...
```

- [ ] **Schritt 5: Alle Tests ausführen**

```bash
pytest -v
```

Erwartete Ausgabe: Alle Tests PASSED

- [ ] **Schritt 6: Commit + Tag**

```bash
git add pbrew/cli/config_.py pbrew/cli/info.py pbrew/cli/__init__.py
git commit -m "Füge config/info-Commands hinzu — alle Commands implementiert"
git tag v0.3.0
```

---

## Self-Review

**Spec-Coverage:**

| Spec-Abschnitt | Task |
|---|---|
| Extension-Management: PECL-API | Task 1 |
| Extension-Installer (phpize/make) | Task 2 |
| INI-Management (nie überschreiben) | Task 2 |
| `pbrew ext install/remove/enable/disable/list` | Task 3 |
| Upgrade-Workflow | Task 4 |
| Config-Diff à la apt (J/N/D) | Task 4 (`_check_ini_diff`) |
| Cleanup alter Versionen nach Upgrade | Task 4 (`_offer_cleanup`) |
| Rollback | Task 4 |
| Extension-Reinstallation bei Upgrade | Task 4 |
| `pbrew config edit/show` | Task 5 |
| `pbrew info` | Task 5 |

**Nicht in diesem Plan (Backlog v2):**
- `pbrew ext list --available` (PECL-Suche)
- `pbrew migrate-from-phpbrew`
- `pbrew backup/restore`
- `pbrew watch` (Cron-Checker)
- Nginx-Snippets
- Build-Cache
