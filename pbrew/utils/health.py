import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CheckResult:
    name: str
    ok: bool
    message: str = ""


def check_php_version(php_bin: Path) -> CheckResult:
    try:
        result = subprocess.run(
            [str(php_bin), "-v"],
            capture_output=True, text=True, timeout=10,
        )
        ok = result.returncode == 0 and "PHP" in result.stdout
        msg = result.stdout.splitlines()[0] if ok else result.stderr.strip()
        return CheckResult("php -v", ok, msg)
    except Exception as exc:
        return CheckResult("php -v", False, str(exc))


def check_extensions_loaded(php_bin: Path, expected: list[str]) -> list[CheckResult]:
    try:
        result = subprocess.run(
            [str(php_bin), "-m"],
            capture_output=True, text=True, timeout=10,
        )
        loaded = {line.strip().lower() for line in result.stdout.splitlines()}
        return [
            CheckResult(
                f"ext:{ext}",
                ext.lower() in loaded,
                "" if ext.lower() in loaded else f"{ext} nicht geladen",
            )
            for ext in expected
        ]
    except Exception as exc:
        return [CheckResult("php -m", False, str(exc))]


def check_fpm_config(fpm_bin: Path, ini: Path, fpm_conf: Path) -> CheckResult:
    try:
        result = subprocess.run(
            [str(fpm_bin), f"--php-ini={ini}", f"--fpm-config={fpm_conf}", "-t"],
            capture_output=True, text=True, timeout=10,
        )
        ok = result.returncode == 0
        return CheckResult("php-fpm -t", ok, result.stderr.strip())
    except Exception as exc:
        return CheckResult("php-fpm -t", False, str(exc))


def check_scan_dir(php_bin: Path, expected: Path) -> CheckResult:
    """Prüft ob der kompilierte scan-dir mit dem erwarteten Pfad übereinstimmt."""
    try:
        result = subprocess.run(
            [str(php_bin), "--ini"],
            capture_output=True, text=True, timeout=10,
        )
        for line in result.stdout.splitlines():
            if "Scan for additional" in line:
                parts = line.split(":", 1)
                if len(parts) < 2:
                    continue
                raw = parts[1].strip()
                if raw == "(none)":
                    return CheckResult(
                        "scan-dir",
                        False,
                        f"PHP meldet scan-dir als (none), erwartet: {expected}",
                    )
                if raw.startswith('"') or raw.startswith("'"):
                    return CheckResult(
                        "scan-dir",
                        False,
                        f"scan-dir enthält Anführungszeichen im Pfad: {raw!r} "
                        f"(erwartet: {expected})",
                    )
                actual = Path(raw)
                ok = actual == expected
                msg = "" if ok else f"erwartet {expected}, Binary hat {actual}"
                return CheckResult("scan-dir", ok, msg)
        return CheckResult("scan-dir", False, "scan-dir-Zeile nicht in php --ini gefunden")
    except Exception as exc:
        return CheckResult("scan-dir", False, str(exc))


def run_basic_checks(prefix: "Path", version: str, family: str, config: dict) -> list[CheckResult]:
    """Führt alle Health-Checks nach einem Build aus."""
    from pbrew.core.paths import version_bin, confd_dir

    php_bin = version_bin(prefix, version, "php")
    results = [check_php_version(php_bin)]
    results.append(check_scan_dir(php_bin, confd_dir(prefix, family)))

    _bundled_map = {
        "intl": "intl", "opcache": "Zend OPcache",
        "exif": "exif", "gd": "gd",
    }
    variants = config.get("build", {}).get("variants", [])
    expected = [_bundled_map[v] for v in variants if v in _bundled_map]
    if expected:
        results.extend(check_extensions_loaded(php_bin, expected))

    extra = config.get("build", {}).get("extra", {})
    if extra.get("with-password-argon2"):
        results.append(_feature_check(php_bin, "argon2",
            "password_hash('x', PASSWORD_ARGON2ID); echo 'ok';"))
    if extra.get("with-sodium"):
        results.append(_feature_check(php_bin, "sodium",
            "sodium_crypto_secretbox_keygen(); echo 'ok';"))
    if extra.get("enable-gd") and extra.get("with-jpeg"):
        results.append(_feature_check(php_bin, "gd:jpeg",
            "var_dump(gd_info()['JPEG Support'] === true);"))

    return results


def _feature_check(php_bin: Path, name: str, code: str) -> CheckResult:
    try:
        result = subprocess.run(
            [str(php_bin), "-r", code],
            capture_output=True, text=True, timeout=10,
        )
        ok = result.returncode == 0
        return CheckResult(f"feature:{name}", ok, result.stderr.strip() if not ok else "")
    except Exception as exc:
        return CheckResult(f"feature:{name}", False, str(exc))
