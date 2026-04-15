from pathlib import Path
import click
from pbrew.core.paths import family_from_version, family_suffix, state_file, global_state_file
from pbrew.core.state import get_family_state, set_global_default


@click.command("use")
@click.argument("version_spec")
@click.pass_context
def use_cmd(ctx, version_spec):
    """Setzt PHP-Version für die aktuelle Shell-Session (via Shell-Funktion)."""
    prefix: Path = ctx.obj["prefix"]
    family = family_from_version(version_spec)
    sf = state_file(prefix, family)
    state = get_family_state(sf)

    if not state.get("active"):
        click.echo(f"PHP {family} ist nicht installiert. Zuerst: pbrew install {family}", err=True)
        raise SystemExit(1)

    click.echo(f"export PBREW_PHP={family}")
    click.echo(f'export PATH="{prefix / "bin"}:$PATH"')
    click.echo("hash -r")


@click.command("switch")
@click.argument("version_spec")
@click.pass_context
def switch_cmd(ctx, version_spec):
    """Setzt PHP-Version permanent als Default."""
    prefix: Path = ctx.obj["prefix"]
    family = family_from_version(version_spec)
    sf = state_file(prefix, family)
    state = get_family_state(sf)

    if not state.get("active"):
        click.echo(f"PHP {family} ist nicht installiert. Zuerst: pbrew install {family}", err=True)
        raise SystemExit(1)

    set_global_default(global_state_file(prefix), family)
    click.echo(f"✓ php{family_suffix(family)} ist jetzt der permanente Default (pbrew switch)")
