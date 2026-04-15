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
