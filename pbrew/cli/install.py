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
            tar.extractall(build_dir.parent, filter="data")
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
            shutil.rmtree(build_dir, ignore_errors=True)
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
