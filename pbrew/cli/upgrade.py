import difflib
import shutil
from pathlib import Path

import click

from pbrew.core.paths import (
    cli_ini_dir, family_from_version, state_file, version_dir, versions_dir,
)
from pbrew.core.resolver import fetch_latest
from pbrew.core.state import get_family_state


@click.command("upgrade")
@click.argument("version_spec", required=False)
@click.option("--dry-run", is_flag=True, help="Nur anzeigen, nicht ausführen")
@click.pass_context
def upgrade_cmd(ctx, version_spec, dry_run):
    """Aktualisiert PHP-Versionen auf das neueste Patch-Level."""
    prefix: Path = ctx.obj["prefix"]

    families = _families_to_upgrade(prefix, version_spec)
    if not families:
        click.echo("Keine installierten PHP-Versionen gefunden.")
        return

    click.echo("Prüfe verfügbare Updates...")
    updates = []
    for family in sorted(families):
        sf = state_file(prefix, family)
        state = get_family_state(sf)
        current = state.get("active")
        if not current:
            continue
        try:
            latest = fetch_latest(family)
        except Exception as exc:
            click.echo(f"  Fehler beim Abrufen von PHP {family}: {exc}", err=True)
            continue
        if latest.version != current:
            updates.append((family, current, latest))
            click.echo(f"  {family}: {current} → {latest.version} verfügbar")
        else:
            click.echo(f"  {family}: {current} — aktuell")

    if not updates:
        click.echo("Alle Versionen sind aktuell.")
        return

    if dry_run:
        return

    for i, (family, current, latest) in enumerate(updates, 1):
        click.echo(f"\n[{i}/{len(updates)}] Aktualisiere {family}: {current} → {latest.version}...")
        _do_upgrade(ctx, prefix, family, current, latest)

    click.echo("\n✓ Upgrade abgeschlossen.")


@click.command("rollback")
@click.argument("version_spec")
@click.pass_context
def rollback_cmd(ctx, version_spec):
    """Wechselt auf die vorherige Patch-Version zurück."""
    prefix: Path = ctx.obj["prefix"]
    family = family_from_version(version_spec)
    sf = state_file(prefix, family)
    state = get_family_state(sf)

    previous = state.get("previous")
    if not previous:
        click.echo(f"Keine vorherige Version für PHP {family} gespeichert.", err=True)
        raise SystemExit(1)

    current = state.get("active")
    vdir = version_dir(prefix, previous)
    if not vdir.exists():
        click.echo(f"PHP {previous} ist nicht mehr installiert (bereits bereinigt?).", err=True)
        raise SystemExit(1)

    click.echo(f"Rollback: {current} → {previous}")
    _switch_to_version(prefix, family, previous)
    click.echo(f"✓ Rollback auf {previous} abgeschlossen.")


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _families_to_upgrade(prefix: Path, version_spec: "str | None") -> list[str]:
    if version_spec:
        return [family_from_version(version_spec)]
    vdir = versions_dir(prefix)
    if not vdir.exists():
        return []
    families: set[str] = set()
    for entry in vdir.iterdir():
        if entry.is_dir():
            parts = entry.name.split(".")
            if len(parts) >= 3:
                families.add(f"{parts[0]}.{parts[1]}")
    return sorted(families)


def _do_upgrade(ctx, prefix: Path, family: str, current: str, latest) -> None:
    from pbrew.cli.install import install_cmd

    # Neue Version bauen (nutzt vorhandene install-Logik inkl. Config aus State)
    ctx.invoke(install_cmd, version_spec=latest.version,
               config_name=None, save=False, jobs=None, skip_lib_check=False)

    # Config-Diff prüfen
    _check_ini_diff(prefix, latest.version, family)

    # PECL-Extensions reinstallieren
    sf = state_file(prefix, family)
    state = get_family_state(sf)
    pecl_extensions = state.get("extensions", [])
    if pecl_extensions:
        click.echo(f"  Reinstalliere Extensions: {', '.join(pecl_extensions)}")
        from pbrew.cli.ext import install_ext_cmd
        for ext_name in pecl_extensions:
            click.echo(f"    → {ext_name}...")
            ctx.invoke(install_ext_cmd, ext_name=ext_name, version_spec=family,
                       ext_version=None, jobs=None)

    # Symlinks aktualisieren (write_versioned_wrappers ist der neue _update_wrappers)
    from pbrew.core.wrappers import write_versioned_wrappers
    write_versioned_wrappers(prefix, latest.version, family)

    # FPM neustarten (wenn Service existiert)
    try:
        from pbrew.cli.fpm import restart_cmd
        suffix = family.replace(".", "")
        ctx.invoke(restart_cmd, target=suffix)
    except Exception as exc:
        click.echo(f"  FPM-Restart fehlgeschlagen: {exc}", err=True)

    # Health-Check
    from pbrew.core.config import load_config
    from pbrew.core.paths import configs_dir
    from pbrew.utils.health import run_basic_checks
    config = load_config(configs_dir(prefix), family)
    results = run_basic_checks(prefix, latest.version, family, config)
    for r in results:
        icon = "✓" if r.ok else "✗"
        msg = f" — {r.message}" if r.message else ""
        click.echo(f"    {icon} {r.name}{msg}")

    # Alte Versionen bereinigen
    _offer_cleanup(prefix, family, current, latest.version)


def _check_ini_diff(prefix: Path, version: str, family: str) -> None:
    """Vergleicht neue php.ini-production mit bestehender php.ini (apt-Stil)."""
    new_production = version_dir(prefix, version) / "lib" / "php.ini-production"
    existing_ini = cli_ini_dir(prefix, family) / "php.ini"
    if not new_production.exists() or not existing_ini.exists():
        return

    old_lines = existing_ini.read_text().splitlines(keepends=True)
    new_lines = new_production.read_text().splitlines(keepends=True)
    diff = list(difflib.unified_diff(
        old_lines, new_lines,
        fromfile="php.ini (aktuell)",
        tofile="php.ini-production (neu)",
    ))
    if not diff:
        return

    changed_lines = [l for l in diff if l.startswith("+") or l.startswith("-")]
    click.echo(f"\n  php.ini-production hat {len(changed_lines)} Änderungen gegenüber der aktuellen php.ini.")

    while True:
        choice = click.prompt(
            "  [J]a übernehmen (alte als .bak) / [N]ein behalten (neue als .dist) / [D]iff anzeigen",
            default="N",
        ).upper()
        if choice == "D":
            click.echo("".join(diff))
            continue
        if choice == "J":
            existing_ini.rename(existing_ini.with_suffix(".ini.bak"))
            shutil.copy2(new_production, existing_ini)
            click.echo("  → Neue php.ini übernommen (alte als .bak gesichert).")
        else:
            shutil.copy2(new_production, existing_ini.with_suffix(".ini.dist"))
            click.echo("  → Neue php.ini als .dist abgelegt, bestehende behalten.")
        break


def _offer_cleanup(prefix: Path, family: str, current: str, new: str) -> None:
    """Fragt nach dem Bereinigen älterer Versionen."""
    vdir = versions_dir(prefix)
    old_versions = sorted(
        e.name for e in vdir.iterdir()
        if e.is_dir() and e.name.startswith(family + ".")
        and e.name not in (current, new)
    )
    to_remove_candidates = [current] + old_versions if current != new else old_versions
    if not to_remove_candidates:
        return

    click.echo("\n  Alte Versionen:")
    for v in to_remove_candidates:
        mb = sum(f.stat().st_size for f in (vdir / v).rglob("*") if f.is_file()) / 1_048_576
        click.echo(f"    {v} — {mb:.0f} MB")

    choice = click.prompt(
        "  [B]ehalten / [V]orherige behalten, ältere löschen / [A]lle löschen",
        default="B",
    ).upper()

    if choice == "A":
        for v in to_remove_candidates:
            shutil.rmtree(vdir / v)
            click.echo(f"  ✗ {v} entfernt.")
    elif choice == "V":
        for v in old_versions:
            shutil.rmtree(vdir / v)
            click.echo(f"  ✗ {v} entfernt.")
        click.echo(f"  ✓ {current} behalten (Rollback möglich).")


def _switch_to_version(prefix: Path, family: str, version: str) -> None:
    """Aktualisiert Wrapper und FPM-Services auf eine andere Patch-Version."""
    from pbrew.core.wrappers import write_versioned_wrappers
    from pbrew.core.state import set_active_version
    from pbrew.core.paths import state_file as sf_path

    write_versioned_wrappers(prefix, version, family)
    set_active_version(sf_path(prefix, family), version)

    try:
        from pbrew.fpm.services import write_service, reload_systemd
        from pbrew.core.config import load_config
        from pbrew.core.paths import configs_dir
        import subprocess

        config = load_config(configs_dir(prefix), family)
        xdebug = config.get("xdebug", {}).get("enabled", False)
        for debug in ([False, True] if xdebug else [False]):
            write_service(prefix, version, family, debug)
        reload_systemd()
        suffix = family.replace(".", "")
        subprocess.run(["sudo", "systemctl", "restart", f"php{suffix}-fpm"], check=True)
    except Exception as exc:
        click.echo(f"  FPM-Update fehlgeschlagen: {exc}", err=True)
