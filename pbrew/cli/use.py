from pathlib import Path
import click
from pbrew.core.paths import (
    family_from_version,
    global_state_file,
    state_file,
    version_dir,
    version_key,
)
from pbrew.core.shell import write_switch_files
from pbrew.core.state import get_family_state, set_active_version, set_global_default
from pbrew.core.wrappers import write_naked_wrappers, write_phpd_wrapper, write_versioned_wrappers


def _is_pinned(version_spec: str) -> bool:
    parts = version_spec.split(".")
    return len(parts) == 3 and all(p.isdigit() for p in parts)


def _resolve_version(prefix: Path, version_spec: str) -> tuple[str, str]:
    """Löst version_spec zu (version, family) auf.

    Gibt bei Fehler einen SystemExit(1) aus.
    """
    if _is_pinned(version_spec):
        vdir = version_dir(prefix, version_spec)
        if not vdir.exists():
            click.echo(
                f"PHP {version_spec} ist nicht installiert. "
                f"Zuerst: pbrew install {version_spec}",
                err=True,
            )
            raise SystemExit(1)
        return version_spec, family_from_version(version_spec)

    family = family_from_version(version_spec)
    sf = state_file(prefix, family)
    state = get_family_state(sf)
    installed = [
        v for v in state.get("installed", {})
        if version_dir(prefix, v).exists()
    ]
    if not installed:
        click.echo(
            f"PHP {family} ist nicht installiert. Zuerst: pbrew install {family}",
            err=True,
        )
        raise SystemExit(1)
    version = max(installed, key=version_key)
    return version, family


@click.command("use")
@click.argument("version_spec")
@click.pass_context
def use_cmd(ctx, version_spec):
    """Setzt PHP-Version für die aktuelle Shell-Session.

    Emittiert ENV-Exporte (PBREW_PATH, PBREW_ACTIVE), die von der
    Shell-Funktion via `eval` gesetzt werden. Der naked `php`-Wrapper
    liest $PBREW_PATH zur Laufzeit und delegiert an die korrekte Version.
    """
    prefix: Path = ctx.obj["prefix"]
    version, _family = _resolve_version(prefix, version_spec)

    pbrew_path = version_dir(prefix, version) / "bin"
    click.echo(f'export PBREW_PATH="{pbrew_path}"')
    click.echo(f'export PBREW_ACTIVE="{version}"')
    click.echo(f"PHP {version}", err=True)


@click.command("switch")
@click.argument("version_spec")
@click.pass_context
def switch_cmd(ctx, version_spec):
    """Setzt PHP-Version permanent (persistent über Shell-Neustarts).

    Schreibt State, Wrappers und .switch-Datei; emittiert zusätzlich die
    ENV-Exporte für den aktuellen Shell-Kontext.
    """
    prefix: Path = ctx.obj["prefix"]
    version, family = _resolve_version(prefix, version_spec)

    set_active_version(state_file(prefix, family), version)
    if _is_pinned(version_spec):
        write_versioned_wrappers(prefix, version, family)

    set_global_default(global_state_file(prefix), family)
    write_naked_wrappers(prefix)

    # phpd nur bei switch (persistent), nicht bei use (ephemer)
    write_phpd_wrapper(prefix, version)

    pbrew_path = version_dir(prefix, version) / "bin"
    write_switch_files(prefix, pbrew_path, version)

    click.echo(f'export PBREW_PATH="{pbrew_path}"')
    click.echo(f'export PBREW_ACTIVE="{version}"')
    click.echo(f"PHP {version}", err=True)


@click.command("unswitch")
@click.pass_context
def unswitch_cmd(ctx):
    """Entfernt PHP-Version-Switching (zurück zu System-PHP).

    Löscht die .switch-Datei und gibt `unset`-Statements für die aktuelle
    Shell-Session aus.
    """
    prefix: Path = ctx.obj["prefix"]

    for name in (".switch", ".switch.fish"):
        (prefix / name).unlink(missing_ok=True)

    click.echo("unset PBREW_PATH PBREW_ACTIVE")
