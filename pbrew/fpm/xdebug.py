from pathlib import Path


def create_debug_wrapper(prefix: Path, version: str, family: str) -> Path:
    """Erstellt php84d Wrapper-Script mit erweitertem PHP_INI_SCAN_DIR.

    Xdebug wird nicht per `-n` (alle Extensions deaktivieren) getrennt,
    sondern durch einen zweiten scan-dir (`conf.d/8.4d/`), der nur
    `xdebug.ini` enthält. Der Wrapper setzt PHP_INI_SCAN_DIR auf beide.
    So bleiben alle anderen Extensions aktiv – nur Xdebug kommt dazu.
    """
    suffix = family.replace(".", "")
    scan_normal = prefix / "etc" / "conf.d" / family
    scan_debug = prefix / "etc" / "conf.d" / f"{family}d"
    php_bin = prefix / "versions" / version / "bin" / "php"

    bdir = prefix / "bin"
    bdir.mkdir(parents=True, exist_ok=True)
    wrapper = bdir / f"php{suffix}d"
    wrapper.write_text(
        f'#!/bin/bash\n'
        f'export PHP_INI_SCAN_DIR="{scan_normal}:{scan_debug}"\n'
        f'exec {php_bin} "$@"\n'
    )
    wrapper.chmod(0o755)
    return wrapper


def create_xdebug_ini(prefix: Path, family: str) -> Path:
    """Erstellt Platzhalter-xdebug.ini im Debug-scan-dir.

    Die echte Extension wird via `pbrew ext install xdebug` gebaut.
    Diese Datei stellt sicher, dass das Verzeichnis existiert und
    dokumentiert den nächsten Schritt.
    """
    debug_dir = prefix / "etc" / "conf.d" / f"{family}d"
    debug_dir.mkdir(parents=True, exist_ok=True)
    ini = debug_dir / "xdebug.ini"
    if ini.exists():
        return ini
    suffix = family.replace(".", "")
    ini.write_text(
        f"; Xdebug — nur in php{suffix}d verfügbar\n"
        f"; Installieren: pbrew ext install xdebug {family}\n"
        f"; zend_extension=xdebug.so\n"
        f"; xdebug.mode=debug\n"
        f"; xdebug.start_with_request=trigger\n"
    )
    return ini


def debug_scan_dir(prefix: Path, family: str) -> str:
    """Gibt den kombinierten PHP_INI_SCAN_DIR-Wert für den Debug-Wrapper zurück."""
    scan_normal = prefix / "etc" / "conf.d" / family
    scan_debug = prefix / "etc" / "conf.d" / f"{family}d"
    return f"{scan_normal}:{scan_debug}"
