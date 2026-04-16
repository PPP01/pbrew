from pathlib import Path
import click
from pbrew.core.paths import family_from_version, family_suffix, state_file, global_state_file, version_dir
from pbrew.core.state import get_family_state, set_active_version, set_global_default
from pbrew.core.wrappers import write_naked_wrappers, write_versioned_wrappers


def _is_pinned(version_spec: str) -> bool:
    parts = version_spec.split(".")
    return len(parts) == 3 and all(p.isdigit() for p in parts)


@click.command("use")
@click.argument("version_spec")
@click.pass_context
def use_cmd(ctx, version_spec):
    """Setzt PHP-Version für die aktuelle Shell-Session (via Shell-Funktion).

    Mit Family (8.4) wird die aktive Patch-Version genutzt.
    Mit voller Version (8.4.19) wird exakt diese Version für die Session gesetzt.
    """
    prefix: Path = ctx.obj["prefix"]

    if _is_pinned(version_spec):
        vdir = version_dir(prefix, version_spec)
        if not vdir.exists():
            click.echo(
                f"PHP {version_spec} ist nicht installiert. "
                f"Zuerst: pbrew install {version_spec}",
                err=True,
            )
            raise SystemExit(1)
        click.echo(f'export PATH="{vdir / "bin"}:{prefix / "bin"}:$PATH"')
        click.echo("hash -r")
    else:
        family = family_from_version(version_spec)
        sf = state_file(prefix, family)
        state = get_family_state(sf)
        if not state.get("active"):
            click.echo(
                f"PHP {family} ist nicht installiert. Zuerst: pbrew install {family}",
                err=True,
            )
            raise SystemExit(1)
        click.echo(f"export PBREW_PHP={family}")
        click.echo(f'export PATH="{prefix / "bin"}:$PATH"')
        click.echo("hash -r")


@click.command("switch")
@click.argument("version_spec")
@click.pass_context
def switch_cmd(ctx, version_spec):
    """Setzt PHP-Version permanent als Default und aktualisiert php/phpd-Wrapper.

    Mit Family (8.4) wird die aktive Patch-Version übernommen.
    Mit voller Version (8.4.19) wird exakt diese Version dauerhaft aktiviert.
    """
    prefix: Path = ctx.obj["prefix"]
    family = family_from_version(version_spec)

    if _is_pinned(version_spec):
        vdir = version_dir(prefix, version_spec)
        if not vdir.exists():
            click.echo(
                f"PHP {version_spec} ist nicht installiert. "
                f"Zuerst: pbrew install {version_spec}",
                err=True,
            )
            raise SystemExit(1)
        version = version_spec
        write_versioned_wrappers(prefix, version, family)
        set_active_version(state_file(prefix, family), version)
    else:
        sf = state_file(prefix, family)
        state = get_family_state(sf)
        if not state.get("active"):
            click.echo(
                f"PHP {family} ist nicht installiert. Zuerst: pbrew install {family}",
                err=True,
            )
            raise SystemExit(1)
        version = state["active"]

    set_global_default(global_state_file(prefix), family)
    write_naked_wrappers(prefix)
    click.echo(f"✓ php{family_suffix(family)} ist jetzt der permanente Default")
    click.echo(f"  php  → {prefix}/bin/php{family_suffix(family)}")
    click.echo(f"  phpd → {prefix}/bin/php-fpm{family_suffix(family)}")
