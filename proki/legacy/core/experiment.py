"""The 30-day test (Deep Work, rule 3: quit social media).

Pick one service (a website or app), stop using it for 30 days without telling
anyone, then answer two questions: would the last 30 days have been notably
better with it? Did anyone care that you weren't there? Two noes → quit it for
good. proki counts slips (a hard rule: the user's own commitment) and asks the
questions on day 30.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from proki.core.events import Segment
from proki.legacy.rules.capture import TimeOnIt
from proki.legacy.rules.base import RuleParams

DAYS = 30
SLIP_AFTER = timedelta(seconds=10)  # on it this long in one visit = a slip


@dataclass(frozen=True)
class Experiment:
    id: int
    key: str  # website domain or app
    started: date
    status: str  # 'running', 'quit' (for good), 'ended' (went back)
    slips: int = 0

    def day(self, today: date) -> int:
        """Day 1 is the start day."""
        return (today - self.started).days + 1

    def due(self, today: date) -> bool:
        """The 30 days are over: time for the two questions."""
        return self.status == "running" and self.day(today) > DAYS


def verdict(better_with_it: bool, anyone_cared: bool) -> str:
    """Newport's rule: two noes → quit for good."""
    return "quit" if not better_with_it and not anyone_cared else "back"


class SlipWatch:
    """A slip = on the service for `SLIP_AFTER` in one visit; counted once per visit."""

    def __init__(self, slip_after: timedelta = SLIP_AFTER):
        self.rule = TimeOnIt(RuleParams(threshold=slip_after.total_seconds()))
        self.visit_since: datetime | None = None
        self.counted = False

    def step(self, now: datetime, segment: Segment | None, key: str) -> bool:
        """True once per visit, when this visit becomes a slip."""
        if segment is None or segment.away or segment.key != key:
            self.visit_since, self.counted = None, False
            return False
        if self.visit_since is None:
            self.visit_since = now
        if not self.counted and self.rule.decide(now - self.visit_since):
            self.counted = True
            return True
        return False
