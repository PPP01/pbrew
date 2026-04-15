import hashlib
import urllib.request
from pathlib import Path

_CHUNK = 65536  # 64 KB


def download(url: str, dest: Path, expected_sha256: str = "") -> None:
    """Lädt url nach dest herunter. Prüft SHA-256 wenn angegeben."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    sha256 = hashlib.sha256()

    with urllib.request.urlopen(url, timeout=60) as response:
        total = int(response.headers.get("Content-Length", 0))
        downloaded = 0

        with open(dest, "wb") as f:
            while True:
                chunk = response.read(_CHUNK)
                if not chunk:
                    break
                f.write(chunk)
                sha256.update(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded * 100 // total
                    mb = downloaded / 1_048_576
                    total_mb = total / 1_048_576
                    print(f"\r  {mb:.1f} / {total_mb:.1f} MB ({pct}%)", end="", flush=True)

    if total:
        print()  # Zeilenumbruch nach Fortschrittszeile

    if expected_sha256 and sha256.hexdigest() != expected_sha256:
        dest.unlink(missing_ok=True)
        raise ValueError(
            f"SHA-256 Prüfung fehlgeschlagen: erwartet {expected_sha256}, erhalten {sha256.hexdigest()}"
        )
