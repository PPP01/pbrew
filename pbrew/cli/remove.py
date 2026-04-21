import shutil
from pathlib import Path
import click
from pbrew.core.paths import family_from_version, version_dir, state_file
from pbrew.core.state import get_family_state, remove_install


@click.command("remove")
@click.argument("version")
@click.option("--yes", "-y", is_flag=True, help="Ohne Bestätigung löschen")
@click.pass_context
def remove_cmd(ctx, version, yes):
    """Deinstalliert eine PHP-Version vollständig."""
    prefix: Path = ctx.obj["prefix"]
    family = family_from_version(version)
    sf = state_file(prefix, family)
    state = get_family_state(sf)

    if state.get("active") == version:
        click.echo(f"Fehler: {version} ist die aktive Version. Erst auf andere wechseln.", err=True)
        raise SystemExit(1)

    vdir = version_dir(prefix, version)
    if not vdir.exists():
        click.echo(f"{version} ist nicht installiert.")
        return

    size_mb = sum(f.stat().st_size for f in vdir.rglob("*") if f.is_file()) / 1_048_576
    click.echo(f"Lösche PHP {version} ({size_mb:.0f} MB): {vdir}")

    if not yes and not click.confirm("Fortfahren?"):
        click.echo("Abgebrochen.")
        return

    shutil.rmtree(vdir)
    remove_install(sf, version)
    click.echo(f"✓ PHP {version} entfernt (Verzeichnis + State).")
