"""The morning start: from picking up the laptop to the first deep-work session.

1. The first activity of the day → show today's work and ask how long the morning
   routine takes (or "start now" / "heading out today").
2. The routine gets that time plus a buffer: clamp(20% of it, 5, 20) minutes.
3. Back at the computer early (after having stepped away) → "Finished your routine?"
   - finished → "start working?": yes → session; no → wait for the deadline
   - "not yet" → back to the routine, the deadline 1 minute later
4. Deadline reached without a session → the alarm rings until a session starts
   (or the user is heading out).
Starting a session at any point ends the morning.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

LEFT_AFTER = timedelta(minutes=3)  # away at least this long during the routine = actually went to do it
EXTENSION = timedelta(minutes=1)  # "not yet": back to the routine, a little more time


def buffer_for(routine: timedelta) -> timedelta:
    """clamp(20% of the routine, 5, 20) minutes."""
    minutes = min(max(routine.total_seconds() / 60 * 0.2, 5), 20)
    return timedelta(minutes=minutes)


class State(Enum):
    WAITING = "waiting"  # no activity yet today
    ASKED = "asked"  # the morning question is showing
    ROUTINE = "routine"  # doing the morning routine; coming back early is checked
    CHECKING = "checking"  # "finished your routine?" is showing
    UNTIL_DEADLINE = "until_deadline"  # finished but not working yet: just wait for the deadline
    RINGING = "ringing"  # deadline passed without a session
    DONE = "done"  # a session started, heading out, or not a morning


class Action(Enum):
    NONE = "none"
    GREET = "greet"  # first activity: show today's work, ask about the routine
    CHECK = "check"  # back early: finished, or not yet?
    ALARM = "alarm"  # deadline passed without a session
    SILENCE = "silence"  # a session started: stop the alarm


@dataclass
class MorningState:
    state: State = State.WAITING
    deadline: datetime | None = None
    away_since: datetime | None = None
    left: bool = False  # stepped away long enough during the routine

    def step(self, now: datetime, active: bool, in_session: bool = False) -> Action:
        if self.state is State.DONE:
            return Action.NONE
        if in_session and self.state is not State.WAITING:
            was_ringing = self.state is State.RINGING
            self.state = State.DONE
            return Action.SILENCE if was_ringing else Action.NONE
        if self.state is State.WAITING:
            if active:
                self.state = State.ASKED
                return Action.GREET
            return Action.NONE
        if self.state in (State.ROUTINE, State.UNTIL_DEADLINE) and now >= self.deadline:
            self.state = State.RINGING
            return Action.ALARM
        if self.state is State.ROUTINE:
            if not active:
                self.away_since = self.away_since or now
                if now - self.away_since >= LEFT_AFTER:
                    self.left = True
            else:
                self.away_since = None
                if self.left:
                    self.state = State.CHECKING
                    return Action.CHECK
        return Action.NONE

    def start_routine(self, now: datetime, minutes: int) -> datetime:
        routine = timedelta(minutes=minutes)
        self.state = State.ROUTINE
        self.deadline = now + routine + buffer_for(routine)
        self.away_since, self.left = None, False
        return self.deadline

    def not_yet(self) -> None:
        """Back to the routine, with the deadline a little later."""
        self.deadline += EXTENSION
        self.state, self.left, self.away_since = State.ROUTINE, False, None

    def finished_not_working(self) -> None:
        """Routine done, but not ready to work: wait for the deadline (then the alarm)."""
        self.state = State.UNTIL_DEADLINE

    def finish(self) -> None:
        """Start now, heading out, or a session started: nothing more this morning."""
        self.state = State.DONE
