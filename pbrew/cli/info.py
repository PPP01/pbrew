from pathlib import Path

import click

from pbrew.core.paths import (
    bin_dir,
    family_from_version,
    family_suffix,
    global_state_file,
    state_file,
    version_dir,
)
from pbrew.core.state import get_family_state, get_global_state


@click.command("info")
@click.argument("version_spec")
@click.pass_context
def info_cmd(ctx, version_spec):
    """Zeigt Detailinformationen zu einer installierten PHP-Version."""
    prefix: Path = ctx.obj["prefix"]
    family = family_from_version(version_spec)
    state = get_family_state(state_file(prefix, family))

    # Version auflösen: '8.4' → aktive Version der Family
    version = version_spec if version_spec.count(".") == 2 else state.get("active")
    if not version:
        click.echo(f"PHP {family} ist nicht installiert.", err=True)
        raise SystemExit(1)

    vdir = version_dir(prefix, version)
    if not vdir.exists():
        click.echo(f"PHP {version} ist nicht installiert (kein Verzeichnis: {vdir}).", err=True)
        raise SystemExit(1)

    entry = state.get("installed", {}).get(version, {})
    global_state = get_global_state(global_state_file(prefix))
    suffix = family_suffix(family)

    is_active = state.get("active") == version
    is_default_family = global_state.get("default_family") == family
    status_parts = []
    if is_active:
        status_parts.append("aktiv")
    if is_default_family and is_active:
        status_parts.append("Family-Default")
    status = ", ".join(status_parts) if status_parts else "installiert (nicht aktiv)"

    click.echo(f"\nPHP {version} (Family {family})")
    click.echo(f"  Pfad:         {vdir}")
    click.echo(f"  Installiert:  {entry.get('installed_at', '—')}")
    click.echo(f"  Build-Dauer:  {_format_duration(entry.get('build_duration_seconds'))}")
    click.echo(f"  Config:       {entry.get('config_name', '—')}")
    click.echo(f"  Variants:     {_format_variants(entry.get('variants'))}")
    click.echo(f"  Wrapper:      {bin_dir(prefix) / f'php{suffix}'}, {bin_dir(prefix) / f'php-fpm{suffix}'}")
    click.echo(f"  Status:       {status}")
    click.echo()


def _format_duration(seconds) -> str:
    if not seconds:
        return "—"
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes}m {secs}s" if minutes else f"{secs}s"


def _format_variants(variants) -> str:
    if not variants:
        return "—"
    return ", ".join(variants)
