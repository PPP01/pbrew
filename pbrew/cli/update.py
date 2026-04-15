from pathlib import Path

import click

from pbrew.core.paths import family_from_version, state_file
from pbrew.core.resolver import fetch_latest
from pbrew.core.state import get_family_state
from pbrew.cli.install import install_cmd


@click.command("update")
@click.argument("version_spec")
@click.pass_context
def update_cmd(ctx, version_spec):
    """Aktualisiert eine PHP-Family auf die neueste Version."""
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

    click.echo(f"  Aktuell: {active}  →  Neu: {release.version}")
    ctx.invoke(install_cmd, version_spec=release.version, config_name=None, save=False, jobs=None)
