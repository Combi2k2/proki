"""Work like Roosevelt (Deep Work, rule 1): a short, intense burst on one task with a
deadline tighter than feels comfortable, counting down.

The deadline is the task's own estimate. At the deadline: done, 5 more minutes,
or stop.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class SprintParams:
    extension: int = 5  # "5 more minutes"


@dataclass
class Sprint:
    title: str
    task_id: int | None
    ends_at: datetime
    asked: bool = False  # "time's up" is showing / was shown for this deadline

    def left(self, now: datetime) -> timedelta:
        return max(self.ends_at - now, timedelta(0))

    def due(self, now: datetime) -> bool:
        return now >= self.ends_at and not self.asked

    def extend(self, now: datetime, minutes: int) -> None:
        self.ends_at, self.asked = now + timedelta(minutes=minutes), False
