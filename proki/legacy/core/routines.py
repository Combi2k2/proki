"""Learning the user's routines from their absences ("what was that?").

An absence runs from the last activity to the next one: away from the keyboard,
or the laptop asleep / proki not running. After it, proki asks what it was, at
random, more often for longer absences; the user types it and openjev sorts it
into the taxonomy (asking the user only when unsure). Overnight absences are
logged as sleep without asking. The answers (and the unasked absences) build up typical times
for meals, sport, etc., which later routine reminders use.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from proki.legacy.rules.absence import AskRule
from datetime import datetime, time, timedelta

# two levels: category → activities (key, label)
TAXONOMY: dict[str, tuple[str, list[tuple[str, str]]]] = {
    "body_care": ("Body care", [("toilet", "Toilet"), ("shower", "Shower"), ("grooming", "Getting ready")]),
    "food": ("Food", [("coffee_snack", "Coffee / snack"), ("cooking", "Cooking"), ("meal", "A meal")]),
    "movement": ("Movement", [("workout", "Sport / workout"), ("walk", "A walk"), ("stretching", "Stretching")]),
    "rest": ("Rest", [("nap", "A nap"), ("sleep", "Sleep"), ("relax", "Relaxing")]),
    "chores": ("Chores", [("cleaning", "Cleaning"), ("laundry", "Laundry"), ("errands", "Shopping / errands")]),
    "people": ("People", [("family_friends", "Family / friends"), ("phone_call", "Phone call"), ("meeting", "Meeting in person")]),
    "out": ("Out", [("commute", "Commute"), ("travel", "Travel"), ("appointment", "Appointment")]),
    "offline_work": ("Offline work", [("reading_paper", "Reading on paper"), ("handwriting", "Working by hand"), ("thinking", "Thinking it through")]),
    "leisure": ("Leisure", [("tv", "TV / video"), ("games", "Games"), ("hobby", "A hobby")]),
}
ACTIVITY_CATEGORY = {key: cat for cat, (_, items) in TAXONOMY.items() for key, _ in items}
ACTIVITY_LABEL = {key: label for _, (_, items) in TAXONOMY.items() for key, label in items}

MIN_ABSENCE = timedelta(minutes=5)


@dataclass(frozen=True)
class Absence:
    start: datetime  # last activity before it
    end: datetime  # first activity after it

    @property
    def duration(self) -> timedelta:
        return self.end - self.start


def ask_probability(duration: timedelta) -> float:
    """How likely proki asks about an absence of this length."""
    return AskRule().chance(Absence(datetime.min, datetime.min + duration))


CONFIDENT = 0.7  # openjev at least this sure of an activity → take it without asking
UNSURE_OPTIONS = 3  # openjev unsure → offer its best guesses, this many


def confident_activity(guesses: list[tuple[str, float]] | None) -> str | None:
    """openjev's activity for a typed answer when it's sure enough (and it's in the taxonomy)."""
    if not guesses:
        return None
    key, probability = guesses[0]
    return key if key != "other" and probability >= CONFIDENT else None


def likely_options(guesses: list[tuple[str, float]] | None) -> list[str]:
    """openjev's best guesses to offer when it's unsure (taxonomy activities only)."""
    return [key for key, p in (guesses or []) if key != "other" and p > 0][:UNSURE_OPTIONS]


def overnight(absence: Absence, bedtime: time, day_starts: time) -> bool:
    """Whether the absence covers part of the night (bedtime until the day starts): that's sleep."""
    t = absence.start.astimezone()
    while t < absence.end:
        clock = t.time()
        if clock >= bedtime or clock < day_starts:
            return True
        t += timedelta(minutes=15)
    return False


class AbsenceTracker:
    """Turns "is the user active now?" (checked every few seconds) into finished absences."""

    def __init__(self, rng: random.Random | None = None, always_ask: bool = False):
        self.rule = AskRule(always_ask, rng)
        self.last_active: datetime | None = None
        self.returned_at: datetime | None = None  # end of the last absence

    def step(self, now: datetime, active: bool, away_since: datetime | None = None) -> Absence | None:
        """Call regularly; returns an absence when the user comes back from one.

        `away_since`: when ActivityWatch says the user left (their last input). It
        marks "away" only after a few idle minutes, so this is earlier than the
        moment proki first sees them as away.
        """
        if not active:
            if away_since is not None and self.last_active is not None:
                if self.returned_at is not None:
                    # ActivityWatch can still report the previous away period for a moment
                    # after the user is back: never reach back into an absence already reported
                    away_since = max(away_since, self.returned_at)
                self.last_active = min(self.last_active, away_since)
            return None
        previous, self.last_active = self.last_active, now
        if previous is not None and now - previous >= MIN_ABSENCE:
            self.returned_at = now
            return Absence(previous, now)
        return None

    def should_ask(self, absence: Absence) -> bool:
        return self.rule.decide(absence)
