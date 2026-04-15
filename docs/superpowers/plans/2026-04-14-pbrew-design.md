# pbrew – PHP Version Manager

Design-Spezifikation für einen Python-basierten PHP-Versionsmanager als Nachfolger von phpbrew.

**Status:** Entwurf
**Datum:** 2026-04-14
**Repository:** Eigenständiges Projekt auf GitHub (PPP01/pbrew)

## Motivation

phpbrew erfordert PHP zum Laufen – ein Hühnchen-Ei-Problem auf frischen Servern. Die corneltek-Dependencies sind tot und erfordern Forks. phpbrew baut PHP zweimal (CLI + FPM), obwohl ein Build genügt. Extension-INIs landen im falschen Verzeichnis bei custom scan-dirs. Das Config-Management erfordert jedes Mal die manuelle Angabe aller Build-Optionen.

pbrew löst diese Probleme: Python-basiert (überall vorinstalliert), ein Build für beide SAPIs, gespeicherte Build-Configs, automatische Upgrades mit Extension-Reinstallation, sauberes FPM-Pool-Management mit Xdebug-Trennung.

## Architektur

Monolithisches Python-Paket mit `click` als CLI-Framework. Einzige externe Dependency.

### Paketstruktur

```
pbrew/
├── cli/              → click-Commands (install, upgrade, use, ext, fpm, ...)
├── core/
│   ├── builder.py    → Configure, Make, Install
│   ├── resolver.py   → PHP-Versionen online abfragen, neueste finden
│   ├── config.py     → TOML-Config laden, mergen, validieren
│   └── state.py      → State-Dateien lesen/schreiben
├── fpm/
│   ├── pools.py      → Pool-Config-Generator
│   ├── services.py   → systemd-Service-Generator
│   └── xdebug.py     → Xdebug-FPM/CLI-Trennung
├── extensions/
│   ├── installer.py  → phpize/make/pecl Wrapper
│   └── pecl.py       → PECL-API-Client
├── shell/
│   ├── integration.py → Shell-Init (bashrc/zshrc)
│   ├── symlinks.py   → Symlink- und Wrapper-Management
│   └── switching.py  → use/switch Logik
└── utils/
    ├── deps.py       → apt-Dependency-Check
    ├── download.py   → HTTP-Download mit Fortschrittsbalken
    ├── health.py     → Post-Build Health-Checks
    └── log.py        → Logging und Build-Log-Management
```

### Mindest-Voraussetzungen

- Python 3.11+ (Ubuntu 22.04 hat 3.10, Ubuntu 24.04 hat 3.12)
- `click` als einzige externe Python-Dependency
- Build-Dependencies (gcc, make, autoconf, ...) werden per `pbrew doctor` geprüft

## Installationsstruktur

Konfigurierbar über `--prefix`. Default: `~/.pbrew/` (User-lokal). Für root/systemweit: `/opt/pbrew/`.

```
PREFIX/
├── versions/
│   ├── 8.4.20/                       ← ein Build
│   │   ├── bin/php, bin/php-fpm, bin/phpize, ...
│   │   ├── lib/, include/
│   │   └── etc/                      ← Build-generierte Defaults (nicht genutzt)
│   └── 8.4.22/                       ← neuerer Patch, parallel installiert
├── etc/
│   ├── cli/
│   │   ├── 8.4/php.ini              ← persistent, überlebt Patch-Upgrades
│   │   └── 8.5/php.ini
│   ├── fpm/
│   │   ├── 8.4/
│   │   │   ├── php.ini
│   │   │   ├── php-fpm.conf
│   │   │   └── php-fpm.d/
│   │   │       ├── alice.conf
│   │   │       └── bob.conf
│   │   └── 8.4d/                     ← nur auf Dev-Servern (xdebug.enabled = true)
│   │       ├── php.ini               ← mit Xdebug geladen
│   │       ├── php-fpm.conf
│   │       └── php-fpm.d/
│   │           ├── alice.conf
│   │           └── bob.conf
│   └── conf.d/
│       ├── 8.4/                      ← shared scan-dir (CLI + FPM, OHNE Xdebug)
│       │   ├── 00-base.ini           ← Timezone, Basics
│       │   ├── apcu.ini
│       │   └── opcache.ini           ← von User angepasst
│       ├── 8.4d/                     ← nur Xdebug-INI (Dev-Server)
│       │   └── xdebug.ini
│       └── 8.5/
├── configs/
│   ├── default.toml                  ← gemeinsame Build-Optionen
│   ├── 8.4.toml                      ← Family-Override (optional)
│   └── production.toml               ← benannte Variante (optional)
├── state/
│   ├── 8.4.toml                      ← aktive Version, Extensions, Config-Zuordnung
│   ├── 8.5.toml
│   ├── global.toml                   ← Default-Version (switch), PREFIX
│   └── logs/
│       ├── 8.4.22-build.log
│       └── 8.4.22-extensions.log
├── bin/
│   ├── pbrew                         ← das Tool selbst
│   ├── php84                         ← Wrapper-Script (ohne Xdebug)
│   ├── php84d                        ← Symlink (mit Xdebug, nur Dev)
│   ├── php85, php85d, ...
│   └── phpize84, php-config84, ...
└── services/                         ← generierte systemd-Units
    ├── php84-fpm.service
    ├── php84d-fpm.service
    └── pbrew-fpm-all.service
```

## Config-Format (TOML)

### default.toml – Gemeinsame Basis

```toml
[build]
jobs = "auto"                         # "auto" = $(nproc), oder feste Zahl
variants = ["default", "exif", "fpm", "intl", "mysql", "sqlite",
            "ftp", "soap", "tidy", "iconv", "gettext", "openssl", "opcache"]

[build.extra]
enable-gd = true
with-jpeg = "/usr/lib/x86_64-linux-gnu/"
with-xpm = "/usr/lib/x86_64-linux-gnu/"
with-webp = "/usr/lib/x86_64-linux-gnu/"
with-freetype = "/usr/include/freetype2/"
with-pdo-mysql = true
with-password-argon2 = true
with-gmp = true
with-sodium = true

[xdebug]
enabled = false                       # true nur auf Dev-Servern

[fpm]
pools_dir = "managed"                 # pbrew verwaltet die Pools

[fpm.pool_defaults]
pm = "dynamic"
pm_max_children = 5
pm_start_servers = 2
pm_min_spare_servers = 1
pm_max_spare_servers = 3
```

### Family-Override (configs/8.4.toml)

```toml
# Erbt alles aus default.toml, überschreibt nur Abweichungen
[build.extra]
with-config-file-scan-dir = "/opt/pbrew/etc/conf.d/8.4"
```

### Benannte Config-Variante (configs/production.toml)

```toml
# Für spezielle Setups: pbrew install 84 --config production
[build]
variants = ["default", "fpm", "mysql", "opcache"]

[build.extra]
enable-gd = false
with-sodium = false

[xdebug]
enabled = false
```

### Config-Auflösungsreihenfolge

1. Explizites `--config name` → `configs/name.toml`
2. Family-Config → `configs/8.4.toml`
3. Fallback → `configs/default.toml`
4. Nichts gefunden → interaktiv nach Optionen fragen und Config speichern

Beim Build wird die verwendete Config in der State-Datei gespeichert, damit `pbrew upgrade` sie automatisch wiederverwendet.

### State-Datei (state/8.4.toml)

```toml
active = "8.4.22"
previous = "8.4.20"
config = "production"                 # oder "default", "8.4", etc.
extensions = ["apcu", "opcache", "intl", "gd", "redis"]

[installed."8.4.22"]
installed_at = 2026-04-14T15:00:00Z
build_duration_seconds = 134

[installed."8.4.20"]
installed_at = 2026-03-10T09:00:00Z
build_duration_seconds = 128
```

## Build-System (Single-Build)

Ein Build erzeugt sowohl CLI- als auch FPM-Binary:

```bash
./configure \
  --prefix=PREFIX/versions/8.4.22 \
  --enable-cli \
  --enable-fpm \
  --with-fpm-systemd \
  --with-config-file-path=PREFIX/etc/cli/8.4 \
  --with-config-file-scan-dir=PREFIX/etc/conf.d/8.4 \
  [alle weiteren Optionen aus Config]

make -j BUILD_JOBS    # "auto" = $(nproc), oder feste Zahl aus Config / -j Flag
make install
```

### SAPI-Trennung bei Single-Build

`--with-config-file-path` wird für CLI ins Binary kompiliert. FPM nutzt den kompilierten Pfad nicht, sondern wird per systemd-Service mit explizitem Flag gestartet:

```bash
ExecStart=PREFIX/versions/8.4.22/sbin/php-fpm \
  --php-ini PREFIX/etc/fpm/8.4/php.ini \
  --fpm-config PREFIX/etc/fpm/8.4/php-fpm.conf \
  --nodaemonize
```

| SAPI | php.ini | scan-dir | Quelle |
| --- | --- | --- | --- |
| CLI | `PREFIX/etc/cli/8.4/php.ini` | `PREFIX/etc/conf.d/8.4/` | Kompiliert ins Binary |
| FPM | `PREFIX/etc/fpm/8.4/php.ini` | `PREFIX/etc/conf.d/8.4/` | Per `--php-ini` Flag |

### Post-Build-Schritte

1. `php.ini`: Aus `php.ini-production` nach `etc/cli/8.4/` und `etc/fpm/8.4/` kopieren – nur wenn noch nicht vorhanden
2. `00-base.ini`: Timezone und Basics in `etc/conf.d/8.4/` schreiben – nur wenn noch nicht vorhanden
3. Symlinks und Wrapper in `bin/` aktualisieren
4. systemd-Services neu generieren und reloaden
5. Extensions aus der vorherigen Patch-Version reinstallieren
6. Health-Check ausführen
7. FPM restarten

### Build-Jobs

In der Config als `jobs = "auto"` (= `nproc`) oder feste Zahl. CLI-Override: `pbrew install 84 -j 4`.

## CLI-Commands

### Versions-Auflösung

Die PHP-Family kann überall angegeben werden – als Argument oder mit Kurzform vorangestellt. Beide Schreibweisen werden akzeptiert: `84` und `8.4`.

**Auflösungsreihenfolge:**

1. Explizit angegeben (`84` als Argument oder `pbrew 84 ...` Kurzform)
2. Aktive Session-Version (`PBREW_PHP` ENV-Variable, gesetzt durch `pbrew use`)
3. Permanent gesetzte Version (`pbrew switch`, gespeichert in `state/global.toml`)
4. Nichts gesetzt → Fehlermeldung

### Command-Übersicht

```bash
# Installation & Build
pbrew install 84                        # neueste 8.4.x bauen
pbrew install 8.4.22                    # exakte Version bauen
pbrew install 84 --config production    # mit benannter Config
pbrew install 84 --save                 # bauen UND Config speichern
pbrew install 84 -j 4                   # Build-Jobs überschreiben

# Upgrade
pbrew upgrade                           # alle Families aktualisieren
pbrew upgrade 84                        # nur 8.4 auf neuestes Patch-Level
pbrew upgrade --dry-run                 # nur zeigen was sich ändern würde
pbrew rollback 84                       # auf vorherige Patch-Version zurück

# Versionswechsel
pbrew list                              # installierte Versionen anzeigen
pbrew use 84                            # für aktuelle Shell-Session
pbrew use 8.4.20                        # exakte Version für Session
pbrew switch 84                         # permanent als Default
pbrew 84                                # Shortcut für pbrew use 84

# Extensions
pbrew ext install apcu                  # für aktive PHP-Version
pbrew ext install xdebug 84             # für bestimmte Family
pbrew ext install xdebug 84 -v 3.2.0   # exakte Extension-Version
pbrew ext install xdebug latest         # explizit neueste
pbrew ext install redis --pecl          # via PECL
pbrew ext remove apcu 84
pbrew ext enable apcu 84
pbrew ext disable apcu 84
pbrew ext list 84
pbrew ext list 84 --available           # verfügbare PECL-Extensions

# FPM
pbrew fpm status                        # Übersicht aller Services
pbrew fpm restart 84                    # systemctl restart php84-fpm
pbrew fpm restart 84d                   # Debug-FPM restarten
pbrew fpm restart all                   # alle Instanzen
pbrew fpm pool add alice 84             # Pool-Config generieren
pbrew fpm pool add alice 84 --template custom.conf
pbrew fpm pool remove alice 84
pbrew fpm pool list 84

# Config
pbrew config edit 84                    # TOML im $EDITOR öffnen
pbrew config show 84                    # aktive Config anzeigen

# Info & Wartung
pbrew known                             # verfügbare PHP-Versionen online
pbrew info 84                           # Build-Details, Pfade, Extensions
pbrew clean 8.4.17                      # alte Patch-Version entfernen
pbrew log 84                            # letztes Build-Log
pbrew log 84 --tail                     # live mitverfolgen
pbrew doctor                            # Gesamtsystem-Check
```

### `pbrew list` Ausgabe

```
pbrew — installierte PHP-Versionen

  Family   Aktiv      Vorherige   CLI     FPM       Xdebug    Extensions
  8.3      8.3.32     8.3.30      php83   active    —         apcu, opcache, intl, gd
  8.4      8.4.22     8.4.20      php84   active    php84d    apcu, opcache, intl, gd, redis
  8.5      8.5.5      —           php85   active    php85d    apcu, opcache, intl, gd

  * php84 ist der aktuelle Default (pbrew switch)
```

## Upgrade-Workflow

### `pbrew upgrade 84`

```
Prüfe verfügbare Updates...
  8.4: 8.4.20 → 8.4.22 verfügbar

[1/1] Baue 8.4.22...
  → Lade php-8.4.22.tar.bz2 herunter...
  → Prüfe Build-Dependencies... ✓
  → Baue mit Config "production" (configs/production.toml)...
  → Build abgeschlossen (2:14)
  → Reinstalliere Extensions: apcu, redis
  → Bundled Extensions OK: opcache, intl, gd
  → Health-Check...
    ✓ php -v
    ✓ php -m — alle Extensions geladen
    ✓ argon2: password_hash() funktioniert
    ✓ gd: JPEG/WebP/Freetype Support vorhanden
    ✓ php-fpm -t — Config-Syntax OK
  → php.ini-production hat sich geändert:
    + opcache.jit_buffer_size default: 64M → 128M
    + Neue Direktive: openssl.default_ec_curve
    [J]a übernehmen (alte als .bak) / [N]ein behalten (neue als .dist) / [D]iff anzeigen? n
    → Neue php.ini als php.ini.dist abgelegt
  → Aktualisiere Symlinks und Wrapper
  → Generiere systemd-Services
  → Prüfe alte Sockets entfernt... ✓
  → Restarte php84-fpm.service ✓
  ✓ 8.4.22 aktiv

Alte Versionen:
  8.4.20 (vorherige) — 245 MB
  8.4.17 (älter)     — 245 MB

[B]ehalten / [V]orherige behalten, ältere entfernen / [A]lle entfernen? v
  ✓ 8.4.20 behalten (Rollback möglich)
  ✗ 8.4.17 entfernt
```

### Config-Diff Handling (à la apt)

Bei Upgrade prüft pbrew ob sich `php.ini-production` upstream geändert hat:

- **[J]a übernehmen:** Neue Version wird aktiv, alte wird als `.bak` gesichert
- **[N]ein behalten:** Bestehende bleibt aktiv, neue wird als `.dist` abgelegt
- **[D]iff anzeigen:** Diff wird angezeigt, danach erneut J/N-Frage

### Rollback

```bash
pbrew rollback 84                       # wechselt zurück auf 8.4.20
```

1. Symlinks/Wrapper zurück auf 8.4.20
2. systemd-Services neu generieren
3. Alte Sockets-Prüfung
4. FPM restarten
5. Health-Check

## FPM-Management

### Pool-Struktur

Pro User und PHP-Family eine Pool-Config:

```ini
; PREFIX/etc/fpm/8.4/php-fpm.d/alice.conf
[alice]
user = alice
group = alice
listen = /run/php/php84-alice.sock
listen.owner = alice
listen.group = www-data
listen.mode = 0660
pm = dynamic
pm.max_children = 5
pm.start_servers = 2
pm.min_spare_servers = 1
pm.max_spare_servers = 3
```

Debug-Pools (nur bei `xdebug.enabled = true`) bekommen den `d`-Suffix:

```ini
; PREFIX/etc/fpm/8.4d/php-fpm.d/alice.conf
[alice-debug]
listen = /run/php/php84d-alice.sock
; Rest identisch
```

### systemd-Services

Generiert in `/etc/systemd/system/`:

```ini
# php84-fpm.service
[Unit]
Description=PHP 8.4 FPM (pbrew)
After=network.target

[Service]
Type=notify
ExecStart=PREFIX/versions/8.4.22/sbin/php-fpm \
  --php-ini PREFIX/etc/fpm/8.4/php.ini \
  --fpm-config PREFIX/etc/fpm/8.4/php-fpm.conf \
  --nodaemonize
ExecReload=/bin/kill -USR2 $MAINPID
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```ini
# pbrew-fpm-all.service
[Unit]
Description=All pbrew PHP-FPM instances
Wants=php83-fpm.service php84-fpm.service php85-fpm.service

[Service]
Type=oneshot
ExecStart=/bin/true
RemainAfterExit=yes
```

### FPM-Restart-Sicherheit

Bei jedem FPM-Restart (manuell oder nach Upgrade):

1. Alten FPM-Prozess stoppen
2. Prüfen dass alle alten Sockets entfernt sind (Timeout 5s, dann Force-Remove)
3. Neuen FPM-Master starten
4. Prüfen dass neue Sockets erstellt wurden
5. Bei Fehler: Rollback auf vorherige Version anbieten

## Xdebug-Trennung

### Voraussetzung

`xdebug.enabled = true` in der Config. Nur auf Dev-Servern.

### Prinzip: Separater scan-dir statt `-n` Hack

Xdebug.ini liegt in einem eigenen Unterverzeichnis, das nur die Debug-Varianten einbinden:

```
PREFIX/etc/conf.d/
├── 8.4/                    ← shared scan-dir (OHNE Xdebug)
│   ├── 00-base.ini
│   ├── apcu.ini
│   └── opcache.ini
└── 8.4d/                   ← nur Xdebug-INI
    └── xdebug.ini
```

### CLI

```bash
# PREFIX/bin/php84 — ohne Xdebug (normaler Aufruf, scan-dir hat kein xdebug.ini)
#!/bin/bash
exec PREFIX/versions/8.4.22/bin/php "$@"

# PREFIX/bin/php84d — mit Xdebug (zusätzlicher scan-dir)
#!/bin/bash
export PHP_INI_SCAN_DIR="PREFIX/etc/conf.d/8.4:PREFIX/etc/conf.d/8.4d"
exec PREFIX/versions/8.4.22/bin/php "$@"
```

`php84` funktioniert direkt – der kompilierte scan-dir (`conf.d/8.4/`) enthält kein Xdebug. `php84d` erweitert den scan-dir per `PHP_INI_SCAN_DIR` um das Xdebug-Verzeichnis. Kein `-n` Hack nötig, alle Extensions bleiben geladen.

### FPM

Zwei separate Master-Prozesse pro Family:
- `php84-fpm.service` → scan-dir: `conf.d/8.4/` (ohne Xdebug), Sockets: `php84-user.sock`
- `php84d-fpm.service` → scan-dir: `conf.d/8.4/:conf.d/8.4d/` (mit Xdebug), Sockets: `php84d-user.sock`

Der Debug-FPM-Service setzt `PHP_INI_SCAN_DIR` in der systemd-Unit:

```ini
[Service]
Environment="PHP_INI_SCAN_DIR=PREFIX/etc/conf.d/8.4:PREFIX/etc/conf.d/8.4d"
ExecStart=PREFIX/versions/8.4.22/sbin/php-fpm \
  --php-ini PREFIX/etc/fpm/8.4/php.ini \
  --fpm-config PREFIX/etc/fpm/8.4d/php-fpm.conf \
  --nodaemonize
```

## Extension-Management

### Installation

```bash
pbrew ext install apcu                  # neueste stabile Version
pbrew ext install xdebug 84 -v 3.2.0   # exakte Version
pbrew ext install redis --pecl          # via PECL
```

### Build-Ablauf

1. Version ermitteln: PECL-API nach stabilster Version fragen (oder `-v` nutzen)
2. Tarball herunterladen und entpacken
3. `phpize` → `./configure` → `make -j` → `make install`
4. INI-Datei in shared scan-dir schreiben: `PREFIX/etc/conf.d/8.4/apcu.ini`
5. Extension in State-Datei registrieren

### INI-Handling

- Neue INI nur anlegen wenn Datei **nicht existiert**
- Bestehende INIs werden **nie überschrieben**
- Bei bereits vorhandener INI: `Config bereits vorhanden: .../opcache.ini (beibehalten)`

### Extension-Typen

| Typ | Beispiele | Handling |
| --- | --- | --- |
| Bundled | opcache, intl, gd, exif | Werden beim PHP-Build mitkompiliert via Variants |
| PECL | apcu, redis, xdebug | Separat per `pbrew ext install` |

### Reinstallation bei Upgrade

Extensions sind gegen eine PHP-Version kompiliert. Bei `pbrew upgrade`:

1. PECL-Extensions werden für die neue Version neu gebaut
2. Dabei wird geprüft ob eine neuere Extension-Version verfügbar ist
3. Bundled Extensions kommen mit dem PHP-Build

## Health-Check

Wird automatisch nach jedem `install` und `upgrade` ausgeführt.

### Basis-Checks (immer)

- `php -v` funktioniert
- `php -m` — alle erwarteten Extensions geladen
- `php-fpm -t` — FPM Config-Syntax OK
- systemd-Service startet

### Feature-spezifische Checks (je nach Config)

| Config-Option | Test |
| --- | --- |
| `with-password-argon2` | `php -r "password_hash('test', PASSWORD_ARGON2ID);"` |
| `enable-gd` + `with-jpeg` | `php -r "var_dump(gd_info());"` → JPEG/WebP/Freetype prüfen |
| `with-openssl` | `php -r "openssl_random_pseudo_bytes(32);"` |
| `enable-intl` | `php -r "new IntlDateFormatter('de_DE');"` |
| `with-sodium` | `php -r "sodium_crypto_secretbox_keygen();"` |
| `with-pdo-mysql` | `php -r "new PDO('mysql:host=localhost');"` (Verbindung darf fehlschlagen, Extension muss laden) |
| Extension `apcu` | `php -r "apcu_enabled();"` |
| Extension `redis` | `php -r "new Redis();"` |
| Extension `xdebug` | `php84d -r "var_dump(xdebug_info());"` (nur php*d*) |

### `pbrew doctor`

Umfassende Systemprüfung:

```
$ pbrew doctor
Prüfe pbrew-Installation...
  ✓ Python 3.12
  ✓ Build-Dependencies vollständig
  ✓ Symlinks konsistent
  ✓ systemd-Services synchron mit installierten Versionen
  ✓ Configs vorhanden für alle Families
  ✓ Keine verwaisten Extensions
  ✓ Alle FPM-Sockets erreichbar
  ✗ php83-fpm.service läuft, aber 8.3 ist nicht mehr installiert
```

## Dependency-Check

Vor jedem Build prüft pbrew ob die nötigen apt-Pakete installiert sind:

```
$ pbrew install 84
Prüfe Build-Abhängigkeiten...
  ✓ gcc        ✓ make       ✓ autoconf
  ✓ libxml2    ✓ libssl     ✓ libsqlite3
  ✗ libgmp-dev — fehlt
  ✗ libtidy-dev — fehlt

Installieren? [J/n] j
  → apt install libgmp-dev libtidy-dev
```

pbrew führt ein Mapping von Variants/Extra-Options zu apt-Paketnamen. Dieses Mapping ist konfigurierbar und erweiterbar.

## Shell-Integration

### Aktivierung

```bash
# In ~/.bashrc oder ~/.zshrc:
eval "$(pbrew shell-init bash)"     # oder: zsh
```

### Was `shell-init` macht

- `PATH` erweitern um `PREFIX/bin`
- Shell-Funktionen für `pbrew use` (setzt `PBREW_PHP` ENV-Variable)
- Auto-Completion für alle Commands registrieren

## Dokumentation (v1)

```
docs/
├── README.md              ← Quickstart, Installation
├── installation.md        ← System-Requirements, Pfade
├── configuration.md       ← TOML-Config-Referenz
├── commands.md            ← Alle Commands mit Beispielen
├── fpm-management.md      ← Pools, Services, Xdebug
├── upgrade-workflow.md    ← Upgrade, Rollback, Extension-Handling
└── migration-phpbrew.md   ← Umstieg von phpbrew
```

## Backlog (v2)

| Feature | Beschreibung |
| --- | --- |
| Parallel-Build | `pbrew upgrade --parallel` — mehrere Families gleichzeitig |
| Backup/Restore | `pbrew backup` / `pbrew restore` — Configs + State exportieren/importieren |
| Nginx-Snippets | `pbrew nginx snippet alice 84` — upstream-Config für Copy/Paste |
| Cron-Checker | `pbrew watch` — prüft täglich auf neue Versionen, Benachrichtigung |
| Migration | `pbrew migrate-from-phpbrew` — importiert Builds, Configs, Pools |
| Build-Cache | Configure-Ergebnis cachen, nur make bei gleichen Optionen |
| Multi-OS | Support für RHEL/Alpine neben Debian/Ubuntu |
