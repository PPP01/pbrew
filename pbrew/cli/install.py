import shutil
import sys
import tarfile
import time
from pathlib import Path

import click

from pbrew.core import build_libs, builder, config as cfg_mod, resolver, state as state_mod
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
@click.option("--skip-lib-check", is_flag=True, help="Überspringt den Pre-Flight-Check der Build-Libraries")
@click.pass_context
def install_cmd(ctx, version_spec, config_name, save, jobs, skip_lib_check):
    """PHP aus dem Quellcode bauen und installieren."""
    prefix: Path = ctx.obj["prefix"]
    family = family_from_version(version_spec)

    parts = version_spec.split(".")
    if len(parts) == 3 and all(p.isdigit() for p in parts):
        click.echo(f"Prüfe PHP {version_spec} auf php.net...")
        release = resolver.fetch_specific(version_spec)
        version = release.version
        click.echo(f"  Version: {version}")
    else:
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

    if not skip_lib_check:
        _check_build_libraries(config.get("build", {}).get("variants", []))

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

    click.echo(f"\n  Baue PHP {version} mit {num_jobs} Jobs")
    click.echo(f"  Build-Log: {log_path}")
    click.echo(f"  (Live verfolgen: tail -f {log_path})\n")

    start = time.monotonic()
    with open(log_path, "w") as log:
        args = builder.build_configure_args(prefix, version, family, config)
        _run_phase("configure", lambda: builder.run_configure(build_dir, args, log),
                   build_dir, log_path)
        _run_phase(f"make -j{num_jobs}", lambda: builder.run_make(build_dir, num_jobs, log),
                   build_dir, log_path)
        _run_phase("make install", lambda: builder.run_make_install(build_dir, log),
                   build_dir, log_path)

    duration = time.monotonic() - start
    click.echo(f"\n  Build abgeschlossen ({_fmt_duration(duration)})")

    _init_php_ini(prefix, version, family)

    sf = state_file(prefix, family)
    state_mod.record_install(
        sf, version,
        config=config_name or "default",
        duration=duration,
        variants=config.get("build", {}).get("variants"),
    )

    write_versioned_wrappers(prefix, version, family)
    write_naked_wrappers(prefix)

    # FPM-Setup: Pool-Dirs, php-fpm.conf, systemd-Unit (+ Debug-Wrapper wenn xdebug aktiv)
    from pbrew.cli.fpm import setup_fpm
    xdebug_enabled = config.get("xdebug", {}).get("enabled", False)
    setup_fpm(prefix, version, family, xdebug=xdebug_enabled)

    click.echo("  Health-Check...")
    results = run_basic_checks(prefix, version, family, config)
    for r in results:
        icon = "✓" if r.ok else "✗"
        msg = f" — {r.message}" if r.message else ""
        click.echo(f"    {icon} {r.name}{msg}")

    if any(not r.ok for r in results):
        click.echo("  Warnung: Einige Checks fehlgeschlagen. Log: " + str(log_path), err=True)

    click.echo(f"✓ PHP {version} installiert.")


def _check_build_libraries(variants: list[str]) -> None:
    """Pre-Flight-Check: bricht ab, wenn Dev-Libs fehlen, mit Installationshinweis."""
    missing = build_libs.check_required_libs(variants)
    if not missing:
        return

    click.echo("\n  Pre-Flight-Check: fehlende Build-Libraries", err=True)
    for m in missing:
        scope = "Pflicht" if m.variant == "core" else f"für {m.variant}"
        pkg_hint = f" → {m.distro_pkg}" if m.distro_pkg else ""
        click.echo(f"    ✗ {m.name} ({scope}){pkg_hint}", err=True)

    cmd = build_libs.install_command(missing)
    if cmd:
        click.echo(f"\n  Installation:\n    {cmd}", err=True)
    else:
        click.echo(
            "\n  Bitte die Dev-Pakete für die obigen pkg-config-Namen installieren.",
            err=True,
        )
    click.echo("\n  Mit --skip-lib-check kann diese Prüfung übersprungen werden.\n", err=True)
    sys.exit(1)


def _run_phase(name: str, action, build_dir: Path, log_path: Path) -> None:
    """Führt eine Build-Phase aus, misst die Zeit und berichtet Erfolg/Fehler."""
    click.echo(f"  → {name}...", nl=False)
    phase_start = time.monotonic()
    try:
        action()
    except Exception as exc:
        elapsed = time.monotonic() - phase_start
        click.echo(f" ✗ ({_fmt_duration(elapsed)})")
        click.echo(f"\n  Fehler in Phase '{name}' nach {_fmt_duration(elapsed)}", err=True)
        click.echo(f"  Log: {log_path}", err=True)

        errors = _extract_errors_from_log(log_path)
        if errors:
            click.echo("\n  Letzte Fehlerzeilen aus dem Log:", err=True)
            for line in errors:
                click.echo(f"    {line}", err=True)

        click.echo(f"\n  {exc}", err=True)
        shutil.rmtree(build_dir, ignore_errors=True)
        sys.exit(1)
    elapsed = time.monotonic() - phase_start
    click.echo(f" ✓ ({_fmt_duration(elapsed)})")


def _fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes}m {secs}s"


def _extract_errors_from_log(
    log_path: Path,
    max_matches: int = 5,
    context_after: int = 2,
    fallback_tail: int = 15,
) -> list[str]:
    """Extrahiert aussagekräftige Fehlerzeilen aus einem Build-Log.

    Strategie:
    1. Case-insensitive nach 'error:'-Treffern suchen, die letzten `max_matches`
       nehmen und je `context_after` Folgezeilen als Kontext anhängen
    2. Kein Match → die letzten `fallback_tail` Zeilen zurückgeben
    3. Log fehlt oder leer → leere Liste
    """
    if not log_path.exists():
        return []
    try:
        lines = log_path.read_text(errors="replace").splitlines()
    except OSError:
        return []
    if not lines:
        return []

    error_indices = [i for i, line in enumerate(lines) if "error:" in line.lower()]

    if not error_indices:
        return lines[-fallback_tail:]

    selected: list[str] = []
    seen: set[int] = set()
    for idx in error_indices[-max_matches:]:
        for offset in range(context_after + 1):
            i = idx + offset
            if i < len(lines) and i not in seen:
                selected.append(lines[i])
                seen.add(i)
    return selected


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


