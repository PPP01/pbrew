from pathlib import Path
import click
from pbrew.core.paths import family_from_version, family_suffix, global_state_file, state_file, versions_dir
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

    # Alle installierten Versionen pro Family sammeln
    installed_versions: dict[str, list[str]] = {}
    for entry in sorted(vdir.iterdir()):
        if not entry.is_dir():
            continue
        try:
            family = family_from_version(entry.name)
        except ValueError:
            continue
        installed_versions.setdefault(family, []).append(entry.name)

    # Versionen innerhalb jeder Family absteigend sortieren (neueste zuerst)
    for family in installed_versions:
        installed_versions[family].sort(
            key=lambda v: tuple(int(x) for x in v.split(".")),
            reverse=True,
        )

    global_state = get_global_state(global_state_file(prefix))
    default_family = global_state.get("default_family", "")

    click.echo(f"\n{'Family':<8} {'Version':<14} {'Config':<14} {'Wrapper':<10} {'Extensions'}")
    click.echo("─" * 72)

    for family in sorted(installed_versions):
        sf = state_file(prefix, family)
        state = get_family_state(sf)
        active = state.get("active", "")
        suffix = family_suffix(family)
        extensions = ", ".join(state.get("extensions", [])) or "—"
        default_mark = " *" if family == default_family else ""

        for i, version in enumerate(installed_versions[family]):
            marker = "▸" if version == active else " "
            config_name = (
                state.get("installed", {}).get(version, {}).get("config_name") or "—"
            )

            if i == 0:
                family_col = family
                wrapper_col = f"php{suffix}{default_mark}"
                ext_col = extensions
            else:
                family_col = ""
                wrapper_col = ""
                ext_col = ""

            click.echo(
                f"  {family_col:<6} {marker} {version:<14} {config_name:<14} "
                f"{wrapper_col:<10} {ext_col}"
            )

    if default_family:
        click.echo(f"\n  * php{family_suffix(default_family)} ist der aktuelle Default")
    click.echo()
