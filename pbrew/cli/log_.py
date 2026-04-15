import subprocess
import sys
from pathlib import Path
import click
from pbrew.core.paths import build_log, family_from_version


@click.command("log")
@click.argument("version_spec")
@click.option("--tail", "-f", is_flag=True, help="Log live verfolgen")
@click.pass_context
def log_cmd(ctx, version_spec, tail):
    """Zeigt das Build-Log einer PHP-Version."""
    prefix: Path = ctx.obj["prefix"]
    family = family_from_version(version_spec)

    from pbrew.core.state import get_family_state
    from pbrew.core.paths import state_file
    sf = state_file(prefix, family)
    state = get_family_state(sf)
    version = state.get("active", version_spec)

    log = build_log(prefix, version)
    if not log.exists():
        click.echo(f"Kein Build-Log für {version} gefunden: {log}", err=True)
        raise SystemExit(1)

    if tail:
        subprocess.run(["tail", "-f", str(log)])
    else:
        click.echo(log.read_text())
