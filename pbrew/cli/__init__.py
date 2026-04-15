import click
from pbrew.cli.install import install_cmd
from pbrew.cli.list_ import list_cmd
from pbrew.cli.use import use_cmd, switch_cmd
from pbrew.cli.known import known_cmd
from pbrew.cli.clean import clean_cmd
from pbrew.cli.log_ import log_cmd
from pbrew.cli.shell_init import shell_init_cmd
from pbrew.cli.doctor import doctor_cmd


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
main.add_command(list_cmd, name="list")
main.add_command(use_cmd, name="use")
main.add_command(switch_cmd, name="switch")
main.add_command(known_cmd, name="known")
main.add_command(clean_cmd, name="clean")
main.add_command(log_cmd, name="log")
main.add_command(shell_init_cmd, name="shell-init")
main.add_command(doctor_cmd, name="doctor")
