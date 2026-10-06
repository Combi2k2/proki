"""Streams: values that change over time, such as key presses, focus, or whether you're in
a session.

Time moves in steps called cycles, one every `Stream.cycle` (10 s unless the config
says otherwise). A `Stream` has one value per cycle. None means unknown.

There are three kinds of streams:

    Primitive   read from what ActivityWatch recorded, or from the clock (core/primitives/)
    operator    built from other streams, like ts_mean(keys, 5) (core/ops/)
    Signal      a named expression over other streams (signal.py, expr.py)

Every named stream is kept in `Stream.registry`, and expressions look names up there.

Each cycle, every stream does two things:

    advance(t)  move on to the cycle at time t (a window adds the new value, drops old ones)
    current()   give this cycle's value (worked out the first time it's asked, then cached)

`Stream.tick(t)` runs one cycle for all streams, each stream's inputs before the stream
itself, so a stream read by several others still moves on only once.

History: a stream with `backfill` keeps a table of its past values as (time, value)
rows, covering its `window`. With `persist`, the table is also saved to disk
(`Stream.storage`), so it survives restarts. Which moments the cycles fall on, and what
each primitive reads, is up to core/primitives/.
"""

from __future__ import annotations

from bisect import bisect_right
from collections import deque
from collections.abc import Iterable, Sequence
from datetime import datetime, timedelta
from typing import Any, ClassVar, Protocol

from proki.errors import ExprError

Value = float | bool | str | None
NEVER = timedelta.max  # the period of a stream that never changes (a constant)


class Storage(Protocol):
    """Where persisted streams save their tables. The app provides one."""

    def load(self, name: str, since: datetime) -> list[tuple[datetime, Any]]: ...
    def save(self, name: str, t: datetime, value: Any) -> None: ...
    def forget(self, name: str, before: datetime) -> None: ...  # delete rows at or before `before`


class Stream:
    """A time series: one value per cycle.

    A stream may take a new value every cycle, or more slowly, every `period` (a stream
    made by `every(x, 5)` takes one every 5 minutes and holds it in between). `fresh`
    says whether it took a new value this cycle.

    History (optional):
        backfill    keep a table of past values, as (time, value) rows
        window      how far back the table goes (None: as far as its inputs' tables go)
        persist     also save the table to disk. On the next start, the saved rows are
                    loaded and new cycles are added after the last one
    """

    registry: ClassVar[dict[str, Stream]] = {}  # every named stream, by name (a newer one replaces an older one)
    storage: ClassVar[Storage | None] = None  # where persisted tables are saved
    now: ClassVar[datetime | None] = None  # the time of the cycle being run (`tick` sets it)
    live: ClassVar[datetime | None] = None  # the present moment the run is catching up to. Cycles before it replay the past
    cycle: ClassVar[timedelta] = timedelta(seconds=10)  # the time between cycles (the config's "cycle")
    epoch: ClassVar[int] = 0  # bumped when a variable changes, so every cached value gets worked out again

    name: str = ""
    inputs: Sequence[Stream] = ()  # the streams it reads (each subclass sets its own)
    period: timedelta | None = None  # how often it takes a new value. None: every cycle
    window: timedelta | None = None  # how far back its table goes
    fresh: bool = True  # whether it took a new value this cycle
    backfill: bool = False  # whether it keeps a table
    persist: bool = False  # whether the table is saved to disk
    _playback: deque[tuple[datetime, Any]] | None = None  # rows being replayed (only during `fill`)
    _table: deque[tuple[datetime, Any]] | None = None  # its (time, value) rows, oldest first
    _cache: Any = None  # this cycle's value, once worked out
    _cached = False
    _epoch = -1  # the epoch the cached value is from

    def advance(self, t: datetime) -> None:
        """Move on to the cycle at time `t`. The base forgets last cycle's value. A window
        operator also adds its input's new value and drops the ones that fell out."""
        self._cached = False

    def current(self) -> Any:
        """This cycle's value. Worked out on the first call and cached. Worked out again if
        a variable changed since (see `epoch`)."""
        if not self._cached or self._epoch != Stream.epoch:
            self._cache  = self.compute()
            self._cached = True
            self._epoch  = Stream.epoch
        return self._cache

    def compute(self) -> Any:
        """Work out this cycle's value. Each kind of stream says how."""
        raise NotImplementedError

    def history(self, since: datetime) -> list[tuple[datetime, Any]]:
        """The table's rows after time `since`, oldest first. Empty if it keeps no table."""
        if self._table is None:
            return []
        rows = list(self._table)
        return rows[bisect_right(rows, since, key=lambda row: row[0]):]

    def reach(self) -> datetime | None:
        """How far back this stream's past is known: its table's oldest row. Without a
        table, the latest of its inputs' reaches (before that, one input doesn't know)."""
        if self._table:
            return self._table[0][0]
        reaches = [r for i in self.inputs if (r := i.reach()) is not None]
        return max(reaches) if reaches else None

    def record(self, t: datetime) -> None:
        """Add this cycle's value to the table, and to disk if persisted.

        Only for a stream with a table, and only when it took a new value. A row the
        table already has (loaded from disk) isn't added twice. Rows older than the
        window are dropped. On the first call, a persisted table first loads its saved
        rows and deletes the ones that fell out of the window."""
        if not self.backfill:
            return
        if self._table is None:  # the first cycle (fresh or not: readers may look now)
            self._table = deque()
            if self.persist and Stream.storage is not None and self.window:  # what was saved before this run
                Stream.storage.forget(self.name, t - self.window)  # what fell out of its window
                self._table.extend(Stream.storage.load(self.name, t - self.window))
        if not self.fresh or (self._table and self._table[-1][0] >= t):
            return
        table = self._table
        value = self.current()
        table.append((t, value))
        if self.persist and Stream.storage is not None:
            Stream.storage.save(self.name, t, value)
        if self.window:  # (t − window, t], like the operators' windows
            oldest, keep = t - self.window, False
        else:  # back to its inputs' oldest
            oldest, keep = max([r for i in self.inputs if (r := i.reach()) is not None], default=None), True
        while oldest is not None and table and (table[0][0] < oldest if keep else table[0][0] <= oldest):
            table.popleft()

    def play(self, t: datetime) -> None:
        """During `fill`: take the value at time `t` from the table instead of working it
        out (the latest row at or before `t`, fresh if that row is from this cycle)."""
        assert self._playback is not None
        self.fresh = False
        while self._playback and self._playback[0][0] <= t:
            self._cache, self._cached, self.fresh = self._playback.popleft()[1], True, True
            self._epoch = Stream.epoch

    @classmethod
    def tick(cls, t: datetime, streams: Iterable[Stream] | None = None) -> None:
        """Run the cycle at time `t`.

        Each stream (all named ones by default, or `streams`) is advanced once, after its
        inputs, and then adds its value to its table. A stream that reads itself, directly
        or through others, raises ExprError."""
        Stream.now = t
        done: set[Stream] = set()
        open_: set[Stream] = set()

        def visit(stream: Stream) -> None:
            if stream in done:
                return
            if stream._playback is not None:
                stream.play(t)
                done.add(stream)
                return
            if stream in open_:
                raise ExprError(f"{stream.name or stream!r} reads itself")
            open_.add(stream)
            for i in stream.inputs:
                visit(i)
            open_.discard(stream)
            stream.advance(t)
            stream.record(t)
            done.add(stream)

        for stream in list(Stream.registry.values()) if streams is None else streams:
            visit(stream)

    @classmethod
    def fill(cls, stream: Stream, until: datetime) -> None:
        """Build the past of a stream added while proki runs.

        The cycles from as far back as its inputs' tables go (or its window) up to `until`
        are run for this stream alone. Streams with a table give their recorded values
        instead of being worked out again.

        Known limits (unused today, since streams are only made at startup): an input
        without a table is worked out again, which disturbs its live window. A slow input
        can give its present value for the first cycles."""
        start = stream.reach()
        if start is None:
            return
        if stream.window is not None:
            start = max(start, until - stream.window)
        playing = [s for s in Stream.registry.values() if s is not stream and s._table]
        for s in playing:
            s._playback = deque(s.history(start - Stream.cycle))
        try:
            t = start
            while t <= until:
                cls.tick(t, [stream])
                t += Stream.cycle
        finally:
            for s in playing:
                s._playback, s._cached = None, False
            Stream.now = until
