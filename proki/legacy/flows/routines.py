"""Routine questions in the running app: after an absence, sometimes ask what it was.

Every absence is stored (asked or not); overnight ones are logged as sleep. The
user types what they did; openjev sorts it into the taxonomy. When openjev is
unsure, the user picks from its best guesses (or turns these follow-ups off: then
openjev's guess is kept, marked unsure). Rules live in core/routines.py.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import Callable

from proki.legacy.flows.base import Flow, FlowContext
from proki.legacy.core.backlog import minutes_text
from proki.legacy.core.routines import ACTIVITY_LABEL, Absence, AbsenceTracker, confident_activity, likely_options, overnight
from proki.core.events import Segment
from proki.legacy.rules.absence import StillThere
from proki.legacy.core.store import Store
from proki.legacy.ui.background import Background
from proki.legacy.ui.popup import Popup

STALE = timedelta(minutes=30)  # a question not asked within this long (popup busy) is dropped
NO_FOLLOW_UPS = "routines_no_follow_ups"  # state key: the user turned off "which one was it?"


class RoutinesFlow(Flow):
    def __init__(self, store: Store, popup: Popup, bedtime: time, day_starts: time, always_ask: bool = False,
                 classify: Callable[[str], list[tuple[str, float]] | None] | None = None,
                 still_there: Callable[[str], float | None] | None = None, still_there_above: float = 0.7,
                 label_name: Callable[[Segment], str | None] = lambda segment: None):
        self.store = store
        self.label_name = label_name  # what a window is ("Video streaming"), for the context
        self.popup = popup
        self.classify = classify  # openjev: typed text → (activity, probability) best first; may be slow
        self.still_there = still_there  # openjev: context → how likely they stayed at the computer; may be slow
        self.skip_rule = StillThere(still_there_above)
        self.left_on: Segment | None = None  # the last thing in focus while active
        self.background = Background()
        self.bedtime = bedtime
        self.day_starts = day_starts
        self.tracker = AbsenceTracker(always_ask=always_ask)
        self.pending: tuple[int, Absence, Segment | None] | None = None  # waiting for the popup to be free
        self.offline_task = False  # the absence ending now was work on an offline task: don't ask

    def offline_work_done(self) -> None:
        """The user is back from working on an offline task (called before `step`)."""
        self.offline_task = True

    def step(self, now: datetime, active: bool, away_since: datetime | None = None,
             in_focus: Segment | None = None) -> None:
        """`in_focus`: the latest segment (what's on screen), to tell openjev what was open."""
        before = self.left_on
        if active and in_focus is not None and not in_focus.away:
            self.left_on = in_focus
        absence = self.tracker.step(now, active, away_since)
        if absence is not None:
            if self.offline_task:
                self.store.add_absence(absence.start, absence.end, "offline_task", "session")
            elif overnight(absence, self.bedtime, self.day_starts):
                self.store.add_absence(absence.start, absence.end, "sleep", "auto")
            elif self.tracker.should_ask(absence):
                absence_id = self.store.add_absence(absence.start, absence.end, None, "unasked")
                if self.still_there and before is not None:
                    context = self._context(absence, before, self.label_name(before))
                    self.background.run(lambda: self.still_there(context),
                                        lambda p: self._checked(absence_id, absence, before, p))
                else:
                    self.pending = (absence_id, absence, before)
            else:
                self.store.add_absence(absence.start, absence.end, None, "unasked")
        if active:
            self.offline_task = False
        if self.pending and not self.popup.isVisible():
            absence_id, absence, left_on = self.pending
            self.pending = None
            if now - absence.end <= STALE:
                self._ask(absence_id, absence, left_on)

    @staticmethod
    def _context(absence: Absence, left_on: Segment, kind_label: str | None = None) -> str:
        """What openjev gets: the app or website (no titles), its kind and category, how long, when."""
        kind = "website" if left_on.url else "app"
        if kind_label:
            kind += f" for {kind_label.lower()}"
        counted = f", which the person counts as {left_on.category.value}" if left_on.category else ""
        return (f"A person's computer got no keyboard or mouse input for "
                f"{int(absence.duration.total_seconds() // 60)} minutes, starting at {absence.start.astimezone():%H:%M}. "
                f"The window in focus the whole time: {left_on.key} (a {kind}{counted}).")

    def _checked(self, absence_id: int, absence: Absence, left_on: Segment | None, probability: float | None) -> None:
        if probability is not None and self.skip_rule.decide(probability):
            self.store.set_absence_activity(absence_id, None, "still_there", confidence=probability)
            return  # openjev is sure they were watching / listening / reading: don't ask
        self.pending = (absence_id, absence, left_on)

    def _ask(self, absence_id: int, absence: Absence, left_on: Segment | None = None) -> None:
        """First: were you away at all? Only then: what did you do?"""
        minutes = minutes_text(int(absence.duration.total_seconds() // 60))
        self.popup.ask(
            f"No input for {minutes} (since {absence.start.astimezone():%H:%M}). Were you away from the computer?",
            lambda a: self._ask_what(absence_id, absence) if a == "away" else self._present(absence_id, absence, left_on),
            [("Yes, I was away", "away"), ("No, I was here", "here")],
        )

    def _present(self, absence_id: int, absence: Absence, left_on: Segment | None) -> None:
        """Not away after all (reading, watching, thinking): that time was at the computer."""
        self.store.set_absence_activity(absence_id, None, "present")
        activity = left_on.category.value if left_on is not None and left_on.category else "unclassified"
        self.store.mark_present(absence.start, absence.end, activity)

    def _ask_what(self, absence_id: int, absence: Absence) -> None:
        self.popup.ask_text(
            f"You were away for {minutes_text(int(absence.duration.total_seconds() // 60))}. What did you do?",
            lambda text: self._typed(absence_id, text),
            placeholder="e.g. lunch with Sam, a walk, laundry",
        )

    def _typed(self, absence_id: int, text: str | None) -> None:
        if text is None:
            self.store.set_absence_activity(absence_id, None, "skipped")
            return
        self.store.set_absence_activity(absence_id, None, "typed", note=text)
        if self.classify:
            self.background.run(lambda: self.classify(text), lambda guesses: self._classified(absence_id, text, guesses))

    def _classified(self, absence_id: int, text: str, guesses: list[tuple[str, float]] | None) -> None:
        if guesses is None:
            return  # openjev unreachable: the typed text is kept
        probability = dict(guesses)
        activity = confident_activity(guesses)
        if activity:
            self.store.set_absence_activity(absence_id, activity, "jev", confidence=probability[activity])
            return
        options = likely_options(guesses)
        best = options[0] if options else None
        # until the user answers (or if they don't want to be asked), keep openjev's guess, marked unsure
        self.store.set_absence_activity(absence_id, best, "jev_unsure", confidence=probability.get(best))
        if self.store.get_state(NO_FOLLOW_UPS) or self.popup.isVisible():
            return
        self.popup.ask(
            f"“{text}”: which one was it?",
            lambda answer: self._picked(absence_id, answer),
            [(ACTIVITY_LABEL[key], key) for key in options]
            + [("Something else", "other"), ("Don't ask me this", "never")],
        )

    def _picked(self, absence_id: int, answer: str) -> None:
        if answer == "never":
            self.store.set_state(NO_FOLLOW_UPS, datetime.now(timezone.utc).isoformat())
        elif answer == "other":
            self.store.set_absence_activity(absence_id, None, "user")  # outside the taxonomy; the text stays
        else:
            self.store.set_absence_activity(absence_id, answer, "user")

    name = "routines"

    def tick(self, ctx: FlowContext) -> None:
        self.step(ctx.now, ctx.active, away_since=ctx.away_since, in_focus=ctx.latest)

