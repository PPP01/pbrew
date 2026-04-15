import glob
import subprocess
import time
from pathlib import Path

import click

from pbrew.core.paths import family_from_version, versions_dir
from pbrew.fpm.pools import pool_config_path, write_pool_config
from pbrew.fpm.services import service_name, service_path, write_service, reload_systemd
from pbrew.fpm.xdebug import create_debug_wrapper, create_xdebug_ini


@click.group("fpm")
def fpm_cmd():
    """FPM-Services und Pools verwalten."""


# ── status ────────────────────────────────────────────────────────────────────

@fpm_cmd.command("status")
@click.pass_context
def status_cmd(ctx):
    """Zeigt Status aller FPM-Services."""
    prefix: Path = ctx.obj["prefix"]
    vdir = versions_dir(prefix)
    if not vdir.exists():
        click.echo("Keine PHP-Versionen installiert.")
        return

    families = _installed_families(vdir)
    if not families:
        click.echo("Keine Families gefunden.")
        return

    click.echo()
    for family in sorted(families):
        for debug in (False, True):
            sname = service_name(family, debug)
            spath = service_path(family, debug)
            if not spath.exists():
                continue
            status = _systemctl_is_active(sname)
            icon = "✓" if status == "active" else "✗"
            click.echo(f"  {icon} {sname}: {status}")
    click.echo()


# ── restart ───────────────────────────────────────────────────────────────────

@fpm_cmd.command("restart")
@click.argument("target")
@click.pass_context
def restart_cmd(ctx, target):
    """Startet FPM-Service neu. TARGET: '84', '84d', oder 'all'."""
    prefix: Path = ctx.obj["prefix"]

    if target == "all":
        vdir = versions_dir(prefix)
        for family in sorted(_installed_families(vdir)):
            for debug in (False, True):
                sname = service_name(family, debug)
                if service_path(family, debug).exists():
                    _restart_service(sname, prefix, family, debug)
        return

    debug = target.endswith("d") and not target.replace("d", "").isalpha()
    family_raw = target[:-1] if debug else target
    family = family_from_version(family_raw)
    _restart_service(service_name(family, debug), prefix, family, debug)


# ── pool ──────────────────────────────────────────────────────────────────────

@fpm_cmd.group("pool")
def pool_group():
    """Pool-Configs verwalten."""


@pool_group.command("add")
@click.argument("user")
@click.argument("version_spec")
@click.option("--debug/--no-debug", default=False, help="Debug-Pool anlegen (Xdebug)")
@click.pass_context
def pool_add_cmd(ctx, user, version_spec, debug):
    """Fügt einen FPM-Pool für USER hinzu."""
    prefix: Path = ctx.obj["prefix"]
    family = family_from_version(version_spec)
    path = write_pool_config(prefix, user, family, debug=debug)
    label = "debug" if debug else "normal"
    suffix = family.replace(".", "")
    debug_suffix = "d" if debug else ""
    click.echo(f"✓ Pool '{user}' ({label}) erstellt: {path}")
    click.echo(f"  → pbrew fpm restart {suffix}{debug_suffix} um zu aktivieren")


@pool_group.command("remove")
@click.argument("user")
@click.argument("version_spec")
@click.option("--debug/--no-debug", default=False)
@click.pass_context
def pool_remove_cmd(ctx, user, version_spec, debug):
    """Entfernt einen FPM-Pool."""
    prefix: Path = ctx.obj["prefix"]
    family = family_from_version(version_spec)
    path = pool_config_path(prefix, family, user, debug)
    if not path.exists():
        click.echo(f"Pool '{user}' nicht gefunden: {path}", err=True)
        raise SystemExit(1)
    path.unlink()
    click.echo(f"✓ Pool '{user}' entfernt.")


@pool_group.command("list")
@click.argument("version_spec")
@click.pass_context
def pool_list_cmd(ctx, version_spec):
    """Listet alle Pools einer PHP-Family."""
    prefix: Path = ctx.obj["prefix"]
    family = family_from_version(version_spec)
    found = False
    for debug in (False, True):
        subdir = f"{family}d" if debug else family
        pool_dir = prefix / "etc" / "fpm" / subdir / "php-fpm.d"
        if not pool_dir.exists():
            continue
        label = "debug" if debug else "normal"
        for conf in sorted(pool_dir.glob("*.conf")):
            click.echo(f"  [{label}] {conf.stem}")
            found = True
    if not found:
        click.echo(f"Keine Pools für PHP {family} gefunden.")


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def setup_fpm(prefix: Path, version: str, family: str, xdebug: bool = False) -> None:
    """Wird von 'pbrew install' aufgerufen. Legt Dirs an, generiert Services."""
    for subdir in ([family, f"{family}d"] if xdebug else [family]):
        fpm_dir = prefix / "etc" / "fpm" / subdir
        (fpm_dir / "php-fpm.d").mkdir(parents=True, exist_ok=True)
        conf = fpm_dir / "php-fpm.conf"
        if not conf.exists():
            suffix = family.replace(".", "")
            debug_suffix = "d" if subdir.endswith("d") else ""
            conf.write_text(
                f"; php-fpm.conf — generiert von pbrew\n"
                f"[global]\n"
                f"pid = /run/php/php{suffix}{debug_suffix}-fpm.pid\n"
                f"error_log = /var/log/php{suffix}{debug_suffix}-fpm.log\n"
                f"\n"
                f"[www]\n"
                f"include = {fpm_dir}/php-fpm.d/*.conf\n"
            )

    if xdebug:
        create_debug_wrapper(prefix, version, family)
        create_xdebug_ini(prefix, family)

    try:
        for debug in ([False, True] if xdebug else [False]):
            write_service(prefix, version, family, debug)
        reload_systemd()
        click.echo(f"  → systemd-Services für PHP {family} generiert.")
    except (PermissionError, subprocess.CalledProcessError):
        click.echo(
            f"  Warnung: Keine Root-Rechte für systemd. Services manuell anlegen:\n"
            f"  sudo pbrew fpm setup {family.replace('.', '')}",
            err=True,
        )


def _installed_families(vdir: Path) -> set[str]:
    families: set[str] = set()
    if not vdir.exists():
        return families
    for entry in vdir.iterdir():
        if entry.is_dir():
            parts = entry.name.split(".")
            if len(parts) >= 3:
                families.add(f"{parts[0]}.{parts[1]}")
    return families


def _systemctl_is_active(sname: str) -> str:
    try:
        result = subprocess.run(
            ["systemctl", "is-active", sname],
            capture_output=True, text=True,
        )
        return result.stdout.strip()
    except FileNotFoundError:
        return "systemctl nicht verfügbar"


def _restart_service(sname: str, prefix: Path, family: str, debug: bool) -> None:
    spath = service_path(family, debug)
    if not spath.exists():
        click.echo(f"Service {sname}.service nicht gefunden: {spath}", err=True)
        return
    click.echo(f"  Restarte {sname}...")
    _wait_for_old_sockets_gone(family, debug)
    try:
        subprocess.run(["sudo", "systemctl", "restart", sname], check=True)
    except subprocess.CalledProcessError as exc:
        click.echo(f"  Fehler beim Restart von {sname}: {exc}", err=True)
        return
    if _wait_for_new_sockets(family, debug):
        click.echo(f"  ✓ {sname} gestartet.")
    else:
        click.echo(f"  Warnung: Keine Sockets nach 10s — {sname} möglicherweise nicht bereit.", err=True)


def _wait_for_old_sockets_gone(family: str, debug: bool, timeout: int = 5) -> None:
    suffix = family.replace(".", "")
    debug_suffix = "d" if debug else ""
    pattern = f"/run/php/php{suffix}{debug_suffix}-*.sock"
    for _ in range(timeout):
        if not glob.glob(pattern):
            return
        time.sleep(1)
    for sock in glob.glob(pattern):
        try:
            Path(sock).unlink()
        except OSError:
            pass


def _wait_for_new_sockets(family: str, debug: bool, timeout: int = 10) -> bool:
    suffix = family.replace(".", "")
    debug_suffix = "d" if debug else ""
    pattern = f"/run/php/php{suffix}{debug_suffix}-*.sock"
    for _ in range(timeout):
        if glob.glob(pattern):
            return True
        time.sleep(1)
    return False
