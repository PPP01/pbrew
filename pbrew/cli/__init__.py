import re
import click
from pbrew.cli.install import install_cmd
from pbrew.cli.list_ import list_cmd
from pbrew.cli.use import use_cmd, switch_cmd, unswitch_cmd
from pbrew.cli.known import known_cmd
from pbrew.cli.clean import clean_cmd
from pbrew.cli.remove import remove_cmd
from pbrew.cli.log_ import log_cmd
from pbrew.cli.shell_init import shell_init_cmd
from pbrew.cli.doctor import doctor_cmd
from pbrew.cli.init_ import init_cmd
from pbrew.cli.cleanup import cleanup_cmd
from pbrew.cli.update import update_cmd
from pbrew.cli.info import info_cmd
from pbrew.cli.env import env_cmd
from pbrew.cli.outdated import outdated_cmd
from pbrew.cli.fpm import fpm_cmd
from pbrew.cli.ext import ext_cmd
from pbrew.cli.upgrade import upgrade_cmd, rollback_cmd
from pbrew.cli.config_ import config_cmd


_VERSION_RE = re.compile(r"^\d{2}$|^\d\.\d+(\.\d+)?$")


class _PbrewGroup(click.Group):
    def resolve_command(self, ctx, args):
        if args and _VERSION_RE.match(args[0]):
            args.insert(0, "use")
        return super().resolve_command(ctx, args)


@click.group(cls=_PbrewGroup, context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(None, "-v", "--version", package_name="pbrew")
@click.option("-p", "--prefix", envvar="PBREW_ROOT", help="pbrew Prefix-Verzeichnis")
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
main.add_command(unswitch_cmd, name="unswitch")
main.add_command(known_cmd, name="known")
main.add_command(clean_cmd, name="clean")
main.add_command(remove_cmd, name="remove")
main.add_command(log_cmd, name="log")
main.add_command(shell_init_cmd, name="shell-init")
main.add_command(doctor_cmd, name="doctor")
main.add_command(init_cmd, name="init")
main.add_command(cleanup_cmd, name="cleanup")
main.add_command(update_cmd, name="update")
main.add_command(info_cmd, name="info")
main.add_command(env_cmd, name="env")
main.add_command(outdated_cmd, name="outdated")
main.add_command(fpm_cmd, name="fpm")
main.add_command(ext_cmd, name="ext")
main.add_command(upgrade_cmd, name="upgrade")
main.add_command(rollback_cmd, name="rollback")
main.add_command(config_cmd, name="config")
