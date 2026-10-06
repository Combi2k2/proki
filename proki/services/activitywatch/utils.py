"""Finding ActivityWatch's programs, and checking that its server is up."""

from __future__ import annotations

import shutil
import requests

from collections.abc import Iterable
from pathlib import Path

UV_TOOLS = Path.home() / ".local" / "bin"  # where `uv tool install` puts programs


def aw_detect(
    directories: list[Path],
    suffix: str,
    modules: list[str],
    optional: Iterable[str] = (),
) -> dict[str, list[str]] | None:
    """The command line of each program in `modules`, from the first of
    `directories` that has all of them (None: ActivityWatch isn't installed). The
    `optional` ones (e.g. aw-watcher-input, installed with uv) are found anywhere, or skipped.

    A program sits right in the directory (macOS app bundle) or in a folder of its own
    name (Windows and Linux: `aw-server/aw-server.exe`). `suffix` is "" or ".exe"."""
    for directory in directories:
        paths = {module: str(path) for module in modules if (path := _program(directory, module, suffix))}

        if len(paths) != len(modules):
            continue

        required_cmds = {module: [path]  for module, path in paths.items()}
        optional_cmds = {module: [found] for module in optional if (found := _anywhere([*directories, UV_TOOLS], module, suffix))}

        return {**required_cmds, **optional_cmds}

    return None


def aw_health(host: str, port: int) -> bool:
    """Whether the server answers."""
    try:
        return requests.get(f"http://{host}:{port}/api/0/info", timeout=1).ok
    except requests.RequestException:
        return False


def _program(directory: Path, module: str, suffix: str) -> Path | None:
    for candidate in (directory / f"{module}{suffix}", directory / module / f"{module}{suffix}"):
        if candidate.is_file():
            return candidate
    return None


def _anywhere(directories: list[Path], module: str, suffix: str) -> str | None:
    for directory in directories:
        if path := _program(directory, module, suffix):
            return str(path)
    return shutil.which(module)
