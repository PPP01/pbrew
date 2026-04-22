from pathlib import Path

from pbrew.core.paths import bin_dir, family_suffix, version_dir


def write_versioned_wrappers(prefix: Path, version: str, family: str) -> None:
    """Erstellt php84, phpize84, php-config84 und php-fpm84 in PREFIX/bin/."""
    bdir = bin_dir(prefix)
    bdir.mkdir(parents=True, exist_ok=True)
    suffix = family_suffix(family)
    vdir = version_dir(prefix, version)

    for name, target in [
        (f"php{suffix}", vdir / "bin" / "php"),
        (f"phpize{suffix}", vdir / "bin" / "phpize"),
        (f"php-config{suffix}", vdir / "bin" / "php-config"),
        (f"php-fpm{suffix}", vdir / "sbin" / "php-fpm"),
    ]:
        wrapper = bdir / name
        wrapper.write_text(f"#!/bin/bash\nexec {target} \"$@\"\n")
        wrapper.chmod(0o755)


def _wrapper_content(pbrew_exec: str, system_cmd: str) -> str:
    """Bash-Wrapper-Template: nutzt $PBREW_PATH; fällt auf System-Binary zurück."""
    return (
        "#!/bin/bash\n"
        'if [ -n "$PBREW_PATH" ]; then\n'
        f'    exec {pbrew_exec} "$@"\n'
        "else\n"
        '    _dir=$(cd "$(dirname "$0")" && pwd)\n'
        f"    _sys=$(PATH=$(printf '%s' \"$PATH\" | tr ':' '\\n' | grep -vxF \"$_dir\" | tr '\\n' ':') command -v {system_cmd} 2>/dev/null)\n"
        '    [ -n "$_sys" ] && exec "$_sys" "$@"\n'
        f"    printf '{system_cmd}: nicht gefunden\\n' >&2\n"
        "    exit 127\n"
        "fi\n"
    )


def _naked_wrapper_content(name: str) -> str:
    return _wrapper_content(f'"$PBREW_PATH/{name}"', name)


def _fpm_wrapper_content() -> str:
    return _wrapper_content('"$(dirname "$PBREW_PATH")/sbin/php-fpm"', "php-fpm")


def write_naked_wrappers(prefix: Path) -> None:
    """Schreibt ENV-aware php/phpize/php-config/php-fpm Wrapper in PREFIX/bin/.

    Ohne gesetztes $PBREW_PATH wird das System-Binary verwendet.
    """
    bdir = bin_dir(prefix)
    bdir.mkdir(parents=True, exist_ok=True)

    for name in ("php", "phpize", "php-config"):
        wrapper = bdir / name
        wrapper.write_text(_naked_wrapper_content(name))
        wrapper.chmod(0o755)

    fpm_wrapper = bdir / "php-fpm"
    fpm_wrapper.write_text(_fpm_wrapper_content())
    fpm_wrapper.chmod(0o755)


def find_xdebug(version_dir: Path) -> Path | None:
    """Sucht xdebug.so in version_dir/lib/php/extensions/** .

    Gibt den ersten Treffer zurück oder None, wenn nicht gefunden.
    """
    search_root = version_dir / "lib" / "php" / "extensions"
    if not search_root.exists():
        return None
    return next(search_root.rglob("xdebug.so"), None)


def write_phpd_wrapper(prefix: Path, version: str) -> bool:
    """Schreibt PREFIX/bin/phpd wenn xdebug für die Version vorhanden ist.

    Löscht einen veralteten phpd-Wrapper, wenn kein xdebug gefunden wird.
    Gibt True zurück wenn der Wrapper erstellt wurde, False wenn xdebug fehlt.
    """
    vdir = version_dir(prefix, version)
    xdebug = find_xdebug(vdir)

    bdir = bin_dir(prefix)
    phpd = bdir / "phpd"

    if xdebug is None:
        phpd.unlink(missing_ok=True)
        return False

    bdir.mkdir(parents=True, exist_ok=True)
    # Prefix und Family werden zur Laufzeit aus den ENV-Vars abgeleitet:
    # $PBREW_PATH = <prefix>/versions/<version>/bin → 3× dirname = prefix
    # $PBREW_ACTIVE = "8.4.20" → ${PBREW_ACTIVE%.*} = "8.4" = family
    phpd.write_text(
        "#!/bin/bash\n"
        'if [ -n "$PBREW_PATH" ]; then\n'
        '    _prefix=$(dirname "$(dirname "$(dirname "$PBREW_PATH")")")\n'
        '    _family="${PBREW_ACTIVE%.*}"\n'
        '    export PHP_INI_SCAN_DIR="$_prefix/etc/conf.d/$_family:$_prefix/etc/conf.d/${_family}d"\n'
        '    exec "$PBREW_PATH/php" "$@"\n'
        "else\n"
        '    echo "phpd: PBREW_PATH nicht gesetzt. Bitte zuerst: pbrew use <version>" >&2\n'
        "    exit 1\n"
        "fi\n"
    )
    phpd.chmod(0o755)
    return True
