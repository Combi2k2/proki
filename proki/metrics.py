"""The metrics: the global signals whose history is saved, read back in buckets that fit the
horizon.

    day     288 buckets of 5 minutes
    week    336 of 30 minutes
    month   360 of 2 hours
    year    365 of a day

Only a persisted signal can be one: its table, as far back as its window, is saved. You choose
which are reported, and how a bucket's made: its values' mean, or their sum, min, max or last.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Any

from proki.core.signals import Signal, Storage, Stream
from proki.core.signals.stream import ALIVE, expanded
from proki.storage import Table

HORIZONS = {"day": (5, 288), "week": (30, 336), "month": (120, 360), "year": (1440, 365)}                # minutes a bucket, buckets
METHODS  = {"mean": lambda v: sum(v) / len(v), "sum": sum, "min": min, "max": max, "last": lambda v: v[-1]}  # a bucket's value, of its values


@dataclass(frozen=True)
class Metric:
    """A persisted signal: reported or not, and how its buckets are made."""

    name   : str
    on     : bool = True
    method : str  = "mean"

    def __post_init__(self):
        if self.method not in METHODS:
            raise ValueError(f"no method {self.method!r}: {', '.join(METHODS)}")


class MetricDB(Table[Metric]):
    NAME = "metrics"
    KEY  = "name"


class Metrics:
    """How each metric's buckets are made, and the history saved."""

    def __init__(self, db: Any, history: Storage):
        self.chosen  = MetricDB(db)
        self.history = history

    def of(self, name: str) -> Metric:
        """How `name`'s buckets are made: as you chose, else the mean."""
        return found[0] if (found := self.chosen.read(name)) else Metric(name)

    def list(self, signals: list[Signal]) -> list[dict]:
        """Every global signal: what it is, whether it's persisted and reported, how far back it
        keeps (minutes), and how its buckets are made."""
        return [{"name": s.name, "desc": s.desc, "expr": s.expr, "persist": s.persist, "on": s.persist and m.on,
                 "pace": pace(s), "method": m.method, "keep": s.window.total_seconds() / 60 if s.backfill and s.window else None}
                for s in signals if "." not in s.name for m in [self.of(s.name)]]

    def choose(self, name: str, **chosen: Any) -> None:
        """`name` reported or not (`on`), its buckets made by `method`, from now on."""
        self.chosen.create(replace(self.of(name), **chosen))

    def read(self, signal: Signal, horizon: str, now: datetime | None = None) -> dict:
        """Its history over `horizon`, a value a bucket (None: nothing in it), each bucket by its
        start, aligned to the local clock."""
        if horizon not in HORIZONS:
            raise ValueError(f"no horizon {horizon!r}: {', '.join(HORIZONS)}")
        size, count = HORIZONS[horizon]
        every  = pace(signal)
        now    = (now or datetime.now(timezone.utc)).astimezone()
        local  = now.replace(tzinfo=None) - datetime(1970, 1, 1)
        end    = now - timedelta(minutes=(local.total_seconds() / 60) % size) + timedelta(minutes=size)
        start  = end - timedelta(minutes=size * count)
        back   = timedelta(minutes=every or 0)  # a slow signal's value is kept as its span ends: at its start
        step   = timedelta(minutes=every) if every else Stream.cycle
        values : list[list[float]] = [[] for _ in range(count)]
        for t, value in expanded(self.history.load(signal.name, start + back - ALIVE), step, now):  # saved as it changed: a row a step
            at = int((t - back - start).total_seconds() // (size * 60))
            if 0 <= at < count and isinstance(value, int | float):
                values[at].append(float(value))
        method = self.of(signal.name).method
        return {"size": size, "method": method,
                "buckets": [[(start + timedelta(minutes=size * i)).isoformat(), METHODS[method](v) if v else None] for i, v in enumerate(values)]}


def pace(signal: Signal) -> float | None:
    """Minutes between a signal's values (None: every cycle)."""
    period = signal.inputs[0].period if signal.inputs else None
    return period.total_seconds() / 60 if period and period != timedelta.max else None
