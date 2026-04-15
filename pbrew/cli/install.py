import shutil
import sys
import tarfile
import time
from pathlib import Path

import click

from pbrew.core import builder, config as cfg_mod, resolver, state as state_mod
from pbrew.core.paths import (
    build_log, cli_ini_dir, configs_dir, distfiles_dir,
    confd_dir, family_from_version, fpm_ini_dir, logs_dir,
    state_file, version_dir,
)
from pbrew.core.wrappers import write_naked_wrappers, write_versioned_wrappers
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

    cfgs_dir = configs_dir(prefix)
    cfg_mod.init_default_config(cfgs_dir)
    config = cfg_mod.load_config(cfgs_dir, family, named=config_name)
    num_jobs = builder.get_jobs(config, override=jobs)

    if save and config_name:
        cfg_mod.save_config(cfgs_dir, config_name, config)
        click.echo(f"  Config als '{config_name}' gespeichert.")

    dist_dir = distfiles_dir(prefix)
    tarball = dist_dir / f"php-{version}.tar.bz2"
    if not tarball.exists():
        click.echo(f"  Lade php-{version}.tar.bz2 herunter...")
        dl_mod.download(release.tarball_url, tarball, expected_sha256=release.sha256)
    else:
        click.echo(f"  Nutze gecachten Tarball: {tarball}")

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

    log_path = build_log(prefix, version)
    logs_dir(prefix).mkdir(parents=True, exist_ok=True)
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

    _init_php_ini(prefix, version, family)

    sf = state_file(prefix, family)
    state_mod.record_install(
        sf, version,
        config=config_name or "default",
        duration=duration,
        variants=config.get("build", {}).get("variants"),
    )

    write_versioned_wrappers(prefix, version, family)
    if not (prefix / "bin" / "php").exists():
        write_naked_wrappers(prefix, version, family)

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
    for dest_dir in (cli_ini_dir(prefix, family), fpm_ini_dir(prefix, family)):
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


