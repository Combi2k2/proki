"""Fill the persisted signals' history (the metrics) from the past ActivityWatch recorded.

    proki-backfill --days 14

It replays the past, cycle by cycle, through the same config, in a process of its own: only
the persisted signals' history is written. Variables and programs aren't touched: nothing is
asked, nothing changes. Windows get your labels (or a similar app's: jev isn't asked), so
depth is as it would be. A value already kept for a time is replaced by the replayed one.
"""

from __future__ import annotations

import argparse
import time as clock
from datetime import datetime, timedelta, timezone

from proki import settings, storage
from proki.core.primitives import Primitive, Recording
from proki.core.signals import Stream
from proki.model import Builder
from proki.programs.code.classify import AppDB, Apps
from proki.services.activitywatch import ActivityWatchClient


class Replayed:
    """Where replayed rows go: written to the history, never read back nor pruned, so rows
    kept live don't stop older ones from being written."""

    def __init__(self, history: storage.HistoryDB):
        self.history = history

    def load(self, name: str, since: datetime) -> list:
        return []

    def save(self, name: str, t: datetime, value) -> None:
        self.history.save(name, t, value)

    def forget(self, name: str, before: datetime) -> None:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--days", type=float, default=14, help="how far back (default 14)")
    days   = parser.parse_args().days
    db     = storage.connect(settings.DB_PATH)
    Apps(AppDB(db))  # the `label` and `depth` inputs read your labels
    Recording.client = ActivityWatchClient(settings.HOST, settings.AW_PORT)
    Stream.storage   = Replayed(storage.HistoryDB(db))

    if (specs := storage.SpecDB(db).load()) is None:
        raise SystemExit("start proki once first: it keeps your programs")
    persisted  = [s.name for s in Builder(specs).build().signals if s.persist]
    now        = datetime.now(timezone.utc)
    start      = now - timedelta(days=days)
    Stream.now = start - timedelta(seconds=start.timestamp() % Stream.cycle.total_seconds())  # on the cycles' grid
    print(f"replaying {days:g} days ({Stream.now:%b %d %H:%M} to now) for {', '.join(persisted)}", flush=True)
    began      = clock.monotonic()
    Primitive.run(now)
    print(f"done in {clock.monotonic() - began:.0f} s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
