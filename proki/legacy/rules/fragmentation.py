from __future__ import annotations

from datetime import datetime, timedelta

from proki.legacy.core.events import Finding, Level, Segment


class Fragmentation:
    """Too many app switches in a short time."""

    name = "fragmentation"

    def __init__(self, window: timedelta = timedelta(minutes=10), max_switches: int = 25):
        self.window = window
        self.max_switches = max_switches

    def check(self, segments: list[Segment], now: datetime) -> Finding | None:
        recent = [s for s in segments if not s.away and s.end >= now - self.window]
        switches = sum(1 for a, b in zip(recent, recent[1:]) if a.app != b.app)
        if switches <= self.max_switches:
            return None
        minutes = int(self.window.total_seconds() // 60)
        return Finding(
            self.name,
            f"You switched apps {switches} times in {minutes} min. "
            "Pick one thing for the next 25 minutes?",
            Level.NOTIFY,
        )


def default_rules() -> list:
    # Nudges outside focus sessions are parked until scheduled deep-work blocks
    # are designed (Deep Work: schedule deep work instead of catching it randomly).
    # Fragmentation stays available but is not active.
    return []
