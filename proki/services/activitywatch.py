"""ActivityWatch, the tracker proki is built on (imported as `aw`): its REST API
(http://host:port/api/0, `is_up`: whether it answers), what its watchers record, and how to
look up a moment in it. proki runs the server and watchers itself (services/supervisor.py,
`MODULES`), so ActivityWatch's own tray app isn't needed.

Watchers store events in typed buckets as (timestamp, duration, data), with identical
neighbours merged. The bucket types proki reads:

    WINDOW   the window watcher      {"app", "title"} (on macOS, also "url" in a browser)
    WEBTAB   the browser extension   {"url", "title"}
    INPUT    the input watcher       {"presses" (down and up), "clicks", "deltaX", "deltaY",
                                      "scrollX", "scrollY"}, an event every ~5 s
    AFK      the AFK watcher         {"status": "afk" / "not-afk"}

Watchers report every few seconds and send their reports in batches: neighbouring events
leave tiny gaps, and the newest event ends a little before now. So an event's value holds
until the next event starts, for at most `HOLD` after its end. Longer gaps are unknown.

Only core/primitives/ reads a `Record`. It keeps what it needs as its own tables.
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

# the programs proki runs (services/supervisor.py): the server first, then the watchers
# that record the buckets above (WEBTAB comes from the browser extension)
MODULES = [
    "aw-server",
    "aw-watcher-window",    # WINDOW
    "aw-watcher-afk",       # AFK
    "aw-watcher-input",     # INPUT: counts of key presses and clicks (never which keys)
]

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

        for i in range(len(self.events) - 1):  # a value holds until the next event starts, at most
            nxt = self.events[i + 1].start
            if self._untils[i] > nxt:  self._untils[i] = nxt

    def covering(self, t: datetime) -> Event | None:
        """The event whose value holds at t (start < t <= until)."""
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
    """The server at `host`:`port` (the config's [activitywatch])."""

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
    def fetch(
        cls,
        start: datetime,
        end: datetime,
        client: ActivityWatchClient,
        previous: Record | None = None,
    ) -> Record:
        """From the server, each bucket type when first asked for.

        Each bucket is read from where its newest event known from the `previous` fetch
        starts, not just from `start`: that event may still be running (a window you stay
        in, a tab you stay on), and the server only returns events that start in the range.
        Only those times are kept from `previous`, so it can be let go."""
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
