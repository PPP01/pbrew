from pathlib import Path


def generate_pool_config(
    user: str,
    family: str,
    prefix: Path,
    debug: bool = False,
    pool_defaults: "dict | None" = None,
) -> str:
    """Generiert den Inhalt einer FPM Pool-Config-Datei."""
    suffix = family.replace(".", "")
    debug_suffix = "d" if debug else ""
    pool_name = f"{user}-debug" if debug else user
    socket = f"/run/php/php{suffix}{debug_suffix}-{user}.sock"

    defaults = {
        "pm": "dynamic",
        "pm_max_children": 5,
        "pm_start_servers": 2,
        "pm_min_spare_servers": 1,
        "pm_max_spare_servers": 3,
    }
    if pool_defaults:
        defaults.update(pool_defaults)

    return (
        f"; Pool {pool_name} — generiert von pbrew fpm pool add\n"
        f"[{pool_name}]\n"
        f"user = {user}\n"
        f"group = {user}\n"
        f"listen = {socket}\n"
        f"listen.owner = {user}\n"
        f"listen.group = www-data\n"
        f"listen.mode = 0660\n"
        f"pm = {defaults['pm']}\n"
        f"pm.max_children = {defaults['pm_max_children']}\n"
        f"pm.start_servers = {defaults['pm_start_servers']}\n"
        f"pm.min_spare_servers = {defaults['pm_min_spare_servers']}\n"
        f"pm.max_spare_servers = {defaults['pm_max_spare_servers']}\n"
    )


def pool_config_path(
    prefix: Path,
    family: str,
    user: str,
    debug: bool = False,
) -> Path:
    """Gibt den Pfad zur Pool-Config-Datei zurück."""
    subdir = f"{family}d" if debug else family
    return prefix / "etc" / "fpm" / subdir / "php-fpm.d" / f"{user}.conf"


def write_pool_config(
    prefix: Path,
    user: str,
    family: str,
    debug: bool = False,
    pool_defaults: "dict | None" = None,
) -> Path:
    """Schreibt Pool-Config. Überschreibt nicht, wenn bereits vorhanden."""
    path = pool_config_path(prefix, family, user, debug)
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(generate_pool_config(user, family, prefix, debug, pool_defaults))
    return path
