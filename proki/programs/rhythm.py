"""The deep-work block reminder (the legacy rhythm flow's): at the block's time, "start
a focus session?" (in 10 minutes, or skip today: kept in proki.db for the chain). The
block comes from the rhythm, or a plan stored for that day (legacy/core/rhythm.py,
schedule.py). The evening "anything new?" is the config's (programs/evening.json).
"""

from __future__ import annotations

from datetime import date, datetime, time, timezone

from proki.core.ui import Ui
from proki.legacy.core.rhythm import Rhythm as Days
from proki.legacy.core.schedule import Block, BlockReminders, RhythmParams
from proki.legacy.core.store import Store
from proki.legacy.flows.base import FlowContext
from proki.programs.base import Ritual, program


class Rhythm(Ritual):
    def __init__(
        self,
        store: Store,
        rhythm: Days,
        params: RhythmParams,
        day_starts: time,
    ):
        super().__init__("rhythm")
        self.store = store
        self.rhythm = rhythm
        self.params = params
        self.day_starts = day_starts
        self.reminders: BlockReminders | None = None

    def today(self, now: datetime) -> date:
        return self.rhythm.today(now)

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
        if Ui.busy() or not self.reminders.due(now, in_session):
            return
        self.reminders.shown = True
        Ui.ask(
            f"It's {block.start.astimezone():%H:%M}: your deep-work block.\nStart a focus session?",
            lambda answer: self._on_block_answer(answer, block),
            [("Start session", "start"), ("In 10 min", "later"), ("Skip today", "skip")],
        )

    def _on_block_answer(self, answer: str, block: Block) -> None:
        now = datetime.now(timezone.utc)
        if answer == "start":
            program("session").request()
        elif answer == "later":
            self.reminders.snooze(now)
        else:
            self.store.log_block(block.day, "skipped", now)
            self.reminders.skip()


    def tick(self, ctx: FlowContext) -> None:
        self.check_block(ctx.now, in_session=ctx.in_session)

