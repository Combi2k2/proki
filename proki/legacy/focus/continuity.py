"""Continuity: whether attention stayed on each item long enough.

Very rapid switching costs attention even inside a small working set
(attention residue, Leroy 2009):

    mean dwell = active time / (switches + 1)
    continuity = 1 − exp(−mean dwell / dwell_scale)

With dwell_scale = 20 s: 5 s per item → 0.22, 20 s → 0.63, 1 min → 0.95.
"""

from __future__ import annotations

import math

from proki.legacy.focus.params import FocusParams
from proki.legacy.focus.window import Window


def mean_dwell_seconds(window: Window) -> float:
    return window.active_seconds / (len(window.switches) + 1)


def continuity(window: Window, params: FocusParams) -> float:
    return 1 - math.exp(-mean_dwell_seconds(window) / params.dwell_scale.total_seconds())
