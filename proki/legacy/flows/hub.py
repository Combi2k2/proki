"""Hub-and-spoke during a session (core/hub.py): email / chat / calls can wait."""

from __future__ import annotations

from typing import Callable

from proki.legacy.core.hub import HubWatch
from proki.legacy.flows.base import Flow, FlowContext
from proki.legacy.ui.popup import Popup


class HubFlow(Flow):
    name = "hub and spoke"

    def __init__(self, popup: Popup, on_answer: Callable[[str], None],
                 label_name: Callable[[str | None], str] = lambda slug: slug or "this"):
        self.popup = popup
        self.label_name = label_name  # a label's name ("Email")
        self.on_answer = on_answer  # the session's answers: "ok" keeps going, "stop" stops it
        self.watch = HubWatch()

    def poll(self, ctx: FlowContext) -> None:
        if self.watch.step(ctx.now, ctx.current, ctx.kind, ctx.in_session) and not self.popup.isVisible():
            self.popup.ask(f"{self.label_name(ctx.kind)} can wait until the session is over (hub and spoke: "
                           "collaboration outside deep work).", self.on_answer,
                           [("Back to work", "ok"), ("Stop session", "stop")])
