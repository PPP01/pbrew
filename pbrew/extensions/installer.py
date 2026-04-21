import subprocess
import tarfile
from pathlib import Path
from typing import IO


def extract_tarball(tarball: Path, dest_dir: Path) -> Path:
    """Entpackt Tarball nach dest_dir, gibt das Source-Verzeichnis zurück."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tarball) as tar:
        # PECL-Tarballs enthalten package.xml vor dem Quellverzeichnis –
        # daher das erste Directory-Member suchen, nicht einfach getnames()[0].
        top_level = next(
            (m.name.rstrip("/") for m in tar.getmembers()
             if m.isdir() and "/" not in m.name.rstrip("/")),
            tar.getnames()[0].split("/")[0],
        )
        tar.extractall(dest_dir, filter="data")
    return dest_dir / top_level


def install_extension(
    prefix: Path,
    version: str,
    ext_name: str,
    src_dir: Path,
    jobs: int,
    log_file: IO[str],
) -> None:
    """Baut eine PHP-Extension via phpize → configure → make → make install."""
    phpize = prefix / "versions" / version / "bin" / "phpize"
    php_config = prefix / "versions" / version / "bin" / "php-config"

    _run([str(phpize)], cwd=src_dir, log_file=log_file)
    _run(
        [str(src_dir / "configure"), f"--with-php-config={php_config}"],
        cwd=src_dir,
        log_file=log_file,
    )
    _run(["make", f"-j{jobs}"], cwd=src_dir, log_file=log_file)
    _run(["make", "install"], cwd=src_dir, log_file=log_file)


def write_ext_ini(
    prefix: Path,
    family: str,
    ext_name: str,
    is_zend: bool = False,
    debug: bool = False,
) -> Path:
    """Schreibt Extension-INI in den scan-dir.

    debug=True schreibt in conf.d/<family>d/ (nur von phpd geladen),
    sonst in conf.d/<family>/ (von php und phpd geladen).
    Bestehende INIs werden nie überschrieben.
    """
    from pbrew.core.paths import confd_debug_dir, confd_dir
    ini_dir = confd_debug_dir(prefix, family) if debug else confd_dir(prefix, family)
    ini_dir.mkdir(parents=True, exist_ok=True)
    ini = ini_dir / f"{ext_name}.ini"
    if ini.exists():
        return ini
    directive = "zend_extension" if is_zend else "extension"
    ini.write_text(f"{directive}={ext_name}.so\n")
    return ini


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
