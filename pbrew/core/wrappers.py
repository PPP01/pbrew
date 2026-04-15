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


def write_naked_wrappers(prefix: Path, version: str, family: str) -> None:
    """Aktualisiert die nackten php/phpd-Wrapper auf die angegebene Version.

    php  → delegiert an php{suffix}      (z.B. php84)
    phpd → delegiert an php-fpm{suffix}  (z.B. php-fpm84)
    """
    bdir = bin_dir(prefix)
    bdir.mkdir(parents=True, exist_ok=True)
    suffix = family_suffix(family)

    php_wrapper = bdir / "php"
    php_wrapper.write_text(f"#!/bin/bash\nexec {bdir / f'php{suffix}'} \"$@\"\n")
    php_wrapper.chmod(0o755)

    phpd_wrapper = bdir / "phpd"
    phpd_wrapper.write_text(f"#!/bin/bash\nexec {bdir / f'php-fpm{suffix}'} \"$@\"\n")
    phpd_wrapper.chmod(0o755)
