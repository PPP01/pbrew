import subprocess
from pathlib import Path


def service_name(family: str, debug: bool = False) -> str:
    """Gibt den systemd-Service-Namen zurück, z.B. 'php84-fpm'."""
    suffix = family.replace(".", "")
    debug_suffix = "d" if debug else ""
    return f"php{suffix}{debug_suffix}-fpm"


def service_path(family: str, debug: bool = False) -> Path:
    """Gibt den Pfad zur systemd Unit-Datei zurück."""
    return Path("/etc/systemd/system") / f"{service_name(family, debug)}.service"


def generate_fpm_service(
    prefix: Path,
    version: str,
    family: str,
    debug: bool = False,
) -> str:
    """Generiert den Inhalt einer systemd FPM Unit."""
    desc_suffix = " (Xdebug)" if debug else ""
    fpm_bin = prefix / "versions" / version / "sbin" / "php-fpm"
    php_ini = prefix / "etc" / "fpm" / family / "php.ini"
    fpm_conf_subdir = f"{family}d" if debug else family
    fpm_conf = prefix / "etc" / "fpm" / fpm_conf_subdir / "php-fpm.conf"

    env_block = ""
    if debug:
        scan_normal = prefix / "etc" / "conf.d" / family
        scan_debug = prefix / "etc" / "conf.d" / f"{family}d"
        env_block = f'Environment="PHP_INI_SCAN_DIR={scan_normal}:{scan_debug}"\n'

    return (
        f"[Unit]\n"
        f"Description=PHP {version} FPM{desc_suffix} (pbrew)\n"
        f"After=network.target\n"
        f"\n"
        f"[Service]\n"
        f"Type=notify\n"
        f"{env_block}"
        f"ExecStart={fpm_bin} \\\n"
        f"  --php-ini {php_ini} \\\n"
        f"  --fpm-config {fpm_conf} \\\n"
        f"  --nodaemonize\n"
        f"ExecReload=/bin/kill -USR2 $MAINPID\n"
        f"Restart=on-failure\n"
        f"\n"
        f"[Install]\n"
        f"WantedBy=multi-user.target\n"
    )


def write_service(
    prefix: Path,
    version: str,
    family: str,
    debug: bool = False,
) -> Path:
    """Schreibt systemd Unit nach /etc/systemd/system/ (benötigt root)."""
    path = service_path(family, debug)
    path.write_text(generate_fpm_service(prefix, version, family, debug))
    return path


def reload_systemd() -> None:
    subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
