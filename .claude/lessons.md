# Team-Learnings — pbrew

## Architektur & Konventionen

## Bekannte Fallen & Gotchas

### questionary in Tests

Beim Testen von Funktionen, die `questionary` verwenden, immer `unittest.mock.patch` auf den Modulpfad `pbrew.cli.ext.questionary.checkbox` / `.select` / `.text` anwenden – nicht auf `questionary.*` global. Nur so greift der Patch in der richtigen Import-Namespace-Kopie.

Zusätzlich `_is_tty` via `patch("pbrew.cli.ext._is_tty", return_value=True)` mocken, nicht `sys.stdin.isatty` direkt – der Click `CliRunner` ersetzt `sys.stdin`, sodass ein Patch auf `sys.stdin.isatty` ins Leere greift.

### VARIANT_FLAGS / VARIANT_EXTENSIONS

`_VARIANT_FLAGS` ist jetzt öffentlich als `VARIANT_FLAGS` exportiert. SAPI-Einträge (`cli`, `fpm`, `fpm-systemd`) sind in `VARIANT_EXTENSIONS` nicht enthalten – `VARIANT_EXTENSIONS` listet ausschließlich echte Extension-Varianten. Bei Iterationen über Extension-Varianten immer `VARIANT_EXTENSIONS` verwenden, nicht `VARIANT_FLAGS`.
