"""Generiert das statische Bash-Wrapper-Skript für ~/.pbrew/bin/pbrew.

Das Skript liest den Pfad zum echten Python-pbrew aus wrapper.env.
Kein Raten, kein Auto-Install von PyPI. pbrew init erkennt die aktuelle
Umgebung und schreibt den Pfad einmalig in die Datei.

Kein `activate`, kein VIRTUAL_ENV, kein PATH-Manipulation.
Binaries werden immer über absolute Pfade aufgerufen.
"""
import shutil
import sys
from pathlib import Path


def detect_pbrew_bin() -> Path:
    """Ermittelt den Pfad zum aktuell laufenden pbrew-Binary.

    Prüfkette:
    1. In einem venv → {sys.prefix}/bin/pbrew
    2. Global installiert → per shutil.which
    3. Fallback → sys.executable (Python selbst)
    """
    if sys.prefix != sys.base_prefix:
        candidate = Path(sys.prefix) / "bin" / "pbrew"
        return candidate
    found = shutil.which("pbrew")
    if found:
        return Path(found)
    return Path(sys.executable)


def write_wrapper_env(prefix: Path, pbrew_bin: Path) -> Path:
    """Schreibt wrapper.env mit dem Pfad zum Python-pbrew.

    Bash-sourceable: KEY="VALUE"-Format.
    """
    prefix.mkdir(parents=True, exist_ok=True)
    env_file = prefix / "wrapper.env"
    env_file.write_text(
        f'# Generiert von "pbrew init" — zeigt auf das Python-pbrew\n'
        f'PBREW_PYTHON_BIN="{pbrew_bin}"\n'
    )
    return env_file


def generate_wrapper_script(prefix: Path) -> str:
    """Gibt den Inhalt des Bash-Wrapper-Skripts zurück mit eingebackenem Prefix."""
    return f'''\
#!/bin/bash
# pbrew — PHP Version Manager (Wrapper)
# Generiert von 'pbrew init'. Liest den Pfad zum Python-pbrew aus wrapper.env.
# Kein activate, kein VIRTUAL_ENV — Aufruf über absolute Pfade.

PBREW_ROOT="${{PBREW_ROOT:-{prefix}}}"

# ── Konfiguration lesen ──────────────────────────────────────
PBREW_PYTHON_BIN=""

if [[ -f "$PBREW_ROOT/wrapper.env" ]]; then
    source "$PBREW_ROOT/wrapper.env"
elif [[ -f "/etc/pbrew/wrapper.env" ]]; then
    source "/etc/pbrew/wrapper.env"
fi

if [[ -z "$PBREW_PYTHON_BIN" ]] || [[ ! -x "$PBREW_PYTHON_BIN" ]]; then
    echo "pbrew: Kein Python-pbrew konfiguriert." >&2
    echo "" >&2
    if [[ -n "$PBREW_PYTHON_BIN" ]]; then
        echo "  Konfigurierter Pfad existiert nicht mehr:" >&2
        echo "    $PBREW_PYTHON_BIN" >&2
        echo "" >&2
    fi
    echo "  Lösung: pbrew aus der Umgebung aufrufen, in der es installiert ist:" >&2
    echo "    source /pfad/zum/venv/bin/activate && pbrew init" >&2
    echo "" >&2
    echo "  Oder manuell wrapper.env anlegen:" >&2
    echo "    echo 'PBREW_PYTHON_BIN=\\"/pfad/zum/venv/bin/pbrew\\"' > $PBREW_ROOT/wrapper.env" >&2
    exit 1
fi

# use/switch müssen Env-Variablen in der aktuellen Shell setzen.
# Unvermeidbar: Child-Prozess kann Parent-Env nicht direkt ändern.
case "$1" in
    use|switch)
        _output="$("$PBREW_PYTHON_BIN" "$@")"
        _rc=$?
        [[ $_rc -eq 0 ]] && builtin eval "$_output"
        exit $_rc
        ;;
    *)
        exec "$PBREW_PYTHON_BIN" "$@"
        ;;
esac
'''


def write_wrapper_script(prefix: Path, overwrite: bool = True) -> Path:
    """Schreibt das Wrapper-Skript nach {{prefix}}/bin/pbrew."""
    bdir = prefix / "bin"
    bdir.mkdir(parents=True, exist_ok=True)
    wrapper = bdir / "pbrew"
    if wrapper.exists() and not overwrite:
        return wrapper
    wrapper.write_text(generate_wrapper_script(prefix))
    wrapper.chmod(0o755)
    return wrapper
