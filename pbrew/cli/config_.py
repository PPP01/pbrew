import os
import subprocess
from pathlib import Path

import click
import tomlkit

from pbrew.core.config import load_config
from pbrew.core.paths import configs_dir, family_from_version


@click.group("config")
def config_cmd():
    """Build-Config verwalten."""


@config_cmd.command("edit")
@click.argument("version_spec")
@click.option("--named", default=None, help="Benannte Config (z.B. production)")
@click.pass_context
def edit_cmd(ctx, version_spec, named):
    """Öffnet die Config im $EDITOR (Default: nano)."""
    prefix: Path = ctx.obj["prefix"]
    family = family_from_version(version_spec)
    name = named or family
    cfgs_dir = configs_dir(prefix)
    cfgs_dir.mkdir(parents=True, exist_ok=True)
    config_file = cfgs_dir / f"{name}.toml"

    if not config_file.exists():
        # Aktuell geladene (ge-merg-te) Config als Startvorlage schreiben
        current = load_config(cfgs_dir, family, named=named)
        config_file.write_text(tomlkit.dumps(current))
        click.echo(f"  Vorlage erstellt: {config_file}")

    editor = os.environ.get("EDITOR", "nano")
    subprocess.run([editor, str(config_file)])


@config_cmd.command("show")
@click.argument("version_spec")
@click.option("--named", default=None, help="Benannte Config")
@click.pass_context
def show_cmd(ctx, version_spec, named):
    """Zeigt die aktive Config (nach Cascade-Auflösung)."""
    prefix: Path = ctx.obj["prefix"]
    family = family_from_version(version_spec)
    cfgs_dir = configs_dir(prefix)
    config = load_config(cfgs_dir, family, named=named)

    click.echo(f"\n# Aktive Config für PHP {family}" +
               (f" (Variante: {named})" if named else ""))
    click.echo(tomlkit.dumps(config))
