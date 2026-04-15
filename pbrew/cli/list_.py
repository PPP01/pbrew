from pathlib import Path
import click
from pbrew.core.paths import global_state_file, state_file, versions_dir
from pbrew.core.state import get_family_state, get_global_state


@click.command("list")
@click.pass_context
def list_cmd(ctx):
    """Zeigt alle installierten PHP-Versionen."""
    prefix: Path = ctx.obj["prefix"]
    vdir = versions_dir(prefix)

    if not vdir.exists():
        click.echo("Keine PHP-Versionen installiert.")
        return

    installed_versions: dict[str, list[str]] = {}
    for entry in sorted(vdir.iterdir()):
        if not entry.is_dir():
            continue
        parts = entry.name.split(".")
        if len(parts) >= 2:
            family = f"{parts[0]}.{parts[1]}"
            installed_versions.setdefault(family, []).append(entry.name)

    global_state = get_global_state(global_state_file(prefix))
    default_family = global_state.get("default_family", "")

    click.echo(f"\n{'Family':<8} {'Aktiv':<12} {'Vorherige':<12} {'Wrapper':<10} {'Extensions'}")
    click.echo("─" * 70)

    for family in sorted(installed_versions):
        sf = state_file(prefix, family)
        state = get_family_state(sf)
        active = state.get("active", "—")
        previous = state.get("previous", "—")
        suffix = family.replace(".", "")
        extensions = ", ".join(state.get("extensions", [])) or "—"
        default_mark = " *" if family == default_family else ""
        click.echo(f"  {family:<8} {active:<12} {previous:<12} php{suffix:<7} {extensions}{default_mark}")

    if default_family:
        click.echo(f"\n  * php{default_family.replace('.', '')} ist der aktuelle Default")
    click.echo()
