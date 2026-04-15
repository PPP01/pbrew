import os
import subprocess
from pathlib import Path
from typing import IO

from pbrew.core.paths import version_dir, cli_ini_dir, confd_dir

# Variant → Liste von configure-Flags.
# Explizites Mapping statt Heuristik: einige Variants brauchen mehrere Flags
# (z.B. mysql → mysqli + pdo-mysql mit mysqlnd-Treiber), manche hängen von
# externen Libs ab und müssen --with- statt --enable- nutzen.
_VARIANT_FLAGS: dict[str, list[str]] = {
    # Built-in / SAPI
    "cli":          ["--enable-cli"],
    "fpm":          ["--enable-fpm"],
    "fpm-systemd":  ["--enable-fpm", "--with-fpm-systemd"],  # braucht libsystemd-dev
    # Core-Extensions (--enable-, eingebaut)
    "opcache":      ["--enable-opcache"],
    "exif":         ["--enable-exif"],
    "intl":         ["--enable-intl"],          # braucht libicu-dev
    "ftp":          ["--enable-ftp"],
    "soap":         ["--enable-soap"],          # braucht libxml2-dev
    "mbstring":     ["--enable-mbstring"],
    "bcmath":       ["--enable-bcmath"],
    "sockets":      ["--enable-sockets"],
    # Extensions mit externer Lib (--with-)
    "openssl":      ["--with-openssl"],
    "iconv":        ["--with-iconv"],
    "gettext":      ["--with-gettext"],
    "tidy":         ["--with-tidy"],
    "curl":         ["--with-curl"],
    "zip":          ["--with-zip"],
    "bz2":          ["--with-bz2"],
    "zlib":         ["--with-zlib"],
    "readline":     ["--with-readline"],
    # Spezielle 1:N-Mappings
    "mysql":        ["--enable-mysqli", "--with-mysqli=mysqlnd", "--with-pdo-mysql=mysqlnd"],
    "sqlite":       ["--with-sqlite3", "--with-pdo-sqlite"],
    "pgsql":        ["--with-pgsql", "--with-pdo-pgsql"],
}


def build_configure_args(
    prefix: Path,
    version: str,
    family: str,
    config: dict,
) -> list[str]:
    """Baut die ./configure Argumentliste aus der Config."""
    vdir = version_dir(prefix, version)
    cli_ini = cli_ini_dir(prefix, family)
    scan_dir = confd_dir(prefix, family)

    base = {
        "prefix": str(vdir),
        "with-config-file-path": str(cli_ini),
        "with-config-file-scan-dir": str(scan_dir),
    }

    extra = config.get("build", {}).get("extra", {})
    for key in ("with-config-file-path", "with-config-file-scan-dir"):
        if key in extra:
            base[key] = extra[key]

    args = [
        f"--prefix={base['prefix']}",
        "--enable-cli",  # Basis: immer CLI bauen
        f"--with-config-file-path={base['with-config-file-path']}",
        f"--with-config-file-scan-dir={base['with-config-file-scan-dir']}",
    ]

    seen: set[str] = set(args)
    variants = config.get("build", {}).get("variants", [])
    for variant in variants:
        if variant in ("default", "cli"):
            continue
        flags = _VARIANT_FLAGS.get(variant, [f"--enable-{variant}"])
        for flag in flags:
            if flag not in seen:
                args.append(flag)
                seen.add(flag)

    skip = {"prefix", "with-config-file-path", "with-config-file-scan-dir"}
    for key, value in extra.items():
        if key in skip:
            continue
        if value is True:
            args.append(f"--{key}")
        elif value is not False and value is not None:
            args.append(f"--{key}={value}")

    return args


def get_jobs(config: dict, override: int | None = None) -> int:
    if override is not None:
        return override
    jobs = config.get("build", {}).get("jobs", "auto")
    if jobs == "auto":
        return os.cpu_count() or 1
    return int(jobs)


def run_configure(src_dir: Path, args: list[str], log_file: IO[str]) -> None:
    _run([str(src_dir / "configure")] + args, cwd=src_dir, log_file=log_file)


def run_make(src_dir: Path, jobs: int, log_file: IO[str]) -> None:
    _run(["make", f"-j{jobs}"], cwd=src_dir, log_file=log_file)


def run_make_install(src_dir: Path, log_file: IO[str]) -> None:
    _run(["make", "install"], cwd=src_dir, log_file=log_file)


def _run(cmd: list[str], cwd: Path, log_file: IO[str]) -> None:
    process = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    for line in process.stdout:
        log_file.write(line)
        log_file.flush()
    process.wait()
    if process.returncode != 0:
        raise subprocess.CalledProcessError(process.returncode, cmd)
