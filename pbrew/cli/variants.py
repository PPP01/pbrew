import click

from pbrew.core.builder import (
    VARIANT_FLAGS, VARIANT_SAAPIS, VARIANT_BUILD_OPTIONS,
    VARIANT_EXTENSIONS, VARIANT_META,
)


@click.command("variants")
def variants_cmd():
    """Zeigt alle verfügbaren Build-Variants, Build-Optionen und Meta-Aliases."""
    extensions = sorted(VARIANT_EXTENSIONS)
    build_options = sorted(VARIANT_BUILD_OPTIONS)
    saapis = sorted(VARIANT_SAAPIS)

    click.echo("Extensions  (erscheinen in `php -m` nach dem Build):")
    _print_wrapped(extensions)
    click.echo()
    click.echo("Build-Optionen  (kein Eintrag in `php -m`, nur Konstanten/Flags):")
    _print_wrapped(build_options)
    click.echo()
    click.echo("SAPIs:")
    _print_wrapped(saapis)
    click.echo()
    click.echo("Meta-Variants  (phpbrew-kompatible Aliases, werden expandiert):")
    for name, members in sorted(VARIANT_META.items()):
        if name in ("all", "everything"):
            click.echo(f"  {name}: (alle aktivierbaren Variants)")
        elif members:
            click.echo(f"  {name}: {', '.join(members)}")
        else:
            click.echo(f"  {name}: (leer)")
    click.echo()
    click.echo("Verwendung in der Config (z.B. configs/8.4/standard.toml):")
    click.echo('  variants = ["default", "ipc", "dbs", "argon2"]')
    click.echo()
    click.echo("Oder interaktiv:  pbrew ext add")


def _print_wrapped(items: list[str], width: int = 72) -> None:
    if not items:
        click.echo("  (keine)")
        return
    line = "  "
    first = True
    for item in items:
        sep = ", " if not first else ""
        if len(line) + len(sep) + len(item) > width and not first:
            click.echo(line)
            line = "  " + item
        else:
            line += sep + item
            first = False
    if line.strip():
        click.echo(line)
