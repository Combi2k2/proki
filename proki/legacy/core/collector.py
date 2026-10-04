"""Reads activity from the local ActivityWatch server's REST API."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import requests

from proki.legacy.config import Config
from proki.core.events import Segment
from proki.legacy.core.timeline import BROWSER_APPS, Tab, attach_inputs, build, input_actions


class Collector:
    def __init__(self, config: Config):
        self._api = f"http://{config.aw_host}:{config.aw_port}/api/0"

    def timeline(self, lookback: timedelta) -> list[Segment]:
        """Segments from the last `lookback`, oldest first, with away time cut out.

        Names are not masked yet: run `categories.prepare` before using them.
        """
        now = datetime.now(timezone.utc)
        return self.between(now - lookback, now)

    def between(self, start: datetime, end: datetime) -> list[Segment]:
        """Like `timeline`, for any time range (e.g. a past day)."""
        buckets = self._get("/buckets/")
        if not any(info.get("type") == "currentwindow" for info in buckets.values()):
            raise RuntimeError("No ActivityWatch window bucket found. Is ActivityWatch running?")

        def events(bucket_type: str):
            for bucket_id, info in buckets.items():
                if info.get("type") != bucket_type:
                    continue
                params = {"start": start.isoformat(), "end": end.isoformat()}
                for e in self._get(f"/buckets/{bucket_id}/events", params):
                    begins = datetime.fromisoformat(e["timestamp"])
                    yield begins, begins + timedelta(seconds=e["duration"]), e["data"]

        windows = [
            Segment(s, e, data.get("app", ""), data.get("title", ""))
            for s, e, data in events("currentwindow")
        ]
        away = [(s, e) for s, e, data in events("afkstatus") if data.get("status") == "afk"]
        tabs = [
            Tab(s, e, data.get("url", ""), data.get("title", ""))
            for s, e, data in events("web.tab.current")
        ]
        inputs = [(s, e, input_actions(data)) for s, e, data in events("os.hid.input")]
        return attach_inputs(build(windows, away, tabs), inputs)

    def current(self) -> Segment | None:
        """What is in focus right now (cheap: only the latest event per bucket).

        Returns an `away` segment when the user is away, None if nothing is known.
        """
        now = datetime.now(timezone.utc)
        buckets = self._get("/buckets/")

        def latest(bucket_type: str) -> dict | None:
            newest = None
            for bucket_id, info in buckets.items():
                if info.get("type") == bucket_type:
                    for e in self._get(f"/buckets/{bucket_id}/events", {"limit": 1}):
                        if newest is None or e["timestamp"] > newest["timestamp"]:
                            newest = e
            return newest

        afk = latest("afkstatus")
        if afk and afk["data"].get("status") == "afk":
            left = datetime.fromisoformat(afk["timestamp"])  # the last input, not when it was noticed
            return Segment(left, now, "(away)", away=True)
        window = latest("currentwindow")
        if window is None:
            return None
        
        url = None
        app = window["data"].get("app", "")
        title = window["data"].get("title", "")
        
        if app in BROWSER_APPS:
            # The extension reports every tab change right away but only updates a
            # tab you stay on now and then, so its latest event is the current tab
            # however old its last update is.
            tab = latest("web.tab.current")
            if tab:
                url, title = tab["data"].get("url") or None, tab["data"].get("title") or title
        return Segment(now, now, app, title, url)

    def _get(self, path: str, params: dict | None = None):
        response = requests.get(self._api + path, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
