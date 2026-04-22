from pathlib import Path

import click

from pbrew.core.paths import family_from_version, state_file
from pbrew.core.resolver import fetch_latest
from pbrew.core.state import get_family_state
from pbrew.cli.install import install_cmd


@click.command("update")
@click.argument("version_spec", metavar="VERSION")
@click.pass_context
def update_cmd(ctx, version_spec):
    """Installiert die neueste Patch-Version einer PHP-Family.

    Baut die neue PHP-Version und aktualisiert die Wrappers (php84 etc.).
    PECL-Extensions werden dabei NICHT neu gebaut – mit installierten
    Extensions (z.B. xdebug) danach `pbrew upgrade` verwenden, das
    Extensions reinstalliert, FPM neustartet und Health-Checks ausführt.

    \b
      pbrew update 84     # PHP 8.4.x → neuestes Patch-Level
      pbrew update 8.3    # PHP 8.3.x → neuestes Patch-Level
    """
    prefix: Path = ctx.obj["prefix"]
    family = family_from_version(version_spec)

    state = get_family_state(state_file(prefix, family))
    active = state.get("active")
    if not active:
        click.echo(
            f"PHP {family} ist nicht installiert. Zuerst: pbrew install {family}",
            err=True,
        )
        raise SystemExit(1)

    click.echo(f"Prüfe verfügbare Versionen für PHP {family}...")
    release = fetch_latest(family)

    if release.version == active:
        click.echo(f"✓ PHP {family} ist bereits aktuell ({active}).")
        return

    config_name = state.get("installed", {}).get(active, {}).get("config_name") or state.get("config")
    if config_name == "default":
        config_name = None

    click.echo(f"  Aktuell: {active}  →  Neu: {release.version}")
    if config_name:
        click.echo(f"  Config:  {config_name}")
    ctx.invoke(install_cmd, version_spec=release.version, config_name=config_name, save=False, jobs=None)
