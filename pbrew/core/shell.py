import os
import re
from pathlib import Path

# Marker-Strings zur Erkennung bestehender Integration (alt + neu).
# Wird von already_integrated() geprüft.
_MARKERS = ("pbrew shell-init", "pbrew/bin", "pbrew-settings.sh")


SHELL_MAP: dict[str, dict] = {
    "bash": {"rc": "~/.bashrc"},
    "zsh":  {"rc": "~/.zshrc"},
    "fish": {"rc": "~/.config/fish/config.fish"},
}


def path_export_snippet(prefix: Path, shell: str) -> str:
    """Gibt das Shell-Snippet für die PATH-Erweiterung zurück."""
    bdir = prefix / "bin"
    if shell == "fish":
        return f"fish_add_path {bdir}"
    return f'export PATH="{bdir}:$PATH"'


def detect_shell() -> "str | None":
    """Erkennt die aktive Shell anhand von $SHELL. Gibt None zurück wenn unbekannt."""
    shell_path = os.environ.get("SHELL", "")
    name = Path(shell_path).name.lower()
    return name if name in SHELL_MAP else None


def _rc_file_for(shell: str) -> Path:
    """Gibt den Standardpfad zur RC-Datei für die angegebene Shell zurück."""
    return Path(SHELL_MAP[shell]["rc"]).expanduser()


def already_integrated(rc_file: Path) -> bool:
    """Prüft, ob pbrew bereits in der RC-Datei eingetragen ist (alt oder neu)."""
    if not rc_file.exists():
        return False
    text = rc_file.read_text()
    return any(marker in text for marker in _MARKERS)


def append_shell_integration(rc_file: Path, snippet: str) -> None:
    """Hängt den Shell-Integration-Snippet an die RC-Datei an."""
    rc_file.parent.mkdir(parents=True, exist_ok=True)
    with rc_file.open("a") as f:
        f.write(f"\n# pbrew — hinzugefügt von 'pbrew init'\n{snippet}\n")


def write_settings_file(prefix: Path) -> Path:
    """Schreibt prefix/pbrew-settings.sh und gibt deren Pfad zurück."""
    settings_file = prefix / "pbrew-settings.sh"
    bin_dir = prefix / "bin"
    content = (
        "# pbrew-settings.sh — generiert von 'pbrew init'\n"
        "# Automatisch erzeugt — Änderungen werden beim nächsten 'pbrew init' überschrieben\n"
        "\n"
        f'export PBREW_ROOT="{prefix}"\n'
        f'export PATH="{bin_dir}:$PATH"\n'
        "\n"
        "pbrew() {\n"
        '    if [ "$1" = "use" ] || [ "$1" = "switch" ] || [ "$1" = "unswitch" ] || [[ "$1" =~ ^[0-9]{2}$ ]] || [[ "$1" =~ ^[0-9]\.[0-9] ]]; then\n'
        "        local _pbrew_out\n"
        '        _pbrew_out="$(command pbrew "$@")"\n'
        "        local _pbrew_rc=$?\n"
        '        [ $_pbrew_rc -eq 0 ] && eval "$_pbrew_out"\n'
        "        return $_pbrew_rc\n"
        "    else\n"
        '        command pbrew "$@"\n'
        "    fi\n"
        "}\n"
        "\n"
        "# Persistenter Switch laden (gesetzt von 'pbrew switch')\n"
        '[ -f "$PBREW_ROOT/.switch" ] && source "$PBREW_ROOT/.switch"\n'
    )
    settings_file.write_text(content)
    return settings_file


def write_switch_files(prefix: Path, pbrew_path: Path, version: str) -> None:
    """Schreibt .switch (Bash/Zsh) und .switch.fish mit ENV-Export-Statements."""
    (prefix / ".switch").write_text(
        f'export PBREW_PATH="{pbrew_path}"\n'
        f'export PBREW_ACTIVE="{version}"\n'
    )
    (prefix / ".switch.fish").write_text(
        f'set -x PBREW_PATH "{pbrew_path}"\n'
        f'set -x PBREW_ACTIVE "{version}"\n'
    )


def replace_or_append_integration(rc_file: Path, new_snippet: str) -> bool:
    """Ersetzt einen alten pbrew-Eintrag in rc_file oder hängt new_snippet an.

    Gibt True zurück wenn ein alter Eintrag ersetzt wurde, False wenn new_snippet
    neu angehängt wurde (append_shell_integration).
    """
    if not rc_file.exists():
        append_shell_integration(rc_file, new_snippet)
        return False

    text = rc_file.read_text()

    # Prüfen ob ein alter Marker vorhanden ist oder das neue Snippet bereits eingetragen ist.
    # has_old erkennt alle bekannten alten und aktuellen pbrew-Eintrags-Stile.
    # has_new ist nur True wenn das exakte neue Snippet schon im Text steht –
    # verhindert Duplikate bei identischem Folgeaufruf, ohne alte source-Zeilen
    # fälschlicherweise als "bereits migriert" einzustufen.
    old_markers = ("pbrew/bin", "pbrew shell-init", "pbrew — hinzugefügt")
    has_old = any(m in text for m in old_markers)
    has_new = new_snippet in text

    if has_new and not has_old:
        return True

    if has_old:
        # Alten Block ersetzen: Kommentarzeile + die direkt folgende Inhalt-Zeile entfernen.
        # Das Muster trifft bewusst unabhängig vom Inhalt der Folgezeile, damit sowohl
        # der alte pbrew/bin-Stil als auch der source-pbrew-settings.sh-Stil korrekt
        # entfernt werden und kein Duplikat entsteht.
        new_text = re.sub(
            r"\n?[ \t]*# pbrew[^\n]*\n[^\n]+",
            "",
            text,
        )
        new_text = new_text.rstrip("\n") + f"\n\n# pbrew — hinzugefügt von 'pbrew init'\n{new_snippet}\n"
        rc_file.write_text(new_text)
        return True

    append_shell_integration(rc_file, new_snippet)
    return False
