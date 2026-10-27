"""`Primitive`, the base of every primitive, and `run`, which drives the cycles.

Each subclass of `Primitive` is one primitive (a "kind"), with no class in between. What
kinds from one source share is a mixin beside `Primitive`, kept within this package:

    class Keys(InputRate, Primitive): ...      # InputRate: shared by keys and the mouse ones
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, ClassVar

from proki.core.signals.stream import Stream, retained
from proki.errors import SignalError
from proki.utils import snake


class Primitive(Stream):
    """A stream read at each cycle's moment, from what was recorded (or the clock).

    Defining a subclass registers its kind in `kinds`, by its `name`, else its class's in
    snake case (`MouseMove` → "mouse_move"): the config's "inputs" pick kinds by it. Making
    one registers it in `Stream.registry`. It keeps a table if the config asks for one
    (`backfill`, how far back: `window`). Each says what it is (`desc`), as you see it."""

    kinds     : ClassVar[dict[str, type[Primitive]]]                 = {}   # every kind, by name
    sources   : ClassVar[list[Callable[[datetime, datetime], None]]] = []   # fetch(start, end): what each source recorded, before the cycles
    unbounded : ClassVar[str] = "a primitive's table needs a window (what was recorded is let go)"
    # a table needs a window: what was recorded is let go after the first run, so a table is
    # all there is of it (a kind can say otherwise)

    def __init_subclass__(cls, **kwargs: Any):
        super().__init_subclass__(**kwargs)
        cls.name = cls.__dict__.get("name") or snake(cls.__name__)
        Primitive.kinds[cls.name] = cls

    def __init__(self, backfill: bool = False, window: timedelta | None = None):
        if backfill and window is None:  raise SignalError(self.unbounded)
        self.name     = type(self).name
        self.backfill = backfill
        self.window   = window
        Stream.registry[self.name] = self

    def read(self, t: datetime) -> Any:
        """The value at time `t` (from what its source recorded, or the clock)."""
        raise NotImplementedError

    def compute(self) -> Any:
        return None if Stream.now is None else self.read(Stream.now)

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.name}>"

    @classmethod
    def run(cls, now: datetime) -> None:
        """Run every stream, cycle by cycle, up to `now`: nothing until a cycle is due.

        It continues from the last cycle run. The first time, it starts as far back as the
        longest table (a persisted one doesn't count: it loads its past from disk), so every
        table starts full. Each source fetches what it recorded before the first cycle
        (`sources`): if that fails, no stream has moved, and the next run retries. Of the
        cycles before the present, only the streams that keep their past are run."""
        t = Stream.now
        if t is not None and t <= now < t + Stream.cycle:
            return
        if t is None or t > now:
            longest = max([timedelta(0), *(s.window for s in Stream.registry.values() if s.backfill and s.window and not s.persist)])
            start   = now - longest
            t       = start - timedelta(seconds=start.timestamp() % Stream.cycle.total_seconds())  # on the cycles' grid
        else:
            for stream in list(Stream.registry.values()):
                if stream.backfill and stream._table is None:  Stream.fill(stream, t)
        Stream.live = now
        for fetch in cls.sources:
            fetch(t, now)

        past = retained(list(Stream.registry.values()))
        while t + Stream.cycle <= now:
            t += Stream.cycle
            Stream.tick(t, past if t + Stream.cycle <= now else None)  # the present: every stream
        Stream.now = t  # where the next run continues
