"""The shallow-work budget in the running app (rules/budget.py, core/budget.py): sometimes
mention it on workdays before the shutdown, more likely the further over the limit."""

from __future__ import annotations

from datetime import date, datetime
from typing import Callable

from proki.legacy.core.budget import BudgetParams, ShallowBudget, ShallowShare
from proki.legacy.core.shutdown import ShutdownParams, workday
from proki.legacy.flows.base import Flow, FlowContext
from proki.legacy.ui.popup import Popup


class BudgetFlow(Flow):
    name = "shallow budget"

    def __init__(self, popup: Popup, params: BudgetParams, shutdown: ShutdownParams,
                 today: Callable[[datetime], date], shallow_today: Callable[[datetime], ShallowShare],
                 start_session: Callable[[], None]):
        self.popup = popup
        self.params = params
        self.shutdown = shutdown  # which days are workdays
        self.today = today
        self.shallow_today = shallow_today  # today's shallow share (from the scoreboard)
        self.start_session = start_session
        self.budget = ShallowBudget(params)

    def tick(self, ctx: FlowContext) -> None:
        if (ctx.in_session or self.popup.isVisible() or not workday(self.today(ctx.now), self.shutdown)
                or ctx.state.get("shutdown_done")):
            return
        today = self.shallow_today(ctx.now)
        if not self.budget.should_prompt(ctx.now, today):
            return
        self.popup.ask(
            f"Shallow work is at {today.share:.0%} of your time at the computer today (your limit: "
            f"{self.params.limit:.0%}). Batch the rest for later and get back to deep work?",
            lambda a: self.start_session() if a == "session" else None,
            [("Start a focus session", "session"), ("Not now", "no")],
        )
