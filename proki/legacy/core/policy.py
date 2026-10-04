"""Decides whether a finding is allowed to interrupt the user right now."""

from __future__ import annotations

from datetime import datetime, timedelta

from proki.core.events import Finding, Level


class NudgePolicy:
    def __init__(self, min_between: timedelta):
        self.min_between = min_between
        self._last_nudge: datetime | None = None
        self._snoozed_until: datetime | None = None

    def allow(self, finding: Finding, now: datetime, away: bool = False) -> bool:
        if finding.level is Level.QUIET:
            return True  # a tray badge never interrupts
        if away:
            return False  # nobody would see it, and it would pile up
        if self._snoozed_until and now < self._snoozed_until:
            return False
        return self._last_nudge is None or now - self._last_nudge >= self.min_between

    def record(self, finding: Finding, now: datetime) -> None:
        if finding.level is not Level.QUIET:
            self._last_nudge = now

    def snooze(self, until: datetime) -> None:
        self._snoozed_until = until
