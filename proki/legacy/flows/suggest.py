"""Outside a session, focus is building up → "start a session?" (config.json's suggest rules)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable

from proki.core.rules import Rule
from proki.core.signals import Update
from proki.legacy.flows.base import Flow, FlowContext, config_rules
from proki.legacy.rules.base import Cadence
from proki.legacy.ui.popup import Popup

RULES = ("suggest_not_in_session", "suggest_not_shut_down", "suggest_no_popup", "suggest_not_lately",
         "focus_rising", "focus_high", "deep_now")


class SuggestSessionFlow(Flow):
    name = "suggest a session"

    def __init__(self, popup: Popup, start_session: Callable[[], None]):
        self.popup = popup
        self.start_session = start_session
        self.cadence = Cadence(timedelta(minutes=1))
        self.suggested: Update | None = None  # set last_suggested = time

    def tick(self, ctx: FlowContext) -> None:
        if not self.cadence.due(ctx.now) or not Rule.vote(config_rules(self.name, *RULES)):
            return
        self.suggested = self.suggested or Update("set", {"last_suggested": "time"})
        self.suggested.apply()
        self.popup.ask("You're getting into it. Start a focus session to protect this?",
                       lambda a: self.start_session() if a == "start" else None,
                       [("Start session", "start"), ("Not now", "no")])
