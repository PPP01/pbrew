@.claude/lessons.md

# pbrew

Python-basierter PHP-Versionsmanager. Eigenständiges Projekt, kein Teil von phpbrew.

## Tech-Stack

- Python 3.11+
- click 8.x (CLI-Framework)
- tomlkit 0.12+ (TOML lesen und schreiben)
- pytest 8.x (Tests)

## Wichtige Befehle

```bash
# Virtuelle Umgebung aktivieren
source .venv/bin/activate

# Dependencies installieren
pip install -e ".[dev]"

# Tests ausführen
pytest -v

# pbrew direkt ausführen
pbrew --help
```

## Verzeichnisstruktur

- `pbrew/cli/` – Click-Commands (je Command eine Datei)
- `pbrew/core/` – Kernlogik (paths, config, state, resolver, builder)
- `pbrew/utils/` – Hilfsfunktionen (download, health)
- `tests/` – Pytest-Tests (TDD: erst Test, dann Implementation)

## Implementierungsplan

Der vollständige Plan liegt unter:
`docs/superpowers/plans/2026-04-15-pbrew-foundation.md`

Zum Ausführen des Plans den Skill `superpowers:executing-plans` oder
`superpowers:subagent-driven-development` verwenden.

## Design-Spec

Vollständige Spezifikation:
`docs/superpowers/plans/2026-04-14-pbrew-design.md`

## Herkunft

Entwickelt als Nachfolger von [phpbrew/phpbrew](https://github.com/phpbrew/phpbrew),
entstanden im Fork-Projekt PPP01/phpbrew.
