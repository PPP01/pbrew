"""Generiert das statische Bash-Wrapper-Skript für ~/.pbrew/bin/pbrew.

Das Skript findet das Python-pbrew automatisch:
1. Dediziertes venv unter $PBREW_ROOT/.venv/
2. Global installiertes pbrew im PATH
3. Auto-Setup: venv anlegen + pip install

Kein `activate`, kein VIRTUAL_ENV, kein PATH-Manipulation.
Binaries werden immer über absolute Pfade aufgerufen.
"""
from pathlib import Path


def generate_wrapper_script(prefix: Path) -> str:
    """Gibt den Inhalt des Bash-Wrapper-Skripts zurück mit eingebackenem Prefix."""
    return f'''\
#!/bin/bash
# pbrew — PHP Version Manager (Wrapper)
# Generiert von 'pbrew init'. Findet das Python-pbrew automatisch.
# Kein activate, kein VIRTUAL_ENV — Aufruf über absolute Pfade.

PBREW_ROOT="${{PBREW_ROOT:-{prefix}}}"

# ── Prüfkette: wo ist das echte Python-pbrew? ─────────────────
if [[ -x "$PBREW_ROOT/.venv/bin/pbrew" ]]; then
    # 1. Dediziertes venv (häufigster Fall)
    _pbrew="$PBREW_ROOT/.venv/bin/pbrew"

elif _global=$(PATH="${{PATH//$PBREW_ROOT\\/bin:/}}" command -v pbrew 2>/dev/null); then
    # 2. Global installiert (pip install pbrew system-weit oder --user)
    _pbrew="$_global"

else
    # 3. Ersteinrichtung: venv anlegen
    echo "pbrew: Richte Python-Umgebung ein..." >&2
    python3 -m venv "$PBREW_ROOT/.venv" || {{ echo "pbrew: python3 -m venv fehlgeschlagen" >&2; exit 1; }}
    "$PBREW_ROOT/.venv/bin/pip" install -q pbrew || {{ echo "pbrew: pip install pbrew fehlgeschlagen" >&2; exit 1; }}
    _pbrew="$PBREW_ROOT/.venv/bin/pbrew"
fi

# use/switch müssen Env-Variablen in der aktuellen Shell setzen.
# Das ist der einzige Punkt, an dem die Ausgabe des Python-Prozesses
# als Shell-Code interpretiert wird — unvermeidbar, weil ein
# Child-Prozess die Env des Parents nicht direkt ändern kann.
case "$1" in
    use|switch)
        _output="$("$_pbrew" "$@")"
        _rc=$?
        [[ $_rc -eq 0 ]] && builtin eval "$_output"
        exit $_rc
        ;;
    *)
        exec "$_pbrew" "$@"
        ;;
esac
'''


def write_wrapper_script(prefix: Path, overwrite: bool = True) -> Path:
    """Schreibt das Wrapper-Skript nach {prefix}/bin/pbrew."""
    bdir = prefix / "bin"
    bdir.mkdir(parents=True, exist_ok=True)
    wrapper = bdir / "pbrew"
    if wrapper.exists() and not overwrite:
        return wrapper
    wrapper.write_text(generate_wrapper_script(prefix))
    wrapper.chmod(0o755)
    return wrapper
