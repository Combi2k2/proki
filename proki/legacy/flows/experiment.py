"""The 30-day test in the running app (rules in core/experiment.py): choose a
service from the tray, slip reminders (with closing the tab), and Newport's two
questions on day 30.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Callable

from proki import platforms
from proki.legacy.flows.base import Flow, FlowContext
from proki.legacy.core.backlog import minutes_text
from proki.legacy.core.events import Segment
from proki.legacy.core.experiment import DAYS, Experiment, SlipWatch, verdict
from proki.legacy.core.store import Store
from proki.legacy.ui.background import Background
from proki.legacy.ui.popup import Popup


class ExperimentFlow(Flow):
    def __init__(self, store: Store, popup: Popup, today: Callable[[datetime], date],
                 candidates: Callable[[], list[tuple[str, int]]]):
        self.store = store
        self.popup = popup
        self.today = today
        self.candidates = candidates  # your distraction sites/apps with minutes (most first)
        self.watches: dict[int, SlipWatch] = {}
        self.asking = False  # the day-30 questions are showing
        self.background = Background()

    def start(self) -> None:
        running = self.store.experiments(("running",))
        if running:
            e = running[0]
            day = e.day(self.today(datetime.now(timezone.utc)))
            slips = f"{e.slips} slip{'s' if e.slips != 1 else ''}"
            self.popup.ask(f"Your 30-day test is running: {e.key}, day {day} of {DAYS}, {slips}. Stop it early?",
                           lambda a: self._stop_early(e) if a == "stop" else None,
                           [("Keep going", "keep"), ("Stop it", "stop")])
            return
        self.background.run(self.candidates, self._offer)  # reading a week of history takes a few seconds

    def _offer(self, candidates: list[tuple[str, int]] | None) -> None:
        options = [(f"{key} ({minutes_text(m)})", key) for key, m in (candidates or [])[:7]]
        if not options:
            self.popup.ask("No distraction sites or apps in the last week to quit.", lambda _: None, [("OK", "ok")])
            return
        self.popup.ask(
            "30-day test: stop using one service for 30 days, without telling anyone. Then decide whether "
            "to quit it for good. Which one? (time in the last week)",
            self._chosen, options + [("Cancel", "cancel")],
        )

    def start_for(self, key: str) -> None:
        self._chosen(key)

    def _chosen(self, key: str) -> None:
        if key == "cancel":
            return
        self.store.start_experiment(key, self.today(datetime.now(timezone.utc)))
        self.popup.ask(f"Day 1 of 30 without {key}. proki will only speak up if you slip.", lambda _: None, [("OK", "ok")])

    def _stop_early(self, e: Experiment) -> None:
        self.store.end_experiment(e.id, "ended", None, None, datetime.now(timezone.utc))

    def step(self, now: datetime, segment: Segment | None) -> None:
        """Every poll: slips on running (or quit-for-good) services."""
        for e in self.store.experiments():
            watch = self.watches.setdefault(e.id, SlipWatch())
            if not watch.step(now, segment, e.key):
                continue
            self.store.add_slip(e.id)
            if self.popup.isVisible():
                continue
            if e.status == "running":
                message = f"Day {e.day(self.today(now))} of your 30-day break from {e.key}."
            else:
                message = f"You quit {e.key} for good."
            self.popup.ask(message, lambda a, s=segment: self._close(s) if a == "close" else None,
                           [("Close it", "close"), ("Just this once", "once")])

    @staticmethod
    def _close(segment: Segment) -> None:
        os_support = platforms.current()
        if segment.url:
            os_support.close_tab(segment.app, segment.url)
        else:
            os_support.close_window(segment.app, segment.title)

    def check_due(self, now: datetime, active: bool) -> None:
        """Every tick: day 30 is over → the two questions."""
        if not active or self.asking or self.popup.isVisible():
            return
        for e in self.store.experiments(("running",)):
            if e.due(self.today(now)):
                self.asking = True
                self.popup.ask(
                    f"Your 30 days without {e.key} are over ({e.slips} slip{'s' if e.slips != 1 else ''}). "
                    "Would the last 30 days have been notably better if you had used it?",
                    lambda a, e=e: self._second(e, a == "yes"), [("Yes", "yes"), ("No", "no")])
                return

    def _second(self, e: Experiment, better: bool) -> None:
        self.popup.ask(f"Did people care that you weren't using {e.key}?",
                       lambda a: self._decide(e, better, a == "yes"), [("Yes", "yes"), ("No", "no")])

    def _decide(self, e: Experiment, better: bool, cared: bool) -> None:
        self.asking = False
        now = datetime.now(timezone.utc)
        if verdict(better, cared) == "quit":
            self.popup.ask(f"Two noes: {e.key} didn't add much. Quit it for good? (proki keeps reminding you on slips)",
                           lambda a: self.store.end_experiment(e.id, "quit" if a == "quit" else "ended", better, cared, now),
                           [("Quit for good", "quit"), ("Go back to it", "back")])
        else:
            self.store.end_experiment(e.id, "ended", better, cared, now)
            self.popup.ask(f"Then go back to {e.key}, knowing what it's worth to you.", lambda _: None, [("OK", "ok")])

    name = "30-day test"

    def tick(self, ctx: FlowContext) -> None:
        self.check_due(ctx.now, ctx.active)

    def poll(self, ctx: FlowContext) -> None:
        self.step(ctx.now, ctx.current)


def experiment_lines(experiments: list[Experiment], today: date) -> list[str]:
    running = [e for e in experiments if e.status == "running"]
    return [f"30-day test: {e.key} · day {min(e.day(today), DAYS)} · {e.slips} slip{'s' if e.slips != 1 else ''}"
            for e in running[:1]]
