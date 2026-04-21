import click
from pbrew.core.paths import version_key
from pbrew.core.resolver import fetch_known, PhpRelease


@click.command("known")
@click.option("--major", default=8, show_default=True, help="PHP Major-Version")
@click.option("--eol", is_flag=True, help="EOL-Versionen einschließen (8.0, 8.1, 7.x …)")
def known_cmd(major, eol):
    """Listet verfügbare PHP-Versionen von php.net."""
    releases: list[PhpRelease] = fetch_known(major, include_eol=eol)

    if eol and major >= 8:
        try:
            prev = fetch_known(major - 1, include_eol=True)
            releases = sorted(releases + prev, key=lambda r: version_key(r.version), reverse=True)
        except Exception:
            pass

    by_family: dict[str, list[PhpRelease]] = {}
    for r in releases:
        by_family.setdefault(r.family, []).append(r)

    for family, fam_releases in sorted(by_family.items(), reverse=True):
        is_eol = fam_releases[0].eol
        shown = [r.version for r in fam_releases[:8]]
        rest = len(fam_releases) > 8
        eol_marker = " [EOL]" if is_eol else ""
        click.echo(f"{family}{eol_marker}: {', '.join(shown)}{'...' if rest else ''}")
