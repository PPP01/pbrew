import subprocess
from pathlib import Path

import click
import questionary
import tomlkit

from pbrew.core.paths import (
    family_from_version, logs_dir, state_file, version_bin,
)
from pbrew.core.state import add_extension, get_family_state
from pbrew.core.wrappers import write_phpd_wrapper
from pbrew.extensions.installer import extract_tarball, install_extension, write_ext_ini
from pbrew.extensions.pecl import fetch_latest_by_stability, fetch_latest_stable, fetch_releases
from pbrew.utils.download import download

# Bekannte Zend-Extensions (brauchen zend_extension= statt extension=)
_ZEND_EXTENSIONS = {"xdebug", "opcache", "ioncube_loader"}

# Extensions die nur in phpd (Debug-Scan-Dir) geladen werden sollen, nicht in php
_DEBUG_EXTENSIONS = {"xdebug"}

# Kuratierte Liste populärer PECL-Extensions als Vorauswahl in `ext add`.
_PECL_SUGGESTIONS: frozenset[str] = frozenset({
    "apcu", "ast", "ds", "event", "grpc", "igbinary", "imagick",
    "mailparse", "memcache", "memcached", "mongodb", "msgpack",
    "oauth", "protobuf", "rdkafka", "redis", "swoole", "uuid",
    "uopz", "xdebug", "yaml", "zstd",
})


@click.group("ext")
def ext_cmd():
    """PHP-Extensions verwalten."""


@ext_cmd.command("install")
@click.argument("ext_name", metavar="EXT[@VERSION]")
@click.argument("version_spec", required=False, metavar="[PHP-VERSION]")
@click.option("-v", "--version", "ext_version", default=None, help="Exakte Extension-Version")
@click.option("-j", "--jobs", type=int, default=None, help="Parallele Build-Jobs")
@click.pass_context
def install_ext_cmd(ctx, ext_name, version_spec, ext_version, jobs):
    """Installiert eine PECL-Extension für die aktive (oder angegebene) PHP-Version.

    EXT[@VERSION] – Name der Extension, optional mit Version oder Stabilitätsstufe:

    \b
      pbrew ext install xdebug            # neueste stabile Version
      pbrew ext install xdebug@beta       # neueste Beta-Version
      pbrew ext install xdebug@alpha      # neueste Alpha-Version
      pbrew ext install xdebug@3.4.0      # exakte Version
      pbrew ext install xdebug 84         # für PHP 8.4
    """
    if "@" in ext_name:
        ext_name, at_version = ext_name.split("@", 1)
        if at_version and not ext_version:
            ext_version = at_version

    _STABILITY_KEYWORDS = {"latest", "stable", "beta", "alpha"}
    stability_request = None
    if ext_version and ext_version.lower() in _STABILITY_KEYWORDS:
        kw = ext_version.lower()
        stability_request = "stable" if kw in {"latest", "stable"} else kw
        ext_version = None

    prefix: Path = ctx.obj["prefix"]
    family = _resolve_family(prefix, version_spec)
    php_version = _resolve_active_version(prefix, family)

    click.echo(f"Installiere {ext_name} für PHP {php_version}...")

    try:
        if ext_version:
            releases = fetch_releases(ext_name)
            release = next((r for r in releases if r.version == ext_version), None)
            if not release:
                click.echo(f"  Version {ext_version} nicht gefunden.", err=True)
                raise SystemExit(1)
        elif stability_request and stability_request != "stable":
            click.echo(f"  Suche neueste {stability_request}-Version von {ext_name}...")
            release = fetch_latest_by_stability(ext_name, stability_request)
            click.echo(f"  Neueste {stability_request}-Version: {release.version}")
        else:
            click.echo(f"  Suche neueste stabile Version von {ext_name}...")
            release = fetch_latest_stable(ext_name)
            click.echo(f"  Neueste stabile Version: {release.version}")
    except RuntimeError as e:
        click.echo(f"  Fehler: {e}", err=True)
        raise SystemExit(1)

    dist_dir = prefix / "distfiles"
    dist_dir.mkdir(parents=True, exist_ok=True)
    tarball = dist_dir / f"{ext_name}-{release.version}.tgz"
    if not tarball.exists():
        click.echo(f"  Lade {ext_name}-{release.version}.tgz herunter...")
        download(release.tarball_url, tarball)

    build_dir = prefix / "build" / php_version / f"{ext_name}-{release.version}"
    if not build_dir.exists():
        src_dir = extract_tarball(tarball, build_dir.parent)
        if src_dir != build_dir:
            src_dir.rename(build_dir)

    from pbrew.core.builder import get_jobs
    from pbrew.core.config import load_config
    from pbrew.core.paths import configs_dir
    config = load_config(configs_dir(prefix), family)
    num_jobs = get_jobs(config, override=jobs)

    _logs = logs_dir(prefix)
    _logs.mkdir(parents=True, exist_ok=True)
    log_path = _logs / f"{ext_name}-{release.version}-{php_version}.log"

    click.echo(f"  Baue {ext_name} {release.version}...")
    with open(log_path, "w") as log:
        try:
            install_extension(prefix, php_version, ext_name, build_dir, num_jobs, log)
        except Exception as exc:
            click.echo(f"  Fehler beim Build. Log: {log_path}", err=True)
            click.echo(f"  {exc}", err=True)
            raise SystemExit(1)

    is_zend = ext_name.lower() in _ZEND_EXTENSIONS
    is_debug = ext_name.lower() in _DEBUG_EXTENSIONS
    ini = write_ext_ini(prefix, family, ext_name, is_zend=is_zend, debug=is_debug)
    click.echo(f"  INI: {ini}")

    sf = state_file(prefix, family)
    add_extension(sf, ext_name)

    write_phpd_wrapper(prefix, php_version)

    click.echo(f"✓ {ext_name} {release.version} installiert.")


@ext_cmd.command("remove")
@click.argument("ext_name")
@click.argument("version_spec", required=False)
@click.pass_context
def remove_ext_cmd(ctx, ext_name, version_spec):
    """Deaktiviert eine Extension (verschiebt INI zu .disabled)."""
    prefix: Path = ctx.obj["prefix"]
    family = _resolve_family(prefix, version_spec)
    ini = prefix / "etc" / "conf.d" / family / f"{ext_name}.ini"
    if not ini.exists():
        click.echo(f"{ext_name}.ini nicht gefunden für PHP {family}.", err=True)
        raise SystemExit(1)
    disabled = ini.with_suffix(".ini.disabled")
    ini.rename(disabled)
    if ext_name.lower() == "xdebug":
        php_version = _resolve_active_version(prefix, family)
        write_phpd_wrapper(prefix, php_version)
    click.echo(f"✓ {ext_name} deaktiviert (INI: {disabled})")


@ext_cmd.command("enable")
@click.argument("ext_name")
@click.argument("version_spec", required=False)
@click.pass_context
def enable_ext_cmd(ctx, ext_name, version_spec):
    """Aktiviert eine deaktivierte Extension."""
    prefix: Path = ctx.obj["prefix"]
    family = _resolve_family(prefix, version_spec)
    confd = prefix / "etc" / "conf.d" / family
    disabled = confd / f"{ext_name}.ini.disabled"
    ini = confd / f"{ext_name}.ini"
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
def disable_ext_cmd(ctx, ext_name, version_spec):
    """Deaktiviert eine Extension (Alias für remove ohne State-Änderung)."""
    prefix: Path = ctx.obj["prefix"]
    family = _resolve_family(prefix, version_spec)
    ini = prefix / "etc" / "conf.d" / family / f"{ext_name}.ini"
    if not ini.exists():
        click.echo(f"{ext_name} ist bereits deaktiviert oder nicht installiert.")
        return
    ini.rename(ini.with_suffix(".ini.disabled"))
    click.echo(f"✓ {ext_name} deaktiviert.")


@ext_cmd.command("installed")
@click.argument("version_spec", required=False)
@click.pass_context
def installed_ext_cmd(ctx, version_spec):
    """Zeigt nur pbrew-verwaltete Extensions (aktiv und inaktiv)."""
    prefix: Path = ctx.obj["prefix"]
    family = _resolve_family(prefix, version_spec)
    confd = prefix / "etc" / "conf.d" / family
    if not confd.exists():
        click.echo(f"Kein scan-dir für PHP {family} gefunden.")
        return
    click.echo(f"\nPbrew-Extensions für PHP {family}:")
    for ini in sorted(confd.glob("*.ini")):
        if ini.stem != "00-base":
            click.echo(f"  [aktiv]    {ini.stem}")
    for ini in sorted(confd.glob("*.ini.disabled")):
        name = ini.name.removesuffix(".ini.disabled")
        click.echo(f"  [inaktiv]  {name}")
    click.echo()


@ext_cmd.command("list")
@click.argument("version_spec", required=False)
@click.pass_context
def list_ext_cmd(ctx, version_spec):
    """Vollständige Extension-Übersicht: geladen, verfügbar und Standard."""
    prefix: Path = ctx.obj["prefix"]
    family = _resolve_family(prefix, version_spec)
    php_version = _resolve_active_version(prefix, family)
    php_bin = version_bin(prefix, php_version, "php")

    if not php_bin.exists():
        click.echo(f"PHP-Binary nicht gefunden: {php_bin}", err=True)
        raise SystemExit(1)

    confd = prefix / "etc" / "conf.d" / family
    pbrew_active: set[str] = set()
    pbrew_disabled: set[str] = set()
    if confd.exists():
        for ini in confd.glob("*.ini"):
            if ini.stem != "00-base":
                pbrew_active.add(ini.stem.lower())
        for ini in confd.glob("*.ini.disabled"):
            pbrew_disabled.add(ini.name.removesuffix(".ini.disabled").lower())

    loaded, local, standard = _query_extensions(php_bin)

    col_width = max((len(name) for _, (name, _) in loaded.items()), default=10) + 2

    click.echo(f"\nExtensions für PHP {family}:\n")
    click.echo("Loaded extensions:")
    for _, (name, version) in sorted(loaded.items()):
        marker = "  [pbrew]" if name.lower() in pbrew_active else ""
        click.echo(f" [*] {name:<{col_width}} {version}{marker}")

    if local or pbrew_disabled:
        click.echo("Available local extensions:")
        shown_lower: set[str] = set()
        for name in local:
            shown_lower.add(name.lower())
            if name.lower() in pbrew_disabled:
                click.echo(f" [-] {name:<{col_width}}  [pbrew, inaktiv]")
            else:
                click.echo(f" [ ] {name}")
        for name in sorted(pbrew_disabled - shown_lower):
            click.echo(f" [-] {name:<{col_width}}  [pbrew, inaktiv]")

    if standard:
        click.echo("Standard extensions (not compiled):")
        for name in standard:
            click.echo(f" [ ] {name}")


# Vollständige Liste der Standard-PHP-Extensions (alle PHP-Versionen ≥ 7.4)
_STANDARD_EXTENSIONS: frozenset[str] = frozenset({
    "bcmath", "bz2", "calendar", "ctype", "curl", "date", "dba", "dom",
    "enchant", "exif", "ffi", "fileinfo", "filter", "ftp", "gd", "gettext",
    "gmp", "hash", "iconv", "intl", "json", "ldap", "libxml", "mbstring",
    "mysqli", "mysqlnd", "odbc", "opcache", "openssl", "pcntl", "pcre",
    "pdo", "pdo_dblib", "pdo_firebird", "pdo_mysql", "pdo_odbc", "pdo_pgsql",
    "pdo_sqlite", "pgsql", "phar", "posix", "random", "readline", "reflection",
    "session", "shmop", "simplexml", "snmp", "soap", "sockets", "sodium",
    "spl", "sqlite3", "standard", "sysvmsg", "sysvsem", "sysvshm", "tidy",
    "tokenizer", "xml", "xmlreader", "xmlwriter", "xsl", "zip", "zlib",
})


def _query_extensions(
    php_bin: Path,
) -> tuple[dict[str, tuple[str, str]], list[str], list[str]]:
    """Fragt geladene und verfügbare Extensions per PHP-Binary ab.

    Returns:
        loaded:    {lowercase_name: (original_name, version_string)}
        local:     Namen von .so-Dateien im extension_dir, die nicht geladen sind
        standard:  Standard-Extensions, die weder geladen noch als .so vorhanden sind
    """
    script = (
        "foreach(get_loaded_extensions() as $e){"
        "$v=phpversion($e);echo $e.'|'.($v?:'').PHP_EOL;}"
    )
    r = subprocess.run([str(php_bin), "-r", script], capture_output=True, text=True, timeout=10)
    loaded: dict[str, tuple[str, str]] = {}
    for line in r.stdout.splitlines():
        if "|" in line:
            name, version = line.split("|", 1)
            loaded[name.lower()] = (name, version)

    r2 = subprocess.run(
        [str(php_bin), "-r", "echo ini_get('extension_dir');"],
        capture_output=True, text=True, timeout=10,
    )
    ext_dir = Path(r2.stdout.strip())

    local: list[str] = []
    local_lower: set[str] = set()
    if ext_dir.is_dir():
        for so in sorted(ext_dir.glob("*.so")):
            if so.stem.lower() not in loaded:
                local.append(so.stem)
                local_lower.add(so.stem.lower())

    standard = sorted(
        name for name in _STANDARD_EXTENSIONS
        if name not in loaded and name not in local_lower
    )

    return loaded, local, standard


def _collect_add_candidates(
    *,
    loaded: dict[str, tuple[str, str]],
    local: list[str],
    standard: list[str],
    pbrew_active: set[str],
    active_variants: set[str],
) -> tuple[list[str], list[str], list[str]]:
    from pbrew.core.builder import VARIANT_EXTENSIONS

    local_candidates = [n for n in local if n.lower() not in pbrew_active]

    known = {n.lower() for n in loaded}
    known |= {n.lower() for n in local}
    known |= {n.lower() for n in standard}
    pecl_candidates = sorted(
        n for n in _PECL_SUGGESTIONS if n.lower() not in known
    )

    rebuild_candidates = sorted(
        n for n in standard
        if n in VARIANT_EXTENSIONS and n not in active_variants
    )
    return local_candidates, pecl_candidates, rebuild_candidates


def _update_config_variants(config_path: Path, variants: list[str]) -> list[str]:
    """Fügt Variants additiv in eine Config-Datei ein. Erzeugt die Datei wenn nötig."""
    if config_path.exists():
        doc = tomlkit.loads(config_path.read_text())
    else:
        doc = tomlkit.document()
    build = doc.setdefault("build", tomlkit.table())
    current = list(build.get("variants", ["default"]))
    added: list[str] = []
    for v in variants:
        if v not in current:
            current.append(v)
            added.append(v)
    build["variants"] = current
    config_path.write_text(tomlkit.dumps(doc))
    return added


def _remove_config_variants(config_path: Path, variants: list[str]) -> list[str]:
    """Entfernt Variants aus einer Config-Datei. Datei muss existieren."""
    doc = tomlkit.loads(config_path.read_text())
    build = doc.get("build")
    if build is None or "variants" not in build:
        return []
    current = list(build["variants"])
    removed: list[str] = []
    for v in variants:
        if v in current:
            current.remove(v)
            removed.append(v)
    build["variants"] = current
    config_path.write_text(tomlkit.dumps(doc))
    return removed


def _prompt_config_choice(configs_dir: Path, active_family: str) -> "Path | None":
    """Fragt nach der Ziel-Config. Gibt None bei Abbruch zurück."""
    existing = sorted(p.name for p in configs_dir.glob("*.toml"))
    choices = existing + ["<neu>"]
    label = (
        f"In welche Config sollen die Variants fuer PHP {active_family} "
        f"eingetragen werden?"
    )
    pick = questionary.select(label, choices=choices).ask()
    if pick is None:
        return None
    if pick == "<neu>":
        name = questionary.text(
            "Name der neuen Config (a-z, 0-9, _ und -):"
        ).ask()
        if not name:
            return None
        import re
        if not re.fullmatch(r"[a-zA-Z0-9_\-]+", name):
            click.echo(f"Ungueltiger Name: {name!r}", err=True)
            return None
        return configs_dir / f"{name}.toml"
    return configs_dir / pick


def _resolve_family(prefix: Path, version_spec: "str | None") -> str:
    if version_spec:
        return family_from_version(version_spec)
    import os
    env = os.environ.get("PBREW_ACTIVE") or os.environ.get("PBREW_PHP")
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
