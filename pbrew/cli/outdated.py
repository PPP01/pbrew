from pathlib import Path

import click

from pbrew.core.paths import state_dir, state_file
from pbrew.core.resolver import fetch_latest
from pbrew.core.state import get_family_state


@click.command("outdated")
@click.pass_context
def outdated_cmd(ctx):
    """Zeigt, welche installierten PHP-Familien Updates haben (Exit 1 wenn ja, 0 wenn alle aktuell)."""
    prefix: Path = ctx.obj["prefix"]
    families = _installed_families(prefix)

    if not families:
        click.echo("Keine PHP-Familien installiert.")
        return

    click.echo(f"\n{'Family':<8} {'Installiert':<14} {'Neueste':<12} Status")
    click.echo("─" * 55)

    has_updates = False
    for family in sorted(families):
        state = get_family_state(state_file(prefix, family))
        active = state.get("active", "—")
        try:
            release = fetch_latest(family)
            latest = release.version
            if latest == active:
                status = "✓ aktuell"
            else:
                status = "↑ Update verfügbar"
                has_updates = True
        except Exception as exc:
            latest = "?"
            status = f"✗ Fehler: {exc}"

        click.echo(f"  {family:<8} {active:<14} {latest:<12} {status}")

    click.echo()
    if has_updates:
        raise SystemExit(1)


def _installed_families(prefix: Path) -> list[str]:
    sdir = state_dir(prefix)
    if not sdir.exists():
        return []
    families = []
    for state_path in sdir.glob("*.json"):
        if state_path.stem == "global":
            continue
        state = get_family_state(state_path)
        if state.get("active"):
            families.append(state_path.stem)
    return families
