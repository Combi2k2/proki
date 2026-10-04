"""Depth: how deep the work in a window was.

    depth = Σ weight(category) × mode × time / Σ time      (neutral time left out of both sums)

Deep counts 1, shallow partly, distraction and unclassified 0 (see params.py).
Mode: creating (lots of keys and clicks) counts fully, consuming (reading,
watching) a bit less: creating > consuming good content > social media.
Neutral items (music player, settings, file manager) don't count for or
against you. None when the window has only neutral time.
"""

from __future__ import annotations

from proki.legacy.core.events import Category
from proki.legacy.focus.params import FocusParams
from proki.legacy.focus.window import Window
from proki.legacy.rules.base import RuleParams, chance_at


def depth(window: Window, params: FocusParams) -> float | None:
    weighted = counted = 0.0
    for stretch in window.stretches:
        if stretch.category is Category.NEUTRAL:
            continue
        weighted += params.weights.get(stretch.category, 0.0) * mode(stretch.inputs, params) * stretch.seconds
        counted += stretch.seconds
    return weighted / counted if counted else None


def mode(inputs: float | None, params: FocusParams) -> float:
    """1 when creating, `consuming` when consuming, soft in between; 1 without input data."""
    if inputs is None:
        return 1.0
    creating = chance_at(inputs, RuleParams(threshold=params.creating_at, softness=params.creating_softness))
    return params.consuming + (1 - params.consuming) * creating
