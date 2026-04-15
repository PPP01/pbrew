import sys
from pathlib import Path

import click

from pbrew.core.paths import bin_dir, family_from_version, versions_dir, state_file
from pbrew.core.prerequisites import check_prerequisites, install_hint
from pbrew.core.state import get_family_state


@click.command("doctor")
@click.pass_context
def doctor_cmd(ctx):
    """Systemweite Prüfung der pbrew-Installation und Build-Voraussetzungen."""
    prefix: Path = ctx.obj["prefix"]
    ok_all = True

    click.echo("Prüfe pbrew-Installation...\n")

    py_ok = sys.version_info >= (3, 11)
    _show("Python " + sys.version.split()[0], py_ok)
    ok_all = ok_all and py_ok

    click.echo("\nBinaries:")
    results = check_prerequisites()
    missing = []
    for r in results:
        _show(r.name, r.found)
        ok_all = ok_all and r.found
        if not r.found:
            missing.append(r.name)

    if missing:
        hint = install_hint()
        if hint:
            click.echo(f"\n  Fehlende Tools installieren:\n    {hint}")

    # Installierte Versionen vs. State-Konsistenz
    vdir = versions_dir(prefix)
    if vdir.exists():
        click.echo("\nInstallierte Versionen:")
        family_states: dict[str, dict] = {}
        for entry in sorted(vdir.iterdir()):
            if not entry.is_dir():
                continue
            try:
                family = family_from_version(entry.name)
            except ValueError:
                continue
            if family not in family_states:
                family_states[family] = get_family_state(state_file(prefix, family))
            active = family_states[family].get("active") == entry.name
            suffix = " (aktiv)" if active else ""
            _show(f"{entry.name}{suffix}", True)
    else:
        click.echo("\n  Keine Versionen installiert.")

    bdir = bin_dir(prefix)
    if bdir.exists():
        click.echo("\nWrapper in " + str(bdir) + ":")
        for wrapper in sorted(bdir.iterdir()):
            ok = wrapper.is_file() and wrapper.stat().st_mode & 0o111
            _show(str(wrapper.name), ok)

    click.echo()
    if ok_all:
        click.echo("✓ Alles in Ordnung.")
    else:
        click.echo("✗ Einige Prüfungen fehlgeschlagen.", err=True)
        raise SystemExit(1)


def _show(name: str, ok: bool) -> None:
    icon = "✓" if ok else "✗"
    click.echo(f"  {icon} {name}")
