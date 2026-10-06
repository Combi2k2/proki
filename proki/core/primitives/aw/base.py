"""What the ActivityWatch primitives (this folder) share: the window watcher's event in focus
(`focused`), a field of it (`Window`), input per minute (`InputRate`)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar

from proki.core.signals.stream import Stream
from proki.services import aw


def focused(rec: aw.Record | None, t: datetime) -> aw.Event | None:
    """The window watcher's event at `t`: the app and window in focus."""
    return None if rec is None else rec[aw.WINDOW].covering(t)


class Window:
    """Mixin: a field of the window in focus."""

    buckets = (aw.WINDOW,)
    field: ClassVar[str]

    def read(self, rec: aw.Record | None, t: datetime) -> Any:
        e = focused(rec, t)
        return e.data.get(self.field) if e else None


class InputRate:
    """Mixin: per minute, over the cycle's time frame (t − cycle, t]: every input event in
    it, each counted for the part of it inside the frame, over the time they cover (the
    newest event may not be written yet). With none in the frame, the event covering the
    moment (input holds a while: `aw.HOLD`)."""

    buckets = (aw.INPUT,)

    def count(self, data: dict) -> float:
        raise NotImplementedError

    def read(self, rec: aw.Record | None, t: datetime) -> Any:
        if rec is None:
            return None
        a = t - Stream.cycle
        weighted = known = 0.0
        for e in rec[aw.INPUT].overlapping(a, t):
            length = (e.end - e.start).total_seconds()
            if length <= 0:
                continue
            inside = (min(e.end, t) - max(e.start, a)).total_seconds()
            weighted += self.count(e.data) / (length / 60) * inside  # its rate, for its time inside
            known += inside
        if known:
            return weighted / known
        e = rec[aw.INPUT].covering(t)
        if e is None or e.end <= e.start:
            return None
        return self.count(e.data) / ((e.end - e.start).total_seconds() / 60)
