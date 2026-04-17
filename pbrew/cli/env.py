import os
import re
from pathlib import Path

import click

from pbrew.core.paths import bin_dir, global_state_file
from pbrew.core.state import get_global_state


@click.command("env")
@click.pass_context
def env_cmd(ctx):
    """Zeigt pbrew-relevante Umgebungsvariablen und die aktive Shell-Konfiguration."""
    prefix: Path = ctx.obj["prefix"]
    bdir = bin_dir(prefix)

    click.echo("\nUmgebung:")
    click.echo(f"  PBREW_ROOT:   {prefix}")

    pbrew_path = os.environ.get("PBREW_PATH")
    click.echo(f"  PBREW_PATH:   {pbrew_path or '—'}")

    pbrew_active = os.environ.get("PBREW_ACTIVE")
    click.echo(f"  PBREW_ACTIVE: {pbrew_active or '—'}")

    path = os.environ.get("PATH", "")
    path_contains = str(bdir) in path.split(":")
    click.echo(f"  PATH:         {bdir} {'(vorhanden)' if path_contains else '(fehlt)'}")

    global_state = get_global_state(global_state_file(prefix))
    default_family = global_state.get("default_family")
    click.echo(f"  Default:      {default_family or '—'}")

    click.echo("\nNackte Wrapper:")
    for name in ("php", "phpd"):
        target = _resolve_wrapper_target(bdir / name)
        click.echo(f"  {name:<5} → {target}")

    click.echo()


def _resolve_wrapper_target(wrapper: Path) -> str:
    """Liest das exec-Ziel aus einem Bash-Wrapper-Skript."""
    if not wrapper.exists():
        return "(nicht vorhanden)"
    try:
        text = wrapper.read_text()
    except OSError:
        return "(unlesbar)"
    if "$PBREW_PATH" in text:
        return "ENV-aware ($PBREW_PATH)"
    match = re.search(r"exec\s+(\S+)", text)
    if not match:
        return "(Format unbekannt)"
    target = Path(match.group(1)).name
    return target
