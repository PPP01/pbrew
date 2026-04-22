import sys
from pathlib import Path

import click

from pbrew.core.paths import (
    family_from_version,
    global_state_file,
    state_file,
    version_bin,
    version_dir,
)
from pbrew.core.state import get_family_state, get_global_state
from pbrew.core.php_test_runner import CATEGORIES, TestResult, run_tests


@click.command("test")
@click.argument("category", required=False, metavar="[KATEGORIE]")
@click.argument("version_spec", required=False, metavar="[PHP-VERSION]")
@click.pass_context
def test_cmd(ctx, category, version_spec):
    """Fuehrt Integrationstests gegen ein installiertes PHP aus.

    \b
    Kategorien: basic, ssl, hash, modules
    \b
      pbrew test               # alle Kategorien, aktive Version
      pbrew test ssl           # nur SSL-Tests
      pbrew test ssl 56        # SSL-Tests fuer PHP 5.6
      pbrew test 84            # alle Tests fuer PHP 8.4
    """
    prefix: Path = ctx.obj["prefix"]

    # Erstes Argument koennte eine Version statt Kategorie sein
    if category and category not in CATEGORIES:
        if version_spec is None:
            version_spec, category = category, None
        else:
            raise click.UsageError(
                f"Unbekannte Kategorie '{category}'. Bekannte Kategorien: {', '.join(CATEGORIES)}"
            )

    categories = [category] if category else None

    # Version auflösen
    version = _resolve_version(prefix, version_spec)
    if not version:
        click.echo("Keine aktive PHP-Version gefunden. Zuerst: pbrew use <VERSION>", err=True)
        raise SystemExit(1)

    php_bin = version_bin(prefix, version, "php")
    if not php_bin.exists():
        click.echo(f"PHP-Binary nicht gefunden: {php_bin}", err=True)
        raise SystemExit(1)

    cat_label = f"  Kategorien:  {', '.join(categories)}" if categories else "  Kategorien:  alle"
    click.echo(f"\nPHP {version} — pbrew test")
    click.echo(cat_label)
    click.echo("─" * 48)

    results = run_tests(php_bin, version, categories)
    _print_results(results)

    passed = sum(1 for r in results if r.passed)
    skipped = sum(1 for r in results if r.skipped)
    failed = sum(1 for r in results if not r.passed and not r.skipped)
    total = len(results) - skipped

    click.echo("─" * 48)
    skip_note = f", {skipped} übersprungen" if skipped else ""
    click.echo(f"\n  {passed}/{total} Tests bestanden{skip_note}\n")

    if failed:
        raise SystemExit(1)


def _resolve_version(prefix: Path, version_spec: str | None) -> str | None:
    if version_spec:
        family = family_from_version(version_spec)
        state = get_family_state(state_file(prefix, family))
        if version_spec.count(".") == 2:
            vdir = version_dir(prefix, version_spec)
            return version_spec if vdir.exists() else None
        return state.get("active")

    # Aktive Version aus dem globalen Default
    global_state = get_global_state(global_state_file(prefix))
    default_family = global_state.get("default_family")
    if default_family:
        state = get_family_state(state_file(prefix, default_family))
        return state.get("active")

    # Fallback: erste Family mit aktiver Version
    from pbrew.core.paths import state_dir
    sdir = state_dir(prefix)
    if sdir.exists():
        for f in sorted(sdir.iterdir()):
            if f.suffix == ".json":
                state = get_family_state(f)
                active = state.get("active")
                if active:
                    return active
    return None


def _print_results(results: list[TestResult]) -> None:
    current_cat = None
    for r in results:
        if r.category != current_cat:
            current_cat = r.category
            click.echo(f"\n  [{current_cat}]")

        if r.skipped:
            icon = "~"
            line = f"    {icon} {r.name}"
            if r.skip_reason:
                line += f"  ({r.skip_reason})"
            click.echo(click.style(line, dim=True))
        elif r.passed:
            click.echo(click.style(f"    ✓ {r.name}", fg="green"))
        else:
            click.echo(click.style(f"    ✗ {r.name}", fg="red"))
            if r.error:
                short = r.error.split("\n")[0][:80]
                click.echo(click.style(f"      → {short}", fg="red", dim=True))
