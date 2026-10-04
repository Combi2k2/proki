"""Low focus in a session: the 2-min focus score below the threshold, and not rising."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from proki.legacy.rules.base import Rule, RuleParams


@dataclass(frozen=True)
class FocusReading:
    intensity: float | None  # the 2-min focus score
    now: datetime


class LowAndNotRising(Rule[FocusReading]):
    """Low focus in a session (core/rule.py): the 2-min score below the threshold
    (hard: exactly the user's line), active only while the score isn't rising.

    Right after switching back from a distraction, the 2-minute window still
    holds the distraction, so the score stays low for a while although the user
    is back on track. Its rising trend shows that: compared with `lookback` ago,
    up by more than `rise` → recovering, not low (no poke, the alarm stops).
    """

    def __init__(self, threshold: float = 0.35, rise: float = 0.05, lookback: timedelta = timedelta(seconds=30)):
        super().__init__(RuleParams(threshold=threshold, direction=-1))
        self.rise = rise
        self.lookback = lookback
        self.history: list[tuple[datetime, float]] = []  # recent (time, score)

    def measure(self, reading: FocusReading) -> float | None:
        return reading.intensity

    def active(self, reading: FocusReading) -> bool:
        return reading.intensity is None or not self.rising(reading.intensity, reading.now)

    def rising(self, intensity: float, now: datetime) -> bool:
        earlier = [score for t, score in self.history if now - t >= self.lookback]
        return bool(earlier) and intensity - earlier[-1] > self.rise

    def __call__(self, intensity: float | None, now: datetime) -> bool:
        """Is focus low now? (Also records the score for the trend.)"""
        self.history = [(t, s) for t, s in self.history if now - t <= 3 * self.lookback]
        low = self.decide(FocusReading(intensity, now))
        if intensity is not None:
            self.history.append((now, intensity))
        return low
