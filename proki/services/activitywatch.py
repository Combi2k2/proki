"""ActivityWatch, the tracker (as `aw`): what its watchers recorded, and what held at a moment.

    client = ActivityWatchClient("127.0.0.1", 5600)
    record = Record.fetch(start, end, client)
    record["currentwindow"].covering(t)     →  Event(start, end, {"app": "Code", "title": ...}): what
                                               held at t (None: unknown)

What each watcher records:

    the window      {"app", "title"} (on macOS, also "url" in a browser)
    the web tab     {"url", "title"}
    the input       {"presses", "clicks", "deltaX", "deltaY", "scrollX", "scrollY"}, every few seconds
    being away      {"status": "afk" or "not-afk"}

A value holds until the next one, or a little after its own end. A longer gap is unknown.
"""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import NamedTuple

import requests

WINDOW  = "currentwindow"
WEBTAB  = "web.tab.current"
INPUT   = "os.hid.input"
AFK     = "afkstatus"

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
        """An event, as the server gives it."""
        start = datetime.fromisoformat(raw["timestamp"])
        return cls(start, start + timedelta(seconds=raw["duration"]), raw["data"])


class Events:
    """One watcher's events, oldest first."""

    def __init__(self, events: list[Event], hold: timedelta = timedelta(0)):
        self.events = sorted(events, key=lambda e: (e.start, e.end))  # twins: the longer last, the one that holds
        self._starts = [e.start for e in self.events]
        self._untils = [e.end + hold for e in self.events]

        for i in range(len(self.events) - 1):  # a value holds until the next event starts, at most
            nxt = self.events[i + 1].start
            if self._untils[i] > nxt:  self._untils[i] = nxt

    def covering(self, t: datetime) -> Event | None:
        """The event whose value holds at t (None: unknown)."""
        i = bisect_left(self._starts, t) - 1
        return self.events[i] if i >= 0 and t <= self._untils[i] else None

    def latest(self, t: datetime) -> Event | None:
        """The last event that started before t, however long ago."""
        i = bisect_left(self._starts, t)
        return self.events[i - 1] if i else None

    def overlapping(self, a: datetime, b: datetime) -> list[Event]:
        """The events that overlap (a, b], oldest first."""
        i = bisect_left(self._starts, b)
        found = []
        while i > 0 and self.events[i - 1].end > a:
            i -= 1
            found.append(self.events[i])
        return found[::-1]


class ActivityWatchClient:
    """The server at `host`:`port`."""

    def __init__(self, host: str, port: int, timeout: float = 10):
        self.api = f"http://{host}:{port}/api/0"
        self.timeout = timeout
        self.session = requests.Session()

    def is_up(self) -> bool:
        """Whether the server answers."""
        try:
            return self.session.get(f"{self.api}/info", timeout=1).ok
        except requests.RequestException:
            return False

    def buckets(self) -> dict[str, dict]:
        """Every bucket, by id: what records it, and where."""
        return self._get("/buckets/")

    def events(
        self,
        bucket_id: str,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        """A bucket's events that start between `start` and `end` (none: any), `limit` at most,
        in no order."""
        params = {
            "start": start and start.isoformat(),
            "end": end and end.isoformat(),
            "limit": limit,
        }
        given = {name: value for name, value in params.items() if value is not None}
        return self._get(f"/buckets/{bucket_id}/events", given)

    def _get(self, path: str, params: dict | None = None):
        response = self.session.get(self.api + path, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()


class Record:
    """What the watchers recorded between `start` and `end`, each one's events by what it
    records (above)."""

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
        """A record of events in hand (tests, replays)."""
        return cls(start, end, lambda bucket_type: events.get(bucket_type, []))

    @classmethod
    def fetch(
        cls,
        start: datetime,
        end: datetime,
        client: ActivityWatchClient,
        previous: Record | None = None,
    ) -> Record:
        """The record, from the server. With the `previous` one, an event still going on
        since then (a window you stay in) is in it too."""
        known = dict(previous.newest) if previous is not None else {}
        buckets: dict[str, dict] = {}

        def events(bucket_type: str) -> list[Event]:
            if not buckets:  buckets.update(client.buckets())

            found = []
            for bucket_id, info in buckets.items():
                if info.get("type") != bucket_type:  continue

                since = min(known.get(bucket_id, start), start)
                for event in map(Event.parse, client.events(bucket_id, since, end)):
                    found.append(event)
                    newest = record.newest.get(bucket_id, event.start)
                    record.newest[bucket_id] = max(event.start, newest)

                if bucket_id not in record.newest and bucket_id in known:
                    record.newest[bucket_id] = known[bucket_id]  # nothing new: the old one still holds
            return found

        record = cls(start, end, events)
        return record
