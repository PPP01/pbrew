import click

from pbrew.core.builder import VARIANT_FLAGS, VARIANT_SAAPIS, VARIANT_BUILD_OPTIONS, VARIANT_EXTENSIONS


@click.command("variants")
def variants_cmd():
    """Zeigt alle verfügbaren Build-Variants und Build-Optionen."""
    extensions = sorted(VARIANT_EXTENSIONS)
    build_options = sorted(VARIANT_BUILD_OPTIONS)
    saapis = sorted(VARIANT_SAAPIS)

    click.echo("Extensions  (erscheinen in `php -m` nach dem Build):")
    _print_wrapped(extensions)
    click.echo()
    click.echo("Build-Optionen  (kein Eintrag in `php -m`, nur Konstanten/Funktionen):")
    _print_wrapped(build_options)
    click.echo()
    click.echo("SAPIs:")
    _print_wrapped(saapis)
    click.echo()
    click.echo("Verwendung in der Config (z.B. configs/8.4/standard.toml):")
    click.echo('  variants = ["default", "intl", "gd", "argon2"]')
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
