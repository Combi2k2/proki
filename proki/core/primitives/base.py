"""`Primitive`: a stream read at each cycle's moment, and `run`, which drives the cycles.

Every subclass of `Primitive` is a kind (never a class between `Primitive` and a kind);
what kinds of one source share is a mixin beside it, in that source's folder
(aw/base.py, sys/base.py, proki/base.py), and stays in this package.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, ClassVar

from proki.core.signals.stream import Stream
from proki.services import aw
from proki.errors import SignalError
from proki.utils import snake


class Primitive(Stream):
    """A stream read from the recording's events, at the cycle's moment. Each kind is
    a subclass, named after it in snake case (`MouseMove`: "mouse_move"); defining one
    registers it in `kinds`, creating one registers it in `Stream.registry`. What kinds
    share is a mixin beside `Primitive`, not a class under it (`class Keys(InputRate,
    Primitive)`, aw/base.py), so only kinds register. It keeps a table if asked (`backfill`, `window`)."""

    kinds: ClassVar[dict[str, type[Primitive]]] = {}
    rec: ClassVar[aw.Record | None] = None     # the run's recording
    buckets: ClassVar[tuple[str, ...]] = ()    # the bucket types it reads (fetched before the cycles)

    def __init_subclass__(cls, **kwargs: Any):
        super().__init_subclass__(**kwargs)
        Primitive.kinds[snake(cls.__name__)] = cls

    # why a table needs a window: the recording is let go after the first run, so a
    # table is all there is of it (a kind can say otherwise: `Moment`)
    unbounded: ClassVar[str] = "a primitive's table needs a window (what ActivityWatch recorded is let go)"

    def __init__(self, backfill: bool = False, window: timedelta | None = None):
        if backfill and window is None:
            raise SignalError(self.unbounded)
        self.name = snake(type(self).__name__)
        self.backfill = backfill
        self.window = window
        Stream.registry[self.name] = self

    def read(self, rec: aw.Record | None, t: datetime) -> Any:
        """The value just before `t`, from the recorded events (`rec`: None before the
        first fetch)."""
        raise NotImplementedError

    def compute(self) -> Any:
        return None if Stream.now is None else self.read(Primitive.rec, Stream.now)

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
        Stream.live = now
        cls.rec = aw.Record.fetch(t, now, aw.ActivityWatchClient(host, port), cls.rec) if rec is None else rec
        for bucket in sorted({b for s in Stream.registry.values() if isinstance(s, Primitive) for b in s.buckets}):
            cls.rec[bucket]  # fetched now: a failure stops the run before any stream moves on

        while t + Stream.cycle <= now:
            t += Stream.cycle
            Stream.tick(t)
        Stream.now = t  # where the next run continues
