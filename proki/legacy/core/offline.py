"""Offline work in a focus session: being away is the work itself.

When the session's current task is marked offline (reading on paper, working by
hand, thinking it through on a walk), leaving the computer doesn't ring the away
alarm or end the session; the time away counts as deep work. Away much longer
than the task needs (its estimate + a grace period) → only the estimate is
credited, and the normal away rules take over from there.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from proki.legacy.core.backlog import Task, away_is_offline_work


@dataclass(frozen=True)
class OfflineStep:
    offline: bool  # working offline, or just back from it: skip the session's focus checks
    away_since: datetime | None  # what the session should see as "away since"
    credit: tuple[datetime, datetime] | None = None  # record this span as offline deep work
    back: bool = False  # the user just came back from the offline work: ask whether the task is done


class OfflineWork:
    def __init__(self) -> None:
        self.since: datetime | None = None  # away on an offline task since then

    def step(self, task: Task | None, away_since: datetime | None, now: datetime) -> OfflineStep:
        if away_since is not None and away_is_offline_work(task, away_since, now):
            if self.since is None:
                self.since = away_since
            return OfflineStep(True, None)
        if self.since is None:
            return OfflineStep(False, away_since)
        start, self.since = self.since, None
        if away_since is not None:
            credited_until = start + timedelta(minutes=task.estimate) if task else start
            return OfflineStep(False, credited_until, (start, credited_until))
        return OfflineStep(True, None, (start, now), back=True)

    def reset(self) -> None:
        self.since = None
