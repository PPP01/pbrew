import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"State-Datei '{path}' ist beschädigt und kann nicht gelesen werden: {e}"
        ) from e


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2, default=str)
        os.replace(tmp, path)
    except Exception:
        os.unlink(tmp)
        raise


def get_family_state(state_file: Path) -> dict:
    return _load(state_file)


def set_active_version(
    state_file: Path,
    version: str,
    config: str = "default",
) -> None:
    state = _load(state_file)
    if "active" in state and state["active"] != version:
        state["previous"] = state["active"]
    state["active"] = version
    state["config"] = config
    state.setdefault("installed", {}).setdefault(version, {})["installed_at"] = (
        datetime.now(timezone.utc).isoformat()
    )
    _save(state_file, state)


def set_build_duration(state_file: Path, version: str, seconds: float) -> None:
    state = _load(state_file)
    state.setdefault("installed", {}).setdefault(version, {})
    state["installed"][version]["build_duration_seconds"] = round(seconds)
    _save(state_file, state)


def record_install(
    state_file: Path,
    version: str,
    config: str = "default",
    duration: float | None = None,
) -> None:
    """Setzt active, config, installed_at und optional build_duration in einem Write."""
    state = _load(state_file)
    if "active" in state and state["active"] != version:
        state["previous"] = state["active"]
    state["active"] = version
    state["config"] = config
    entry = state.setdefault("installed", {}).setdefault(version, {})
    entry["installed_at"] = datetime.now(timezone.utc).isoformat()
    if duration is not None:
        entry["build_duration_seconds"] = round(duration)
    _save(state_file, state)


def add_extension(state_file: Path, extension: str) -> None:
    state = _load(state_file)
    extensions: list = state.get("extensions", [])
    if extension not in extensions:
        extensions.append(extension)
    state["extensions"] = extensions
    _save(state_file, state)


def get_global_state(global_state_file: Path) -> dict:
    return _load(global_state_file)


def set_global_default(global_state_file: Path, family: str) -> None:
    state = _load(global_state_file)
    state["default_family"] = family
    _save(global_state_file, state)
