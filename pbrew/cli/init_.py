from pathlib import Path

import click

from pbrew.core.global_config import global_config_file, write_prefix
from pbrew.core.paths import (
    bin_dir,
    distfiles_dir,
    etc_dir,
    get_prefix,
    state_dir,
    versions_dir,
)


@click.command("init")
def init_cmd():
    """Richtet pbrew ein: Prefix wählen und Verzeichnisse anlegen."""
    current_default = get_prefix()

    chosen = click.prompt("Installationspräfix", default=str(current_default))
    prefix = Path(chosen).expanduser().resolve()

    click.echo(f"\nRichte pbrew unter {prefix} ein...\n")

    dirs = [
        versions_dir(prefix),
        bin_dir(prefix),
        etc_dir(prefix),
        distfiles_dir(prefix),
        state_dir(prefix),
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        click.echo(f"  ✓ {d.relative_to(prefix)}/")

    write_prefix(prefix)
    click.echo(f"\nKonfiguration gespeichert: {global_config_file()}")
    click.echo("\npbrew ist eingerichtet. Weiter mit:")
    click.echo("  pbrew doctor        — Build-Voraussetzungen prüfen")
    click.echo("  pbrew known         — Verfügbare PHP-Versionen anzeigen")
    click.echo("  pbrew install 8.4   — PHP 8.4 installieren")
