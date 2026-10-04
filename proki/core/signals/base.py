"""Signals: quantities that change over time (key presses, focus, in a session, ...).

Time moves in cycles of `Stream.cycle` (10 s unless the config says otherwise): a `Stream`
is a time series with one value per cycle (None: unknown). Three kinds of streams:

    Primitive   read from what ActivityWatch recorded, or from proki's state (primitive.py)
    operator    made by an operator from other streams; a window keeps a queue (core/ops/)
    Signal      a name and an `expr`, a time-series expression over other streams

Every Signal and Primitive is kept in `Stream.registry` by name; an expression's names
are looked up there. Rules (core/rules.py) read one signal each.

Each cycle, a stream is moved on with `advance()` and read with `current()`:

    advance(t)  the cycle at t: a window pushes its input's new value on its queue and
                drops what fell out; the cached value is dropped
    current()   the value in this cycle, worked out when first asked and cached until
                the next `advance`

`Stream.tick(t)` advances every stream once, inputs before the streams that read them (so
a stream read by several others moves on once per cycle), then keeps the tables: a
stream with `backfill` keeps its history (its `window` of it) as (time, value) rows, and
a `persist`ed one also saves them (`Stream.storage`). Operators know no clock, only each
cycle's time: a window over w minutes holds what came in the last w minutes. Which
moments the cycles are, and what each primitive reads, is up to primitive.py.

Expressions use Python's syntax, parsed with `ast` and walked by hand (no `eval`):

    ts_mean(keys + mouse_click, 5)
    ts_sum(sector == "video", 60)
    ts_mean(focus_2m, 2) - delay(ts_mean(focus_2m, 2), 2)
    ts_count(app, 30) > 20 and not in_session

numbers, text in quotes, + - * /, comparisons (and `in` a tuple of constants), and /
or / not, the operators of ops/, and names. Time is always in minutes: windows, delays, and rates (keys is presses per
minute). An expression compiles into a tree of streams on the first cycle after the
signal is made, so it may name streams made after it.
"""

from __future__ import annotations

import ast
import operator
from bisect import bisect_right
from collections import deque
from collections.abc import Iterable
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any, ClassVar, Protocol

Value = float | bool | str | None
NEVER = timedelta.max  # the period of something that never changes


class Storage(Protocol):
    """Where persisted streams keep their history (the app gives one: core/store.py)."""

    def load(self, name: str, since: datetime) -> list[tuple[datetime, Any]]: ...
    def save(self, name: str, t: datetime, value: Any) -> None: ...


class Stream:
    """A time series: a value each cycle, a new one every `period` (None: each cycle).

    `backfill`: it keeps its history as a table of (time, value) rows, filled in when it
    starts (the startup replay, or from its inputs' tables for one added later). `window`:
    how much time the table keeps; None: as far back as its inputs' tables reach.
    `persist`: the table is also saved (`Stream.storage`), so it reaches back further than
    the replay; a saved table is taken as it is up to its last row, and the cycles after
    it add to it.
    """

    registry: ClassVar[dict[str, Stream]] = {}  # every named stream (signals, primitives), by name (the newest of a name)
    storage: ClassVar[Storage | None] = None
    now: ClassVar[datetime | None] = None  # the current cycle's time (`tick` sets it)
    cycle: ClassVar[timedelta] = timedelta(seconds=10)  # the time between cycles (the config's "cycle")

    name: str = ""
    inputs: list[Stream] = []  # the streams it reads (advanced before it)
    period: timedelta | None = None  # how often it takes a new value; None: each cycle (`every` makes slower ones)
    window: timedelta | None = None
    fresh: bool = True  # whether it took a new value this cycle
    backfill: bool = False
    persist: bool = False
    _playback: deque[tuple[datetime, Any]] | None = None  # its rows, played back while filling another
    _table: deque[tuple[datetime, Any]] | None = None
    _cache: Any = None
    _cached = False

    def advance(self, t: datetime) -> None:
        """Move on to the cycle at `t` (operators with a queue push and drop here)."""
        self._cached = False

    def current(self) -> Any:
        """The value in this cycle, worked out once."""
        if not self._cached:
            self._cache  = self.compute()
            self._cached =  True
        return self._cache

    def compute(self) -> Any:
        """Work out the value in this cycle (from the inputs' current values, the queue)."""
        raise NotImplementedError

    def history(self, since: datetime) -> list[tuple[datetime, Any]]:
        """Its table's rows after `since`, oldest first (empty without a table)."""
        if self._table is None:
            return []
        rows = list(self._table)
        return rows[bisect_right(rows, since, key=lambda row: row[0]):]

    def reach(self) -> datetime | None:
        """How far back its history is known: its table's oldest row, else its inputs'
        (the most recent of them: older, one of them doesn't know)."""
        if self._table:
            return self._table[0][0]
        reaches = [r for i in self.inputs if (r := i.reach()) is not None]
        return max(reaches) if reaches else None

    def record(self, t: datetime) -> None:
        """Add this cycle's value to its table (and storage), if it keeps one, the value is
        new and the table doesn't reach this far yet; let go of rows out of its window."""
        if not self.backfill:
            return
        if self._table is None:  # the first cycle (fresh or not: readers may look now)
            self._table = deque()
            if self.persist and Stream.storage is not None:  # what was saved before this run
                since = t - self.window if self.window else datetime.min.replace(tzinfo=t.tzinfo)
                self._table.extend(Stream.storage.load(self.name, since))
        table = self._table
        if not self.fresh or (table and table[-1][0] >= t):
            return
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
        """Take its value at `t` from its rows (while filling another stream): the latest
        row at or before `t`; fresh if one came in this cycle."""
        assert self._playback is not None
        self.fresh = False
        while self._playback and self._playback[0][0] <= t:
            self._cache, self._cached, self.fresh = self._playback.popleft()[1], True, True

    @classmethod
    def tick(cls, t: datetime, streams: Iterable[Stream] | None = None) -> None:
        """The cycle at `t`: advance each stream once, its inputs first (`streams`: every
        signal and primitive, and so everything they read), then keep the tables. A stream
        playing back its rows takes its value from them, without its inputs."""
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
        """Fill in a stream added after startup, from the tables the others keep (each plays
        its rows back in order): the cycles from as far back as they reach (or its window)
        up to `until`. The others stay as they are."""
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


class Signal(Stream):
    def __init__(self, name: str, expr: str, backfill: bool = False, window: timedelta | None = None,
                 persist: bool = False):
        if not name:    raise ValueError("signal name can't be empty")
        if not expr:    raise ValueError("signal expr can't be empty")
        if persist and not backfill:
            raise ValueError("a persisted signal keeps a table: it needs backfill=True")

        parse(expr)  # a syntax error shows now; unknown names on the first cycle

        self.name = name
        self.expr = expr  # e.g. "ts_mean(keys, 5)"
        self.backfill = backfill
        self.window = window
        self.persist = persist
        self._tree: Stream | None = None
        Stream.registry[name] = self

    @property
    def inputs(self) -> list[Stream]:  # type: ignore[override]
        if self._tree is None:
            self._tree = compile_expr(self.expr)
        return [self._tree]

    def advance(self, t: datetime) -> None:
        super().advance(t)
        self.period, self.fresh = self.inputs[0].period, self.inputs[0].fresh

    def compute(self) -> Any:
        return self.inputs[0].current()

    def __repr__(self) -> str:
        return f"<Signal {self.name} = {self.expr}>"


class ExprError(ValueError):
    pass

BINARY = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv
}
COMPARE = {
    ast.Lt: operator.lt, ast.LtE: operator.le,
    ast.Gt: operator.gt, ast.GtE: operator.ge,
    ast.Eq: operator.eq, ast.NotEq: operator.ne,
    ast.In: lambda a, b: a in b, ast.NotIn: lambda a, b: a not in b
}


@lru_cache(maxsize=256)
def parse(expr: str) -> ast.expr:
    try:
        return ast.parse(expr, mode="eval").body
    except SyntaxError as e:
        raise ExprError(f"can't read {expr!r}: {e.msg}") from None


def compile_expr(expr: str) -> Stream:
    """The expression as a stream; its names refer to `Stream.registry`."""
    from proki.core.ops import Constant

    result = _build(parse(expr))
    return result if isinstance(result, Stream) else Constant(result)


def _lift(f: Any, *args: Any) -> Any:
    """`f` over the arguments: worked out now when they're all constants (`7 * 1440` is a
    number, usable as a window), else a stream (ops.Lift)."""
    from proki.core import ops  # ops builds on Stream

    if any(isinstance(a, Stream) for a in args):
        return ops.Lift(f, *args)
    return None if any(a is None for a in args) else f(*args)


def _build(node: ast.expr) -> Any:
    from proki.core import ops  # ops builds on Stream

    match node:
        case ast.Constant(value=value) if isinstance(value, (int, float, str, bool)):
            return value
        case ast.Tuple(elts=elts) if all(isinstance(e, ast.Constant) for e in elts):
            return tuple(_build(e) for e in elts)  # for `in`: sector in ("ide", "terminal")
        case ast.Name(id=name):
            if name not in Stream.registry:
                raise ExprError(f"unknown name {name!r}")
            return Stream.registry[name]
        case ast.Call(func=ast.Name(id=name), args=args, keywords=[]) if name in ops.FUNCTIONS:
            return ops.FUNCTIONS[name](*(_build(a) for a in args))
        case ast.BinOp(left=left, op=op, right=right) if type(op) in BINARY:
            f = BINARY[type(op)]
            return _lift(
                lambda a, b: None if f is operator.truediv and b == 0 else f(a, b),
                _build(left),
                _build(right)
            )
        case ast.UnaryOp(op=ast.USub(), operand=operand):   return _lift(operator.neg, _build(operand))
        case ast.UnaryOp(op=ast.Not(), operand=operand):    return _lift(operator.not_, _build(operand))
        case ast.BoolOp(op=op, values=values):
            combine = all if isinstance(op, ast.And) else any
            return _lift(lambda *vs: combine(bool(v) for v in vs), *(_build(v) for v in values))
        case ast.Compare(left=left, ops=comparisons, comparators=rights) if all(type(c) in COMPARE for c in comparisons):
            operands = [_build(left), *(_build(r) for r in rights)]
            fs = [COMPARE[type(c)] for c in comparisons]
            return _lift(lambda *vs: all(f(a, b) for f, a, b in zip(fs, vs, vs[1:])), *operands)
    raise ExprError(f"not allowed in an expression: {ast.unparse(node)}")

