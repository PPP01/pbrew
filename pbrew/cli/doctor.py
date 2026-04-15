import shutil
import sys
from pathlib import Path

import click

from pbrew.core.paths import bin_dir, versions_dir, state_file
from pbrew.core.state import get_family_state


# Binaries die für den Build benötigt werden
_REQUIRED_BINS = ["gcc", "make", "autoconf", "bison", "re2c", "pkg-config"]


@click.command("doctor")
@click.pass_context
def doctor_cmd(ctx):
    """Systemweite Prüfung der pbrew-Installation und Build-Voraussetzungen."""
    prefix: Path = ctx.obj["prefix"]
    ok_all = True

    click.echo("Prüfe pbrew-Installation...\n")

    # Python-Version
    py_ok = sys.version_info >= (3, 11)
    _show("Python " + sys.version.split()[0], py_ok)
    ok_all = ok_all and py_ok

    # Binary-Dependencies
    click.echo("\nBinaries:")
    for binary in _REQUIRED_BINS:
        found = shutil.which(binary) is not None
        _show(binary, found)
        ok_all = ok_all and found

    # Installierte Versionen vs. State-Konsistenz
    vdir = versions_dir(prefix)
    if vdir.exists():
        click.echo("\nInstallierte Versionen:")
        for entry in sorted(vdir.iterdir()):
            if not entry.is_dir():
                continue
            parts = entry.name.split(".")
            if len(parts) >= 3:
                family = f"{parts[0]}.{parts[1]}"
                sf = state_file(prefix, family)
                state = get_family_state(sf)
                active = state.get("active") == entry.name
                suffix = " (aktiv)" if active else ""
                _show(f"{entry.name}{suffix}", True)
    else:
        click.echo("\n  Keine Versionen installiert.")

    # Wrapper in bin/
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
