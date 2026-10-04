"""Primitive signals, computed straight from what ActivityWatch recorded.

The one place that reads ActivityWatch (core/collector.py still does too, until the
rest of proki moves onto signals), through services/activitywatch (`aw`: the server's API, and
how the watchers store data). Which primitives exist, and how much history each
keeps, is the config's "inputs" (proki/compiler.py).

    recorded           whether ActivityWatch recorded anything (false: it or proki was off)

    about the app, window or tab in focus
        app            the app                                    window watcher
        title          the window title                           window watcher
        url            the tab's address, while a browser is in focus   browser extension
        sector         what the app or page is ("video_streaming", "chat", ...), from the
                       app and the window title (in a browser, the title names the page)
        depth          how deep it is, from its label's category (`Depth.depth_of`, set by the app)

    about the time (of the cycle, not from ActivityWatch)
        clock          minutes since local midnight (0 to 1440)
        weekday        0 Monday to 6 Sunday, local
        time           minutes since 1970 (never wraps: `time - last_suggested`)

    about input, per minute over each cycle's time frame (aw-watcher-input, an event every ~5 s)
        keys           key presses (the watcher counts down and up: its `presses` / 2)
        mouse_move     mouse movement, in pixels
        mouse_click    mouse clicks
        mouse_scroll   scrolling, in scroll units

ActivityWatch keeps events (timestamp, duration, data) and merges identical
neighbours, so a value holds over each event, with gaps where nothing was recorded
(unknown: None). A primitive's value in a cycle comes from the event holding at the
cycle's moment.

This file drives the cycles (signals/base.py): `Primitive.run(now)` fetches what
ActivityWatch recorded since the last cycle and ticks every stream through the cycles up
to `now`, one every 10 s. The first time, it starts as far back as the longest table
(the config's `backfill`), so every table starts full; then ActivityWatch's events are
let go: a primitive with a table keeps its own history. After a pause (proki not
running, the computer asleep), the cycles in between are run from what was recorded;
`recorded` is false where nothing was.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, ClassVar

from proki.platforms import current as platform
from proki.core.signals.base import Stream
from proki.services import aw
from proki.utils import snake

BROWSER_APPS = platform().BROWSER_APPS


class Primitive(Stream):
    """A stream read from the recording's events, at the cycle's moment. Each kind is
    a class, named after it in snake case (`MouseMove`: "mouse_move"); defining one
    registers it in `kinds` (`kind=False`: a base, not a primitive itself), creating
    one registers it in `Stream.registry`. It keeps a table if asked (`backfill`, `window`)."""

    kinds: ClassVar[dict[str, type[Primitive]]] = {}
    rec: ClassVar[aw.Record | None] = None     # the run's recording

    def __init_subclass__(cls, kind: bool = True, **kwargs: Any):
        super().__init_subclass__(**kwargs)
        if kind:
            Primitive.kinds[snake(cls.__name__)] = cls

    def __init__(self, backfill: bool = False, window: timedelta | None = None):
        if backfill and window is None:
            raise ValueError("a primitive's table needs a window (its events are let go)")
        self.name = snake(type(self).__name__)
        self.backfill = backfill
        self.window = window
        Stream.registry[self.name] = self

    def read(self, rec: aw.Record, t: datetime) -> Any:
        """The value just before `t`, from the recorded events."""
        raise NotImplementedError

    def compute(self) -> Any:
        r = Primitive.rec
        t = Stream.now
        if r is None or t is None:
            return None
        return self.read(r, t)

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.name}>"

    @classmethod
    def run(cls,
        now: datetime,
        rec: aw.Record | None = None,
        host: str = "127.0.0.1",
        port: int = 5600
    ) -> None:
        """Every stream, cycle by cycle, up to `now`: from the last cycle run; the first
        time, from as far back as the longest table (of a stream that isn't persisted:
        a persisted one loads what's older from storage), so every table starts full. A
        stream added since keeps a table: it's filled in first, from its inputs' tables."""
        t = Stream.now
        if t is None or t > now:
            longest = max([timedelta(0), *(s.window for s in Stream.registry.values()
                                           if s.backfill and s.window and not s.persist)])
            start = now - longest
            t = start - timedelta(seconds=start.timestamp() % Stream.cycle.total_seconds())  # on the cycles' grid
        else:
            for stream in list(Stream.registry.values()):
                if stream.backfill and stream._table is None:
                    Stream.fill(stream, t)
        cls.rec = aw.Record.fetch(t, now, aw.ActivityWatchClient(host, port), cls.rec) if rec is None else rec

        while t + Stream.cycle <= now:
            t += Stream.cycle
            Stream.tick(t)
        Stream.now = t  # where the next run continues


class Recorded(Primitive):
    """Whether ActivityWatch recorded anything at the moment: false while it (or proki,
    which runs it) was off, or the computer asleep."""

    def read(self, rec: aw.Record, t: datetime) -> Any:
        return rec[aw.WINDOW].covering(t) is not None or rec[aw.INPUT].covering(t) is not None


class Window(Primitive, kind=False):
    """A field of the window in focus."""

    field: ClassVar[str]

    def read(self, rec: aw.Record, t: datetime) -> Any:
        e = rec[aw.WINDOW].covering(t)
        return e.data.get(self.field) if e else None


class App(Window):
    field = "app"


class Title(Window):
    field = "title"


class Url(Primitive):
    """The tab in focus. The extension reports a tab change right away but only updates a
    tab you stay on now and then, so the current tab is the latest event, however old."""

    def read(self, rec: aw.Record, t: datetime) -> Any:
        app = rec[aw.WINDOW].covering(t)
        tab = rec[aw.WEBTAB].latest(t)

        app = app.data.get("app") if app else None
        url = tab.data.get("url") if tab and app in BROWSER_APPS else None

        return url


class Sector(Primitive):
    """`Sector.classify(app, title)` of the window in focus (the app sets it)."""

    classify: ClassVar[Callable[[str, str], str | None]] = staticmethod(lambda app, title: None)

    def read(self, rec: aw.Record, t: datetime) -> Any:
        app = rec[aw.WINDOW].covering(t)
        return Sector.classify(
            app.data.get("app", ""),
            app.data.get("title", "")
        ) if app else None


class Depth(Primitive):
    """How deep what's in focus is, from `Depth.depth_of(app, title)` (its label's
    category; the app sets it)."""

    depth_of: ClassVar[Callable[[str, str], float | None]] = staticmethod(lambda app, title: None)

    def read(self, rec: aw.Record, t: datetime) -> Any:
        app = rec[aw.WINDOW].covering(t)
        return Depth.depth_of(
            app.data.get("app", ""),
            app.data.get("title", "")
        ) if app else None


class Moment(Primitive, kind=False):
    """From the cycle's time alone, so known even when nothing was recorded."""

    def compute(self) -> Any:
        return None if Stream.now is None else self.at(Stream.now)

    def at(self, t: datetime) -> Any:
        raise NotImplementedError


class Clock(Moment):
    def at(self, t: datetime) -> Any:
        local = t.astimezone()
        return local.hour * 60 + local.minute + local.second / 60


class Weekday(Moment):
    def at(self, t: datetime) -> Any:
        return t.astimezone().weekday()


class Time(Moment):
    def at(self, t: datetime) -> Any:
        return t.timestamp() / 60


class InputRate(Primitive, kind=False):
    """Per minute, over the cycle's time frame (t − cycle, t]: every input event in it,
    each counted for the part of it inside the frame, over the time they cover (the
    newest event may not be written yet). With none in the frame, the event covering the
    moment (input holds a while: `aw.HOLD`)."""

    def count(self, data: dict) -> float:
        raise NotImplementedError

    def read(self, rec: aw.Record, t: datetime) -> Any:
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


class Keys(InputRate):
    def count(self, data: dict) -> float:
        return data.get("presses", 0) / 2


class MouseMove(InputRate):
    def count(self, data: dict) -> float:
        return abs(data.get("deltaX", 0)) + abs(data.get("deltaY", 0))


class MouseClick(InputRate):
    def count(self, data: dict) -> float:
        return data.get("clicks", 0)


class MouseScroll(InputRate):
    def count(self, data: dict) -> float:
        return abs(data.get("scrollX", 0)) + abs(data.get("scrollY", 0))
