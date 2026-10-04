"""Stability: whether switching stayed within a small working set.

Deep work still switches, but between a few related items (a "working
sphere", González & Mark 2004), measured like an OS working set (Denning 1968):

    effective items = exp(entropy of time per item)      glances barely count
    fit             = min(1, capacity / effective items)
    hit             = a switch back to an item used within the horizon,
                      unless it's a distraction (going back to YouTube is never a hit)
    hit rate        = (hits + 1) / (switches + 1)        no switching → 1
    stability       = fit × hit rate
"""

from __future__ import annotations

import math
from collections import defaultdict

from proki.core.events import Category
from proki.legacy.focus.params import FocusParams
from proki.legacy.focus.window import Switch, Window


def effective_items(window: Window) -> float:
    per_item: dict[str, float] = defaultdict(float)
    for stretch in window.stretches:
        per_item[stretch.item] += stretch.seconds
    total = sum(per_item.values())
    if not total:
        return 0.0
    return math.exp(-sum(s / total * math.log(s / total) for s in per_item.values() if s > 0))


def fit(window: Window, params: FocusParams) -> float:
    items = effective_items(window)
    return min(1.0, params.capacity / items) if items else 1.0


def is_hit(switch: Switch, window: Window) -> bool:
    if switch.to_category is Category.DISTRACTION:
        return False
    return switch.since_last_use is not None and switch.since_last_use <= window.horizon


def hit_rate(window: Window) -> float:
    hits = sum(is_hit(s, window) for s in window.switches)
    return (hits + 1) / (len(window.switches) + 1)


def stability(window: Window, params: FocusParams) -> float:
    return fit(window, params) * hit_rate(window)
