from pathlib import Path

import click

from pbrew.core.paths import distfiles_dir, state_dir, versions_dir, state_file, family_from_version
from pbrew.core.state import get_family_state


@click.command("cleanup")
@click.option("--dry-run", is_flag=True, help="Zeigt was gelöscht würde, ohne zu löschen")
@click.pass_context
def cleanup_cmd(ctx, dry_run):
    """Entfernt Tarballs von nicht installierten PHP-Versionen aus dem Distfiles-Cache."""
    prefix: Path = ctx.obj["prefix"]

    installed = _collect_installed_versions(prefix)
    ddir = distfiles_dir(prefix)

    if not ddir.exists():
        click.echo("Distfiles-Verzeichnis nicht gefunden.")
        return

    removed = 0
    for tarball in sorted(ddir.glob("php-*.tar.bz2")):
        version = tarball.name.removeprefix("php-").removesuffix(".tar.bz2")
        if version not in installed:
            size_mb = tarball.stat().st_size / 1_048_576
            click.echo(f"  {'[dry-run] ' if dry_run else ''}Entferne {tarball.name} ({size_mb:.1f} MB)")
            if not dry_run:
                tarball.unlink()
            removed += 1

    if removed == 0:
        click.echo("Keine veralteten Tarballs gefunden.")
    elif not dry_run:
        click.echo(f"\n✓ {removed} Tarball(s) gelöscht.")
    else:
        click.echo(f"\n{removed} Tarball(s) würden gelöscht (--dry-run).")


def _collect_installed_versions(prefix: Path) -> set[str]:
    """Gibt alle bekannten installierten Versionen aus dem State zurück."""
    installed: set[str] = set()
    sdir = state_dir(prefix)
    if not sdir.exists():
        return installed
    for state_path in sdir.glob("*.json"):
        if state_path.stem == "global":
            continue
        state = get_family_state(state_path)
        installed.update(state.get("installed", {}).keys())
        if state.get("active"):
            installed.add(state["active"])
    return installed
