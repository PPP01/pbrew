import click
from pbrew.cli.install import install_cmd


@click.group()
@click.option("--prefix", envvar="PBREW_ROOT", help="pbrew Prefix-Verzeichnis")
@click.pass_context
def main(ctx, prefix):
    """pbrew — PHP Version Manager"""
    ctx.ensure_object(dict)
    from pbrew.core.paths import get_prefix
    from pathlib import Path
    ctx.obj["prefix"] = Path(prefix) if prefix else get_prefix()


main.add_command(install_cmd, name="install")
