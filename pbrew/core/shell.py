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


def write_settings_file(prefix: Path, pbrew_bin: Path) -> Path:
    """Schreibt prefix/pbrew-settings.sh und gibt deren Pfad zurück."""
    bin_dir = pbrew_bin.parent
    settings_file = prefix / "pbrew-settings.sh"
    content = (
        "# pbrew-settings.sh — generiert von 'pbrew init'\n"
        "# Automatisch erzeugt — Änderungen werden beim nächsten 'pbrew init' überschrieben\n"
        "\n"
        f'export PBREW_ROOT="{prefix}"\n'
        f'export PATH="{bin_dir}:$PATH"\n'
        "\n"
        "pbrew() {\n"
        '    if [ "$1" = "use" ] || [ "$1" = "switch" ] || [ "$1" = "unswitch" ]; then\n'
        '        eval "$(command pbrew "$@")"\n'
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


def replace_or_append_integration(rc_file: Path, new_snippet: str) -> bool:
    """Ersetzt einen alten pbrew-Eintrag in rc_file oder hängt new_snippet an.

    Gibt True zurück wenn ein alter Eintrag ersetzt wurde, False wenn new_snippet
    neu angehängt wurde (append_shell_integration).
    """
    if not rc_file.exists():
        append_shell_integration(rc_file, new_snippet)
        return False

    text = rc_file.read_text()

    # Prüfen ob ein alter Marker (pbrew/bin oder pbrew shell-init) vorhanden ist,
    # aber noch nicht der neue Marker (pbrew-settings.sh).
    old_markers = ("pbrew/bin", "pbrew shell-init", "pbrew — hinzugefügt")
    has_old = any(m in text for m in old_markers)
    has_new = "pbrew-settings.sh" in text

    if has_new:
        # Bereits auf neuem Stand – nichts tun, kein Duplikat erzeugen
        return True

    if has_old:
        # Alten Block ersetzen: Kommentarzeile + Snippet-Zeile(n) entfernen
        # Muster: optionale Leerzeile, Kommentar "# pbrew …", dann die eigentliche Zeile
        new_text = re.sub(
            r"\n?# pbrew[^\n]*\n[^\n]*(?:pbrew/bin|pbrew shell-init)[^\n]*\n?",
            "",
            text,
        )
        new_text = new_text.rstrip("\n") + f"\n\n# pbrew — hinzugefügt von 'pbrew init'\n{new_snippet}\n"
        rc_file.write_text(new_text)
        return True

    append_shell_integration(rc_file, new_snippet)
    return False
