"""`Primitive`, the base of every primitive, and `run`, which drives the cycles.

Each subclass of `Primitive` is one primitive (a "kind"). There's no class in between.
What several kinds from one source share is a mixin next to `Primitive`, in that
source's folder (aw/base.py, sys/base.py, proki/base.py):

    class Keys(InputRate, Primitive): ...      # InputRate: shared by keys and the mouse ones

The mixins aren't exported outside this package.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, ClassVar

from proki.core.signals.stream import Stream
from proki.services import aw
from proki.errors import SignalError
from proki.utils import snake


class Primitive(Stream):
    """A stream read at each cycle's moment, from what was recorded (or the clock).

    Defining a subclass registers its kind in `kinds`, by its name in snake case
    (`MouseMove` → "mouse_move"). The config's "inputs" pick kinds by that name. Making one
    registers it in `Stream.registry`. It keeps a table if the config asks for one
    (`backfill`, how far back: `window`)."""

    kinds: ClassVar[dict[str, type[Primitive]]] = {}  # every kind, by name
    rec: ClassVar[aw.Record | None] = None     # what ActivityWatch recorded, for the current run
    buckets: ClassVar[tuple[str, ...]] = ()    # the ActivityWatch bucket types it reads (fetched before the cycles)

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
        """The value at time `t`, from the recorded events (`rec` is None before the
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
        """Run every stream, cycle by cycle, up to `now`.

        It continues from the last cycle run. The first time, it starts as far back as
        the longest table (persisted tables don't count: they load their past from
        disk), so every table starts full. What ActivityWatch recorded is fetched before
        the first cycle: if that fails, no stream has moved and the next run retries.
        `rec`: a recording to use instead of fetching (tests)."""
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
