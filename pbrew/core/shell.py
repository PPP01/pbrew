import os
from pathlib import Path

_MARKER = "pbrew shell-init"

SHELL_MAP: dict[str, dict] = {
    "bash": {
        "snippet": 'eval "$(pbrew shell-init bash)"',
        "rc": "~/.bashrc",
    },
    "zsh": {
        "snippet": 'eval "$(pbrew shell-init zsh)"',
        "rc": "~/.zshrc",
    },
    "fish": {
        "snippet": "pbrew shell-init fish | source",
        "rc": "~/.config/fish/config.fish",
    },
}


def detect_shell() -> "str | None":
    """Erkennt die aktive Shell anhand von $SHELL. Gibt None zurück wenn unbekannt."""
    shell_path = os.environ.get("SHELL", "")
    name = Path(shell_path).name.lower()
    return name if name in SHELL_MAP else None


def _rc_file_for(shell: str) -> Path:
    """Gibt den Standardpfad zur RC-Datei für die angegebene Shell zurück."""
    return Path(SHELL_MAP[shell]["rc"]).expanduser()


def already_integrated(rc_file: Path) -> bool:
    """Prüft, ob pbrew bereits in der RC-Datei eingetragen ist."""
    if not rc_file.exists():
        return False
    return _MARKER in rc_file.read_text()


def append_shell_integration(rc_file: Path, snippet: str) -> None:
    """Hängt den Shell-Integration-Snippet an die RC-Datei an."""
    rc_file.parent.mkdir(parents=True, exist_ok=True)
    with rc_file.open("a") as f:
        f.write(f"\n# pbrew — hinzugefügt von 'pbrew init'\n{snippet}\n")
