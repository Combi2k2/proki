"""ActivityWatch's REST API (http://host:port/api/0), what its watchers record, and how
to look up a moment in it.

Watchers store events in typed buckets as (timestamp, duration, data), with identical
neighbours merged. The bucket types proki reads:

    WINDOW   the window watcher      {"app", "title"} (on macOS, also "url" in a browser)
    WEBTAB   the browser extension   {"url", "title"}
    INPUT    the input watcher       {"presses" (down and up), "clicks", "deltaX", "deltaY",
                                      "scrollX", "scrollY"}, an event every ~5 s
    AFK      the AFK watcher         {"status": "afk" / "not-afk"}

Watchers report every few seconds and send their reports in batches: neighbouring events
leave tiny gaps, and the newest event ends a little before now. So an event's value holds
until the next event starts, for at most `HOLD` after its end; longer gaps are unknown.

Only core/signals/primitive.py reads a `Record`; it keeps what it needs as its own tables.
"""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import NamedTuple

import requests

WINDOW = "currentwindow"
WEBTAB = "web.tab.current"
INPUT = "os.hid.input"
AFK = "afkstatus"

# how long a value outlives its event (see above)
HOLD = {
    WINDOW: timedelta(seconds=15),
    WEBTAB: timedelta(seconds=0),
    INPUT: timedelta(seconds=15),
    AFK: timedelta(seconds=15),
}


class Event(NamedTuple):
    start: datetime
    end: datetime
    data: dict

    @classmethod
    def parse(cls, raw: dict) -> Event:
        """From the server's JSON: {"timestamp", "duration" (s), "data"}."""
        start = datetime.fromisoformat(raw["timestamp"])
        return cls(start, start + timedelta(seconds=raw["duration"]), raw["data"])


class Events:
    """One bucket type's events, oldest first, searchable by time."""

    def __init__(self, events: list[Event], hold: timedelta = timedelta(0)):
        self.events = sorted(events, key=lambda e: e.start)
        self._starts = [e.start for e in self.events]
        self._untils = [e.end + hold for e in self.events]

        for i in range(len(self.events) - 1):
            if self._untils[i] > self.events[i + 1].start:
                self._untils[i] = self.events[i + 1].start

    def covering(self, t: datetime) -> Event | None:
        """The event whose value holds at t (start < t <= until)."""
        i = bisect_left(self._starts, t) - 1
        return self.events[i] if i >= 0 and t <= self._untils[i] else None

    def latest(self, t: datetime) -> Event | None:
        """The last event that started before t, however long ago."""
        i = bisect_left(self._starts, t)
        return self.events[i - 1] if i else None


class ActivityWatchClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 5600, timeout: float = 10):
        self.api = f"http://{host}:{port}/api/0"
        self.timeout = timeout
        self.session = requests.Session()

    def is_up(self) -> bool:
        try:
            return self.session.get(f"{self.api}/info", timeout=1).ok
        except requests.RequestException:
            return False

    def buckets(self) -> dict[str, dict]:
        """Every bucket, by id: {"type": "currentwindow", "hostname": ..., ...}."""
        return self._get("/buckets/")

    def events(
        self,
        bucket_id: str,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        """A bucket's events starting between `start` and `end` (default: any), at most
        `limit` of them (the server's order isn't guaranteed to be newest first)."""
        params = {"start": start and start.isoformat(), "end": end and end.isoformat(), "limit": limit}
        return self._get(f"/buckets/{bucket_id}/events", {k: v for k, v in params.items() if v is not None})

    def _get(self, path: str, params: dict | None = None):
        response = self.session.get(self.api + path, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()


class Record:
    """What the watchers recorded between `start` and `end`: `record[WINDOW]` is the
    window watcher's `Events`, fetched when first asked for."""

    def __init__(self, start: datetime, end: datetime, fetch: Callable[[str], list[Event]]):
        self.start = start
        self.end = end
        self._fetch = fetch
        self._events: dict[str, Events] = {}
        self.newest: dict[str, datetime] = {}  # bucket id → when its newest fetched event starts

    def __getitem__(self, bucket_type: str) -> Events:
        if bucket_type not in self._events:
            hold = HOLD.get(bucket_type, timedelta(0))
            self._events[bucket_type] = Events(self._fetch(bucket_type), hold)
        return self._events[bucket_type]

    @classmethod
    def of(cls, start: datetime, end: datetime, events: dict[str, list[Event]]) -> Record:
        """A recording from events in hand (tests, replays)."""
        return cls(start, end, lambda bucket_type: events.get(bucket_type, []))

    @classmethod
    def fetch(cls, start: datetime, end: datetime, client: ActivityWatchClient, previous: Record | None = None) -> Record:
        """From the server, each bucket type when first asked for.

        Each bucket is read from where its newest event known from the `previous` fetch
        starts, not just from `start`: that event may still be running (a window you stay
        in, a tab you stay on), and the server only returns events that start in the range.
        Only those times are kept from `previous`, so it can be let go."""
        known = dict(previous.newest) if previous is not None else {}
        buckets: dict[str, dict] = {}

        def events(bucket_type: str) -> list[Event]:
            if not buckets:
                buckets.update(client.buckets())
            found = []
            for bucket_id, info in buckets.items():
                if info.get("type") != bucket_type:
                    continue
                since = min(known.get(bucket_id, start), start)
                for event in map(Event.parse, client.events(bucket_id, since, end)):
                    found.append(event)
                    record.newest[bucket_id] = max(event.start, record.newest.get(bucket_id, event.start))
                if bucket_id not in record.newest and bucket_id in known:
                    record.newest[bucket_id] = known[bucket_id]  # nothing new: the old one still holds
            return found

        record = cls(start, end, events)
        return record
