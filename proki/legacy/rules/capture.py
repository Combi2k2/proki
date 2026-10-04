"""Time spent on something against a threshold (capture questions, core/capture.py)."""

from __future__ import annotations

from datetime import timedelta

from proki.legacy.rules.base import Rule


class TimeOnIt(Rule[timedelta]):
    """Time spent on something, in seconds, against a threshold (core/rule.py)."""

    def measure(self, spent: timedelta) -> float:
        return spent.total_seconds()
