import os
from pathlib import Path

# Marker-Strings zur Erkennung bestehender Integration (alt + neu).
# Wird von already_integrated() geprüft.
_MARKERS = ("pbrew shell-init", "pbrew/bin")


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
