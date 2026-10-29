"""Streams: values that change over time, such as key presses, focus, or whether you're in a
session.

Time moves in cycles, one every `Stream.cycle` (10 s unless the config says otherwise). A
stream has one value a cycle, None when it's unknown:

    an input        what your computer recorded, or the clock
    an operator     made of other streams: ts_mean(keys, 5)
    Signal          an expression, named
    Variable        a value that's set: by a program, or by you

Every named stream is in `Stream.registry`, where expressions find it by its name.

`Stream.tick(t)` runs a cycle: each stream moves on to `t` after what it reads, whatever
order they were made in. Its value is worked out as it's first read in the cycle, from what
it reads as it is then; a variable reads as it's set, at once.

A stream with `backfill` keeps its past, a value a cycle over its `window`. With `persist`
its past is saved too: after a restart, it's still there, and the time proki wasn't running
is unknown.
"""

from __future__ import annotations

from bisect import bisect_right
from collections import deque
from collections.abc import Callable, Iterable, Sequence
from datetime import datetime, timedelta
from typing import Any, ClassVar, Protocol

from proki.errors import ExprError

Value = float | bool | str | None
Infer = Callable[[Callable[["Stream"], Any]], Any]   # a type, from the types of what it reads (`of(stream)`)
NEVER = timedelta.max                                # the period of a stream that never changes (a constant)
ALIVE = timedelta(minutes=10)                        # a saved value unchanged this long is saved again: a longer gap, proki wasn't running


class Storage(Protocol):
    """Where the streams that persist save their past. The app gives one."""

    def load(self, name: str, since: datetime) -> list[tuple[datetime, Any]]: ...
    def save(self, name: str, t: datetime, value: Any) -> None: ...
    def forget(self, name: str, before: datetime) -> None: ...  # its rows at or before `before` let go


class Stream:
    """A value a cycle.

    One may take a new value more slowly than every cycle, one every `period` (every(x, 5):
    one every 5 minutes, held in between); `fresh` says whether it took one this cycle.

        backfill    it keeps its past, a value a cycle
        window      how far back (None: as far as what it reads keeps theirs)
        persist     its past is saved too, and there again after a restart
    """

    registry  : ClassVar[dict[str, Stream]] = {}            # every named stream, by name (a newer one replaces an older one)
    storage   : ClassVar[Storage | None] = None             # where the past of the ones that persist is saved
    now       : ClassVar[datetime | None] = None            # the cycle being run
    live      : ClassVar[datetime | None] = None            # the present the run catches up to: the cycles before it, the past
    cycle     : ClassVar[timedelta] = timedelta(seconds=10) # the time between cycles
    keeps     : ClassVar[bool] = False                      # whether its value carries over from the cycles before (a window's does)

    name      : str = ""
    desc      : str = ""                                    # what it is, in a line (an operator has none)
    inputs    : Sequence[Stream] = ()                       # what it reads
    period    : timedelta | None = None                     # how often it takes a new value (None: every cycle)
    window    : timedelta | None = None                     # how far back its past goes
    fresh     : bool = True                                 # whether it took a new value this cycle
    backfill  : bool = False                                # whether it keeps its past
    persist   : bool = False                                # whether its past is saved

    _typed    : str | dict | None = None                    # its type, once known
    _infer    : Infer | None = None                         # how its type's worked out from what it reads (None: it has one)
    _cache    : Any = None                                  # this cycle's value, once worked out
    _cached   : bool = False                                # whether it is
    _table    : deque[tuple[datetime, Any]] | None = None   # its past, (time, value), the oldest first
    _saved    : tuple[datetime, Any] | None = None          # the last of it saved
    _playback : deque[tuple[datetime, Any]] | None = None   # its past, given back while another's is built (`fill`)

    @property
    def type(self) -> str | dict:
        """What its values are (any: it can't tell)."""
        if self._typed is None and self._infer is not None:  settle([self])
        return "any" if self._typed is None else self._typed

    def advance(self, t: datetime) -> None:
        """On to the cycle at `t` (a window takes its input's new value, lets the old ones go)."""
        self._cached = False

    def current(self) -> Any:
        """This cycle's value."""
        if not self._cached:
            self._cache  = self.compute()
            self._cached = True
        return self._cache

    def compute(self) -> Any:
        """This cycle's value, worked out: each kind of stream says how."""
        raise NotImplementedError

    def history(self, since: datetime) -> list[tuple[datetime, Any]]:
        """Its past after `since`, (time, value), the oldest first (none: it keeps none)."""
        if self._table is None:
            return []
        rows = list(self._table)
        return rows[bisect_right(rows, since, key=lambda row: row[0]):]

    def reach(self) -> datetime | None:
        """How far back its past is known: its own, else the latest of what it reads."""
        if self._table:
            return self._table[0][0]
        reaches = [r for i in self.inputs if (r := i.reach()) is not None]
        return max(reaches) if reaches else None

    def record(self, t: datetime) -> None:
        """This cycle's value, kept in its past (and saved, if it persists), the past out of
        its window let go."""
        if not self.backfill:
            return
        if self._table is None:  # its first cycle: what was saved before, in its window
            self._table = deque()
            if self.persist and Stream.storage is not None and self.window:
                Stream.storage.forget(self.name, t - self.window)
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
        if self.window:  # (t − window, t], as the windows are
            oldest, keep = t - self.window, False
        else:  # back to what it reads' oldest
            oldest, keep = max([r for i in self.inputs if (r := i.reach()) is not None], default=None), True
        while oldest is not None and table and (table[0][0] < oldest if keep else table[0][0] <= oldest):
            table.popleft()

    def close(self) -> None:
        """Proki quitting: its saved past says nothing's known from the next cycle on."""
        if self.persist and Stream.storage is not None and self._saved is not None and self._saved[1] is not None and Stream.now:
            Stream.storage.save(self.name, Stream.now + (self.period or Stream.cycle), None)
            self._saved = (Stream.now, None)

    def play(self, t: datetime) -> None:
        """While another's past is built: its value at `t` taken from its past, not worked out."""
        assert self._playback is not None
        self.fresh = False
        while self._playback and self._playback[0][0] <= t:
            self._cache, self._cached, self.fresh = self._playback.popleft()[1], True, True

    @classmethod
    def tick(cls, t: datetime, streams: Iterable[Stream] | None = None) -> None:
        """The cycle at `t`, for every named stream (or `streams`), each after what it reads.
        ExprError for one that reads itself."""
        Stream.now = t
        done : set[Stream] = set()
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
        """The past of a stream made while proki runs, up to `until`, as far back as what it
        reads keeps (or its window): what keeps its past gives it back, not worked out again."""
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
    """The type of each of `streams`, and of what they read, worked out from what each reads
    (`again`: anew, the ones known before too). One coming round to itself reads itself as any."""
    made: list[Stream] = []
    seen: set[Stream]  = set()

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
    """The ones among `streams`, and what they read, whose value carries over from the cycles
    before: a window, or one keeping its past. Catching up on the past, only they're run each
    cycle; the others, at the present one."""
    seen: set[Stream]  = set()
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
    """A saved past, a row a `step` up to `until`: each value until the next, a few minutes at
    most (a longer gap: nothing known)."""
    made = []
    for (t, value), after in zip(rows, [*(r[0] for r in rows[1:]), None]):
        end = min(t + ALIVE, after if after else max(until, t + step))  # the last: up to now at most
        while t < end:
            made.append((t, value))
            t += step
    return made
