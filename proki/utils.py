"""Small helpers that know nothing about proki: names, values, chances, text similarity,
waiting."""

from __future__ import annotations

import math
import re
import time
from collections import Counter
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import numpy as np


# names

def snake(name: str) -> str:
    """TsMean → ts_mean (how a class is named in expressions and the config)."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def slugify(name: str) -> str:
    """"Video streaming" → "video_streaming"."""
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


# values

def fill(text: str, values: dict[str, Any]) -> str:
    """`text` with its {name} / {name:format} filled in from `values` (as it is, where it can't)."""
    try:
        return text.format_map(values)
    except (KeyError, IndexError, ValueError, TypeError):
        return text


def same(a: Any, b: Any) -> bool:
    return type(a) is type(b) and a == b  # True and 1 stay apart


def minutes(m: float) -> timedelta:
    """`m` minutes; a number, not negative (true / false aren't numbers here)."""
    if isinstance(m, bool) or not isinstance(m, int | float):
        raise TypeError(f"minutes are a number, not {m!r}")
    if m < 0:
        raise ValueError(f"minutes can't be {m:g}")
    return timedelta(minutes=m)


def is_number(x: Any) -> bool:
    return isinstance(x, int | float)  # bool too: true counts as 1


def kind(x: Any) -> str:
    """What sort of value: "bool", "number", "str", "NoneType", ... (1 and 1.0 alike)."""
    return "bool" if isinstance(x, bool) else "number" if isinstance(x, int | float) else type(x).__name__


# chances

def sigmoid(z: float) -> float:
    """1 / (1 + e^−z), without overflow."""
    return float(0.5 * (1 + np.tanh(z / 2)))


def bell(z: float) -> float:
    """e^(−z²/2): 1 at 0, 61% at ±1, 14% at ±2."""
    return float(np.exp(-z * z / 2))


def chance(p: float, rng: np.random.Generator | None = None) -> bool:
    """True with probability p (surely at 1, never at 0)."""
    return p >= 1.0 or (p > 0.0 and (rng or np.random.default_rng()).random() < p)


# text similarity

def grams(text: str, n: int = 3) -> list[str]:
    """Character n-grams of each word (with its edges): "Gmail" → " gm", "gma", ..., "il "."""
    out = []
    for word in re.findall(r"\w+", text.lower()):
        word = f" {word} "
        out += [word[i:i + n] for i in range(len(word) - n + 1)]
    return out


def vector(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    """The tokens' TF-IDF vector, of length 1 (empty: no tokens)."""
    counts = Counter(tokens)
    v = {w: n * idf.get(w, 1.0) for w, n in counts.items()}
    norm = math.sqrt(sum(x * x for x in v.values()))
    return {w: x / norm for w, x in v.items()} if norm else {}


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    """The cosine similarity of two vectors of length 1."""
    if len(a) > len(b):
        a, b = b, a
    return sum(x * b.get(w, 0.0) for w, x in a.items())


# waiting

def wait_until(condition: Callable[[], bool], timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while not condition() and time.monotonic() < deadline:
        time.sleep(0.2)


def wait_while(condition: Callable[[], bool], timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while condition() and time.monotonic() < deadline:
        time.sleep(0.2)
