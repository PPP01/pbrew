import shutil
from pathlib import Path
import click
from pbrew.core.paths import distfiles_dir, state_dir, state_file, family_from_version
from pbrew.core.state import get_family_state


@click.command("clean")
@click.argument("version", required=False)
@click.option("--dry-run", is_flag=True, help="Zeigt was gelöscht würde, ohne zu löschen")
@click.pass_context
def clean_cmd(ctx, version, dry_run):
    """Löscht Build-Verzeichnisse und veraltete Distfiles.

    Ohne Argument: alle Build-Verzeichnisse + veraltete PHP-Tarballs.
    Mit VERSION: nur das Build-Verzeichnis dieser PHP-Version.
    """
    prefix: Path = ctx.obj["prefix"]

    if version:
        _clean_version_builds(prefix, version, dry_run)
    else:
        _clean_all_builds(prefix, dry_run)
        _clean_old_tarballs(prefix, dry_run)


def _clean_version_builds(prefix: Path, version: str, dry_run: bool) -> None:
    try:
        family = family_from_version(version)
    except ValueError:
        click.echo(f"Ungültige Versionsangabe: {version!r}", err=True)
        raise SystemExit(1)

    build_root = prefix / "build"
    entries = []
    if build_root.exists():
        for entry in sorted(build_root.iterdir()):
            if not entry.is_dir():
                continue
            try:
                if family_from_version(entry.name) == family:
                    entries.append(entry)
            except ValueError:
                pass

    if not entries:
        click.echo(f"Kein Build-Verzeichnis für PHP {family} gefunden.")
        return

    for entry in entries:
        size_mb = sum(f.stat().st_size for f in entry.rglob("*") if f.is_file()) / 1_048_576
        click.echo(f"  {'[dry-run] ' if dry_run else ''}Entferne build/{entry.name}/ ({size_mb:.0f} MB)")
        if not dry_run:
            shutil.rmtree(entry)
    if not dry_run:
        click.echo(f"✓ Build-Verzeichnisse für PHP {family} entfernt.")


def _clean_all_builds(prefix: Path, dry_run: bool) -> None:
    build_root = prefix / "build"
    if not build_root.exists():
        click.echo("Kein Build-Verzeichnis gefunden.")
        return

    removed = 0
    total_mb = 0.0
    for entry in sorted(build_root.iterdir()):
        if not entry.is_dir():
            continue
        size_mb = sum(f.stat().st_size for f in entry.rglob("*") if f.is_file()) / 1_048_576
        click.echo(f"  {'[dry-run] ' if dry_run else ''}Entferne build/{entry.name}/ ({size_mb:.0f} MB)")
        if not dry_run:
            shutil.rmtree(entry)
        removed += 1
        total_mb += size_mb

    if removed == 0:
        click.echo("Keine Build-Verzeichnisse gefunden.")
    elif not dry_run:
        click.echo(f"\n✓ {removed} Build-Verzeichnis(se) entfernt ({total_mb:.0f} MB).")


def _clean_old_tarballs(prefix: Path, dry_run: bool) -> None:
    ddir = distfiles_dir(prefix)
    if not ddir.exists():
        return

    installed = _collect_installed_versions(prefix)
    removed = 0
    for tarball in sorted(ddir.glob("php-*.tar.bz2")):
        version = tarball.name.removeprefix("php-").removesuffix(".tar.bz2")
        if version not in installed:
            size_mb = tarball.stat().st_size / 1_048_576
            click.echo(f"  {'[dry-run] ' if dry_run else ''}Entferne {tarball.name} ({size_mb:.1f} MB)")
            if not dry_run:
                tarball.unlink()
            removed += 1

    if removed > 0 and not dry_run:
        click.echo(f"✓ {removed} veraltete(n) Tarball(s) gelöscht.")


def _collect_installed_versions(prefix: Path) -> set[str]:
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
