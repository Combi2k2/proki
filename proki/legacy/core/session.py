"""Focus sessions: started and stopped by the user, never a fixed length.

Phases, by time since the start (the numbers are never shown to the user):

    building (0–25 min)  focus low for 1 min → poke, again every minute until focus is back
    free    (25–50 min)  no reminders to stop; focus low → ask "is this session done?",
                         and if the user keeps going, poke every minute while focus stays low
    wrap-up (50 min+)    "time to wrap up", repeated every 2 minutes until the user stops

In any phase: away for 5 minutes → alarm until the user is back; away for 10 minutes →
the session ends by itself, as of when the user left.

`FocusSession.step` turns (time, focus low?, away since) into one action; the app
shows it. Whether focus is "low" is decided outside (see `LowFocus`), so the rule
can later become personal (e.g. a quantile of the user's own history).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Protocol


class Action(Enum):
    NONE = "none"
    POKE = "poke"  # focus slipped: come back
    ASK_DONE = "ask_done"  # past the build-up phase and focus dropped: finished?
    WRAP_UP = "wrap_up"  # past the healthy maximum: time to stop
    ALARM = "alarm"  # away too long during a session
    END = "end"  # away so long that the session is over (ends as of when the user left)


@dataclass(frozen=True)
class SessionParams:
    build_up: timedelta = timedelta(minutes=25)  # soft target; encouraged, never shown
    wrap_up: timedelta = timedelta(minutes=50)  # healthy maximum for one stretch
    low_focus_for: timedelta = timedelta(minutes=1)  # low this long before the first poke
    poke_every: timedelta = timedelta(minutes=1)
    wrap_up_every: timedelta = timedelta(minutes=2)
    away_alarm_after: timedelta = timedelta(minutes=5)
    alarm_every: timedelta = timedelta(minutes=1)
    away_end_after: timedelta = timedelta(minutes=10)


class LowFocus(Protocol):
    def __call__(self, intensity: float | None, now: datetime) -> bool: ...


@dataclass(frozen=True)
class BelowThreshold:
    """Low focus = short-window intensity below a fixed number. A first version:
    to be replaced by a personal quantile as the user's focus improves."""

    threshold: float = 0.35

    def __call__(self, intensity: float | None, now: datetime | None = None) -> bool:
        return intensity is not None and intensity < self.threshold


class FocusSession:
    def __init__(self, started_at: datetime, params: SessionParams):
        self.started_at = started_at
        self.params = params
        self.low_since: datetime | None = None
        self.last_poke: datetime | None = None
        self.asked_done = False  # already asked during this dip in focus
        self.last_wrap_up: datetime | None = None
        self.last_alarm: datetime | None = None
        self.counts = {action: 0 for action in Action if action is not Action.NONE}

    def elapsed(self, now: datetime) -> timedelta:
        return now - self.started_at

    def step(self, now: datetime, low_focus: bool, away_since: datetime | None) -> Action:
        action = self._decide(now, low_focus, away_since)
        if action is not Action.NONE:
            self.counts[action] += 1
        return action

    def _decide(self, now: datetime, low_focus: bool, away_since: datetime | None) -> Action:
        p = self.params
        if away_since is not None:
            self.low_since = None  # focus is judged again once the user is back
            if now - away_since >= p.away_end_after:
                return Action.END
            if now - away_since >= p.away_alarm_after and _due(self.last_alarm, now, p.alarm_every):
                self.last_alarm = now
                return Action.ALARM
            return Action.NONE
        self.last_alarm = None

        if self.elapsed(now) >= p.wrap_up:
            if _due(self.last_wrap_up, now, p.wrap_up_every):
                self.last_wrap_up = now
                return Action.WRAP_UP
            return Action.NONE

        if not low_focus:
            self.low_since = self.last_poke = None
            self.asked_done = False
            return Action.NONE
        self.low_since = self.low_since or now
        if now - self.low_since < p.low_focus_for:
            return Action.NONE
        if self.elapsed(now) >= p.build_up and not self.asked_done:
            self.asked_done = True
            self.last_poke = now  # if they keep going, the next poke comes a minute later
            return Action.ASK_DONE
        if _due(self.last_poke, now, p.poke_every):
            self.last_poke = now
            return Action.POKE
        return Action.NONE


def _due(last: datetime | None, now: datetime, every: timedelta) -> bool:
    return last is None or now - last >= every
