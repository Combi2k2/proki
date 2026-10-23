"""Small helpers that know nothing about proki: names, values, chances, text similarity,
waiting, finding the commands that start installed programs."""

import keyword
import re
import shutil
import time
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from typing import Any

import numpy as np

def same(a: Any, b: Any) -> bool:
    return type(a) is type(b) and a == b  # True and 1 stay apart

def numeric(x: Any) -> bool:
    return isinstance(x, int | float)  # bool too: true counts as 1

def boolean(x: Any) -> bool:
    return isinstance(x, bool)

# names

def snake(name: str) -> str:
    """TsMean as ts_mean: how a class is named in expressions and the config."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def slugify(name: str) -> str:
    """"Video streaming" as "video_streaming"."""
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def ident(name: Any) -> bool:
    """Whether `name` can name something: a name as in Python, in plain letters
    (`focus_5m`), and not one of Python's words (`if`, `not`, ...)."""
    if not isinstance(name, str):   return False
    if not name.isascii():          return False
    if not name.isidentifier():     return False
    if keyword.iskeyword(name):     return False
    return True

# times
def span(said: float | str) -> timedelta:
    """Read minutes or a duration such as 30s, 5min, 1h, or 2d."""
    if isinstance(said, str):
        units = {"s": 1/60, "min": 1, "h": 60, "d": 1440}
        found = re.fullmatch(rf"\s*(\d+(?:\.\d+)?)\s*({'|'.join(units)})\s*", said)
        if not found:
            raise ValueError(f"a time is minutes, or a number and s, min, h or d ({said!r})")
        return timedelta(minutes=float(found[1]) * units[found[2]])
    if boolean(said) or not numeric(said):
        raise TypeError(f"minutes are a number, not {said!r}")
    if said < 0:
        raise ValueError(f"minutes can't be {said:g}")
    return timedelta(minutes=said)

# string format

class Unknown:
    """A value not known, as `fill` writes it: "-", whatever the format asks."""

    def __format__(self, spec: str) -> str:
        return "-"

def fill(text: str, values: dict[str, Any]) -> str:
    """`text` with its {name} / {name:format} filled in from `values`: an unknown value
    (None) as "-", whatever its format. As it is, where it can't."""
    try:
        return text.format_map({name: Unknown() if value is None else value for name, value in values.items()})
    except (KeyError, IndexError, ValueError, TypeError):
        return text

# chances

def sigmoid(z: float) -> float:
    """1 / (1 + e^-z), without overflow."""
    return float(0.5 * (1 + np.tanh(z / 2)))


def bell(z: float) -> float:
    """e^(-z^2 / 2): 1 at 0, 61% at 1 or -1, 14% at 2 or -2."""
    return float(np.exp(-z * z / 2))


def chance(p: float, rng: np.random.Generator | None = None) -> bool:
    """True with probability p (surely at 1, never at 0)."""
    return p >= 1.0 or (p > 0.0 and (rng or np.random.default_rng()).random() < p)

# waiting

def wait_until(condition: Callable[[], bool], timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while not condition() and time.monotonic() < deadline:
        time.sleep(0.2)


def wait_while(condition: Callable[[], bool], timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while condition() and time.monotonic() < deadline:
        time.sleep(0.2)

# commands

def find_commands(
    modules: list[str],
    directories: list[Path],
    suffix: str = "",
) -> dict[str, list[str]] | None:
    """Each module's start command: its installed program (arguments can follow).

        find_commands(["nats-server"], [])    {"nats-server": ["/opt/homebrew/bin/nats-server"]}

    `directories` are tried in order. In each, a module's program is looked for:

        right in it          a macOS app bundle, a bin folder: `<dir>/aw-server`
        in its own folder    Windows and Linux: `<dir>/aw-server/aw-server.exe`
        on the PATH          when the directory doesn't have it

    The first directory where every module is found gives the commands. Without
    directories, the PATH alone. None: they aren't all found. `suffix` is "" or ".exe"."""
    paths_init = {name: path for name in modules if (path := shutil.which(f"{name}{suffix}")) is not None}
    for directory in directories:
        paths = paths_init.copy()
        for name in modules:
            cands = [
                directory / f"{name}{suffix}",
                directory / name / f"{name}{suffix}",
            ]
            if cands[0].is_file():  paths[name] = cands[0]
            if cands[1].is_file():  paths[name] = cands[1]

        if len(paths) == len(modules):
            return {name: [str(paths[name])] for name in modules}

    if len(paths_init) == len(modules):
        return {name: [str(paths_init[name])] for name in modules}

    return None
