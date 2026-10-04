"""The daily routine's prompts: the deep-work block reminder (morning) and the
evening "anything new to take care of?" (once per day, at planning time).

The logic lives in core/ (schedule, rhythm); tasks are handled by tasks_controller.
"""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Callable

from proki.legacy.flows.base import Flow, FlowContext
from proki.legacy.core.rhythm import Rhythm
from proki.legacy.core.schedule import Block, BlockReminders, RhythmParams
from proki.legacy.core.store import Store
from proki.legacy.ui.popup import Popup


class RhythmFlow(Flow):
    def __init__(
        self,
        store: Store,
        rhythm: Rhythm,
        params: RhythmParams,
        day_starts: time,
        popup: Popup,
        request_session: Callable[[], None],
        ask_anything_new: Callable[[], None],
    ):
        self.store = store
        self.rhythm = rhythm
        self.params = params
        self.day_starts = day_starts
        self.popup = popup
        self.request_session = request_session
        self.ask_anything_new = ask_anything_new
        self.reminders: BlockReminders | None = None

    def today(self, now: datetime) -> date:
        return self.rhythm.today(now)

    # --- evening: anything new? ---------------------------------------------------------

    def check_evening(self, now: datetime) -> None:
        """Once per day, from planning time until the day ends, ask about new tasks."""
        local = now.astimezone().time()
        if not (local >= self.params.planning_time or local < self.day_starts) or self.popup.isVisible():
            return
        today = self.today(now).isoformat()
        if self.store.get_state("evening_asked") == today:
            return
        self.store.set_state("evening_asked", today)
        self.ask_anything_new()

    # --- the deep-work block -------------------------------------------------------------

    def todays_block(self, now: datetime) -> Block | None:
        return self.rhythm.block(self.today(now), now.astimezone().tzinfo)

    def check_block(self, now: datetime, in_session: bool) -> None:
        """At block time, ask to start a session (if nothing else is on screen)."""
        block = self.todays_block(now)
        if block is None:
            self.reminders = None
            return
        if self.reminders is None or self.reminders.block != block:
            self.reminders = BlockReminders(block)
            if "skipped" in self.store.block_actions(block.day):
                self.reminders.skip()
        if self.popup.isVisible() or not self.reminders.due(now, in_session):
            return
        self.reminders.shown = True
        self.popup.ask(
            f"It's {block.start.astimezone():%H:%M}: your deep-work block.\nStart a focus session?",
            lambda answer: self._on_block_answer(answer, block),
            [("Start session", "start"), ("In 10 min", "later"), ("Skip today", "skip")],
        )

    def _on_block_answer(self, answer: str, block: Block) -> None:
        now = datetime.now(timezone.utc)
        if answer == "start":
            self.request_session()
        elif answer == "later":
            self.reminders.snooze(now)
        else:
            self.store.log_block(block.day, "skipped", now)
            self.reminders.skip()

    name = "rhythm"

    def tick(self, ctx: FlowContext) -> None:
        self.check_block(ctx.now, in_session=ctx.in_session)
        if not ctx.state.get("shutdown_done"):  # the shutdown already asked what's on your mind
            self.check_evening(ctx.now)

