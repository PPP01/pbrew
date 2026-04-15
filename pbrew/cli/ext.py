from pathlib import Path

import click

from pbrew.core.paths import (
    family_from_version, logs_dir, state_file,
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
def install_ext_cmd(ctx, ext_name, version_spec, ext_version, jobs):
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

    dist_dir = prefix / "distfiles"
    dist_dir.mkdir(parents=True, exist_ok=True)
    tarball = dist_dir / f"{ext_name}-{release.version}.tgz"
    if not tarball.exists():
        click.echo(f"  Lade {ext_name}-{release.version}.tgz herunter...")
        download(release.tarball_url, tarball)

    build_dir = prefix / "build" / f"{ext_name}-{release.version}"
    if not build_dir.exists():
        src_dir = extract_tarball(tarball, build_dir.parent)
        if src_dir != build_dir:
            src_dir.rename(build_dir)

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

    is_zend = ext_name.lower() in _ZEND_EXTENSIONS
    ini = write_ext_ini(prefix, family, ext_name, is_zend=is_zend)
    click.echo(f"  INI: {ini}")

    sf = state_file(prefix, family)
    add_extension(sf, ext_name)
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


@ext_cmd.command("list")
@click.argument("version_spec", required=False)
@click.pass_context
def list_ext_cmd(ctx, version_spec):
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
        # stem gibt hier "{name}.ini" zurück – das .ini entfernen
        name = ini.name.removesuffix(".ini.disabled")
        click.echo(f"  [inaktiv]  {name}")
    click.echo()


def _resolve_family(prefix: Path, version_spec: "str | None") -> str:
    if version_spec:
        return family_from_version(version_spec)
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
