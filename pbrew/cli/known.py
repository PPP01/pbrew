import click
from pbrew.core.resolver import fetch_known


@click.command("known")
@click.option("--major", default=8, show_default=True, help="PHP Major-Version")
def known_cmd(major):
    """Listet verfügbare PHP-Versionen von php.net."""
    releases = fetch_known(major)

    by_family: dict[str, list[str]] = {}
    for r in releases:
        by_family.setdefault(r.family, []).append(r.version)

    for family, versions in sorted(by_family.items(), reverse=True):
        shown = versions[:8]
        rest = "..." if len(versions) > 8 else ""
        click.echo(f"{family}: {', '.join(shown)}{' ...' if rest else ''}")
