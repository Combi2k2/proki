"""Streams: values that change over time, such as key presses, focus, or whether you're in
a session.

Time moves in steps called cycles, one every `Stream.cycle` (10 s unless the config
says otherwise). A `Stream` has one value per cycle. None means unknown.

There are three kinds of streams:

    Primitive   read from what your computer recorded, or from the clock
    operator    built from other streams, like ts_mean(keys, 5)
    Signal      a named expression over other streams

Every named stream is kept in `Stream.registry`, and expressions look names up there.

Each cycle, every stream does two things:

    advance(t)  move on to the cycle at time t (a window adds the new value, drops old ones)
    current()   give this cycle's value (worked out the first time it's asked, then cached)

`Stream.tick(t)` runs one cycle for all streams, each stream's inputs before the stream
itself, so a stream read by several others still moves on only once.

History: a stream with `backfill` keeps a table of its past values as (time, value)
rows, covering its `window`. With `persist`, the table is also saved to disk
(`Stream.storage`), so it survives restarts: a row as its value changes, and one every
few minutes while it doesn't, read back a row a cycle (`expanded`). A longer gap is a
time proki wasn't running: nothing is known of it. As proki quits, each one's saved table
says nothing's known from then (`close`). Which moments the cycles fall on, and what
each primitive reads, is up to the primitives.
"""

from __future__ import annotations

from bisect import bisect_right
from collections import deque
from collections.abc import Callable, Iterable, Sequence
from datetime import datetime, timedelta
from typing import Any, ClassVar, Protocol

from proki.errors import ExprError

Value = float | bool | str | None
Infer = Callable[[Callable[["Stream"], Any]], Any]  # a type, from the types of what it reads (`of(stream)`)
NEVER = timedelta.max  # the period of a stream that never changes (a constant)
ALIVE = timedelta(minutes=10)  # a persisted value unchanged this long is saved again: a longer gap, proki wasn't running


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
    desc: str = ""  # what it is, in a line (an operator has none)
    _typed: str | dict | None = None  # compile time type
    _infer: Infer | None = None  # how its type's worked out from what it reads (None: it has one already)
    inputs: Sequence[Stream] = ()  # the streams it reads (each subclass sets its own)
    period: timedelta | None = None  # how often it takes a new value. None: every cycle
    window: timedelta | None = None  # how far back its table goes
    fresh: bool = True  # whether it took a new value this cycle
    backfill: bool = False  # whether it keeps a table
    persist: bool = False  # whether the table is saved to disk
    _playback: deque[tuple[datetime, Any]] | None = None  # rows being replayed (only during `fill`)
    _table: deque[tuple[datetime, Any]] | None = None  # its (time, value) rows, oldest first
    _saved: tuple[datetime, Any] | None = None  # the last row saved to disk (a persisted table's)
    _cache: Any = None  # this cycle's value, once worked out
    _cached = False
    _epoch = -1  # the epoch the cached value is from
    keeps: ClassVar[bool] = False  # whether its value carries over from the cycles before (a window's does)

    @property
    def type(self) -> str | dict:
        """What its values are (any: it can't tell), worked out once (`settle`)."""
        if self._typed is None and self._infer is not None:  settle([self])
        return "any" if self._typed is None else self._typed

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
                saved = Stream.storage.load(self.name, t - self.window - ALIVE)
                self._saved = saved[-1] if saved else None
                self._table.extend(row for row in expanded(saved, self.period or Stream.cycle, t) if row[0] > t - self.window)
        if not self.fresh or (self._table and self._table[-1][0] >= t):
            return
        table = self._table
        value = self.current()
        table.append((t, value))
        if self.persist and Stream.storage is not None and (self._saved is None or self._saved[1] != value or t - self._saved[0] >= ALIVE):
            Stream.storage.save(self.name, t, value)  # as it changes, and now and then while it doesn't
            self._saved = (t, value)
        if self.window:  # (t − window, t], like the operators' windows
            oldest, keep = t - self.window, False
        else:  # back to its inputs' oldest
            oldest, keep = max([r for i in self.inputs if (r := i.reach()) is not None], default=None), True
        while oldest is not None and table and (table[0][0] < oldest if keep else table[0][0] <= oldest):
            table.popleft()

    def close(self) -> None:
        """Proki quitting: its saved table says nothing's known from the next cycle on."""
        if self.persist and Stream.storage is not None and self._saved is not None and self._saved[1] is not None and Stream.now:
            Stream.storage.save(self.name, Stream.now + (self.period or Stream.cycle), None)
            self._saved = (Stream.now, None)

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


def settle(streams: Iterable[Stream], again: bool = False) -> None:
    """The type of each of `streams`, and of the streams they read, worked out from what each
    reads and kept (`again`: anew, the ones worked out before too). One whose type comes
    round to itself reads itself as any there."""
    made: list[Stream] = []
    seen: set[Stream] = set()

    def walk(stream: Stream) -> None:
        if stream in seen:
            return
        seen.add(stream)
        made.append(stream)
        for i in stream.inputs:
            walk(i)

    def of(stream: Stream) -> Any:
        if stream._typed is None and stream._infer is not None and stream not in working:
            working.add(stream)
            try:
                stream._typed = stream._infer(of)
            finally:
                working.discard(stream)
        return "any" if stream._typed is None else stream._typed

    for stream in streams:
        walk(stream)
    if again:
        for stream in made:
            if stream._infer is not None:  stream._typed = None
    
    working: set[Stream] = set()
    for stream in made:
        of(stream)


def retained(streams: Iterable[Stream]) -> list[Stream]:
    """The ones among `streams`, and the streams they read, whose value carries over from
    the cycles before: a window, or one keeping a table. Catching up on the past, only they
    need each cycle run: the others are worked out at the present one."""
    seen: set[Stream] = set()
    kept: list[Stream] = []

    def walk(stream: Stream) -> None:
        if stream in seen:
            return
        seen.add(stream)
        if stream.keeps or stream.backfill:
            kept.append(stream)
        for i in stream.inputs:
            walk(i)

    for stream in streams:
        walk(stream)
    return kept


def expanded(rows: list[tuple[datetime, Any]], step: timedelta, until: datetime) -> list[tuple[datetime, Any]]:
    """Saved rows (each saved as its value changed, and every few minutes while it didn't) as
    a row a `step`, before `until`: each row's value, until the next row, or for those few
    minutes at most (a longer gap: nothing known)."""
    made = []
    for (t, value), after in zip(rows, [*(r[0] for r in rows[1:]), None]):
        end = min(t + ALIVE, after if after else max(until, t + step))  # the last: until now at most (one after: as it is)
        while t < end:
            made.append((t, value))
            t += step
    return made
