"""The evening wind-down: an anchor for sleep, so the day has a clear end.

Every night (weekends too):
- from wind-down time (22:00): a poke every 5 minutes while the user is active,
  with "10 more minutes" once per night;
- from the hard stop (00:00): the alarm rings while the user is active, until they
  lock the screen, the Mac sleeps, or they're away.
The night ends when the next day starts (04:00). Focus sessions don't shield
from it: a late session is one of the habits to break.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import Enum


@dataclass(frozen=True)
class BedtimeParams:
    enabled: bool = True
    wind_down: time = time(22, 0)
    hard_stop: time = time(0, 0)
    poke_every: timedelta = timedelta(minutes=5)
    snooze: timedelta = timedelta(minutes=10)
    alarm: bool = True  # ring at the hard stop


class Phase(Enum):
    DAY = "day"
    WIND_DOWN = "wind_down"  # pokes
    HARD_STOP = "hard_stop"  # alarm


class Action(Enum):
    NONE = "none"
    POKE = "poke"
    ALARM = "alarm"  # start ringing (keeps ringing while active)
    SILENCE = "silence"  # stop ringing: the user stopped


def phase(now: datetime, p: BedtimeParams, day_starts: time) -> Phase:
    """Where `now` falls: the night runs from wind-down to the start of the next day."""
    t = now.astimezone().time()
    after_midnight = t < day_starts
    if not p.enabled or not (t >= p.wind_down or after_midnight):
        return Phase.DAY
    past_hard_stop = (after_midnight and (t >= p.hard_stop or p.hard_stop >= p.wind_down)) or (
        not after_midnight and p.hard_stop >= p.wind_down and t >= p.hard_stop
    )
    return Phase.HARD_STOP if past_hard_stop else Phase.WIND_DOWN


def night_of(now: datetime, day_starts: time) -> date:
    """The evening a night belongs to (00:30 belongs to the evening before)."""
    local = now.astimezone()
    return local.date() - timedelta(days=1) if local.time() < day_starts else local.date()


class WindDown:
    """Turns (time, is the user active?) into pokes and the alarm, per night."""

    def __init__(self, params: BedtimeParams, day_starts: time):
        self.params = params
        self.day_starts = day_starts
        self.night: date | None = None
        self.last_poke: datetime | None = None
        self.snoozed_until: datetime | None = None
        self.snooze_used = False
        self.ringing = False

    def step(self, now: datetime, active: bool) -> Action:
        current = phase(now, self.params, self.day_starts)
        if current is Phase.DAY:
            return self._silence()
        night = night_of(now, self.day_starts)
        if night != self.night:  # a new night: fresh pokes, fresh snooze
            self.night, self.last_poke, self.snoozed_until, self.snooze_used = night, None, None, False
        if not active:
            return self._silence()
        if current is Phase.HARD_STOP and self.params.alarm:
            if not self.ringing:
                self.ringing = True
                return Action.ALARM
            return Action.NONE
        if self.snoozed_until and now < self.snoozed_until:
            return Action.NONE
        if self.last_poke is None or now - self.last_poke >= self.params.poke_every:
            self.last_poke = now
            return Action.POKE
        return Action.NONE

    def snooze(self, now: datetime) -> bool:
        """"10 more minutes": allowed once per night. Returns whether it was granted."""
        if self.snooze_used:
            return False
        self.snooze_used = True
        self.snoozed_until = now + self.params.snooze
        return True

    def _silence(self) -> Action:
        if self.ringing:
            self.ringing = False
            return Action.SILENCE
        return Action.NONE
