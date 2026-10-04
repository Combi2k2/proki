"""The evening wind-down in the running app: pokes, "10 more minutes", the alarm,
and when the user stopped last night / started this morning (from the minute ledger).

The rules live in core/bedtime.py; this module shows popups and rings the alarm.
"""

from __future__ import annotations

from datetime import datetime, time, timezone
from typing import Callable

from proki.legacy.flows.base import Flow, FlowContext
from proki.legacy.core.bedtime import Action, BedtimeParams, WindDown
from proki.legacy.core.store import Store
from proki.legacy.ui.popup import Popup
from proki.legacy.ui.sound import Alarm


class BedtimeFlow(Flow):
    def __init__(self, store: Store, params: BedtimeParams, day_starts: time, popup: Popup, alarm: Alarm,
                 lock_screen: Callable[[], None], today: Callable[[datetime], object]):
        self.store = store
        self.day_starts = day_starts
        self.popup = popup
        self.alarm = alarm
        self.lock_screen = lock_screen
        self.today = today
        self.wind_down = WindDown(params, day_starts)

    def step(self, now: datetime, active: bool) -> None:
        action = self.wind_down.step(now, active)
        local = now.astimezone()
        if action is Action.POKE:
            options = [("OK, winding down", "ok"), ("Lock screen", "lock")]
            if not self.wind_down.snooze_used:
                options.insert(0, ("10 more minutes", "snooze"))
            self.popup.ask(
                f"It's {local:%H:%M}. Time to wrap up and get ready for bed.\n"
                "Ending the day on time is how you take back control of tomorrow.",
                self._answer, options,
            )
        elif action is Action.ALARM:
            self.alarm.start()
            self.popup.ask(
                f"It's {local:%H:%M}, past your stop time. The alarm keeps ringing while you're still here.\n"
                "Lock the screen and go to sleep.",
                self._answer, [("Lock screen", "lock")],
            )
        elif action is Action.SILENCE:
            self.alarm.stop()

    def _answer(self, response: str) -> None:
        if response == "snooze":
            self.wind_down.snooze(datetime.now(timezone.utc))
        elif response == "lock":
            self.lock_screen()

    # --- last night ------------------------------------------------------------------------

    def last_night(self, now: datetime) -> tuple[datetime | None, datetime | None]:
        """(last active minute of the previous day, first active minute today), from the
        minute ledger, which is filled from ActivityWatch's history even when proki wasn't running."""
        from datetime import timedelta

        from proki.legacy.metrics.day import day_bounds

        _, start, end = day_bounds(now, self.day_starts)
        active = lambda entries: [e.minute for e in entries if e.activity not in (None, "away")]
        yesterday = active(self.store.minutes(start - timedelta(days=1), start))
        today = active(self.store.minutes(start, end))
        return (yesterday[-1] + timedelta(minutes=1) if yesterday else None, today[0] if today else None)

    name = "bedtime"

    def tick(self, ctx: FlowContext) -> None:
        self.step(ctx.now, ctx.active)

