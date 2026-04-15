from pathlib import Path

import click

from pbrew.core.config import init_profiles
from pbrew.core.global_config import global_config_file, write_prefix
from pbrew.core.paths import (
    bin_dir,
    configs_dir,
    distfiles_dir,
    etc_dir,
    get_prefix,
    state_dir,
    versions_dir,
)
from pbrew.core.prerequisites import check_prerequisites, install_hint
from pbrew.core.shell import (
    SHELL_MAP,
    _rc_file_for,
    already_integrated,
    append_shell_integration,
    detect_shell,
)


@click.command("init")
def init_cmd():
    """Richtet pbrew ein: Prefix wählen, Verzeichnisse anlegen, Shell integrieren."""
    current_default = get_prefix()

    chosen = click.prompt("Installationspräfix", default=str(current_default))
    prefix = Path(chosen).expanduser().resolve()

    click.echo(f"\nRichte pbrew unter {prefix} ein...\n")

    dirs = [
        versions_dir(prefix),
        bin_dir(prefix),
        etc_dir(prefix),
        distfiles_dir(prefix),
        state_dir(prefix),
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        click.echo(f"  ✓ {d.relative_to(prefix)}/")

    created = init_profiles(configs_dir(prefix))
    if created:
        click.echo(f"\nBuild-Profile angelegt: {', '.join(created)}")
        click.echo("  Verwenden mit: pbrew install 8.4 --config=dev")
    else:
        click.echo("\nBuild-Profile: bereits vorhanden.")

    write_prefix(prefix)
    click.echo(f"\nKonfiguration gespeichert: {global_config_file()}")

    _setup_shell_integration()
    _check_build_prerequisites()

    click.echo("\npbrew ist eingerichtet. Weiter mit:")
    click.echo("  pbrew known         — Verfügbare PHP-Versionen anzeigen")
    click.echo("  pbrew install 8.4   — PHP 8.4 installieren")


def _check_build_prerequisites() -> None:
    click.echo("\nBuild-Voraussetzungen:")
    results = check_prerequisites()
    missing = [r.name for r in results if not r.found]
    for r in results:
        icon = "✓" if r.found else "✗"
        click.echo(f"  {icon} {r.name}")
    if missing:
        hint = install_hint()
        if hint:
            click.echo(f"\n  Fehlende Tools installieren:\n    {hint}")
        else:
            click.echo(f"\n  Fehlend: {', '.join(missing)}")
    else:
        click.echo("  Alle Build-Tools vorhanden.")


def _setup_shell_integration() -> None:
    click.echo("\nShell-Integration:")
    shell = detect_shell()
    if shell is None:
        click.echo("  Shell nicht erkannt – bitte manuell einrichten.")
        _print_manual_hint(None)
        return

    rc_file = _rc_file_for(shell)
    snippet = SHELL_MAP[shell]["snippet"]

    if already_integrated(rc_file):
        click.echo(f"  ✓ Bereits in {rc_file} eingetragen.")
        return

    if click.confirm(f"  Integration in {rc_file} eintragen?", default=True):
        append_shell_integration(rc_file, snippet)
        click.echo(f"  ✓ Eingetragen. Shell neu starten oder: source {rc_file}")
    else:
        _print_manual_hint(shell)


def _print_manual_hint(shell: "str | None") -> None:
    if shell and shell in SHELL_MAP:
        snippet = SHELL_MAP[shell]["snippet"]
        click.echo(f"  Manuell in die RC-Datei eintragen:\n    {snippet}")
    else:
        click.echo("  Manuell in die RC-Datei eintragen: eval \"$(pbrew shell-init bash|zsh)\"")
