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


def write_naked_wrappers(prefix: Path) -> None:
    """Schreibt ENV-aware php/phpize/php-config/php-fpm Wrapper in PREFIX/bin/.

    Jeder Wrapper leitet zur Laufzeit via $PBREW_PATH weiter; ohne gesetzte
    Variable fällt er auf /usr/bin/env zurück.
    """
    bdir = bin_dir(prefix)
    bdir.mkdir(parents=True, exist_ok=True)

    # Einfache Binaries in bin/
    for name in ("php", "phpize", "php-config"):
        wrapper = bdir / name
        wrapper.write_text(
            "#!/bin/bash\n"
            f'if [ -n "$PBREW_PATH" ]; then\n'
            f'    exec "$PBREW_PATH/{name}" "$@"\n'
            f"else\n"
            f"    exec /usr/bin/env {name} \"$@\"\n"
            f"fi\n"
        )
        wrapper.chmod(0o755)

    # php-fpm liegt in sbin/, nicht in bin/
    fpm_wrapper = bdir / "php-fpm"
    fpm_wrapper.write_text(
        "#!/bin/bash\n"
        "# php-fpm liegt in sbin/, nicht in bin/ – daher dirname von PBREW_PATH\n"
        'if [ -n "$PBREW_PATH" ]; then\n'
        '    exec "$(dirname "$PBREW_PATH")/sbin/php-fpm" "$@"\n'
        "else\n"
        '    exec /usr/bin/env php-fpm "$@"\n'
        "fi\n"
    )
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

    Gibt True zurück wenn der Wrapper erstellt wurde, False wenn xdebug fehlt.
    """
    vdir = version_dir(prefix, version)
    xdebug = find_xdebug(vdir)
    if xdebug is None:
        return False

    bdir = bin_dir(prefix)
    bdir.mkdir(parents=True, exist_ok=True)

    phpd = bdir / "phpd"
    phpd.write_text(
        "#!/bin/bash\n"
        'if [ -n "$PBREW_PATH" ]; then\n'
        '    EXT_DIR="$("$PBREW_PATH/php" -r \'echo ini_get("extension_dir");\' 2>/dev/null)"\n'
        '    XDEBUG="$EXT_DIR/xdebug.so"\n'
        '    [ -f "$XDEBUG" ] && exec "$PBREW_PATH/php" -dzend_extension="$XDEBUG" "$@"\n'
        '    exec "$PBREW_PATH/php" "$@"\n'
        "else\n"
        '    echo "phpd: PBREW_PATH nicht gesetzt. Bitte zuerst: pbrew use <version>" >&2\n'
        "    exit 1\n"
        "fi\n"
    )
    phpd.chmod(0o755)
    return True
