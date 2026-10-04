from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from urllib.parse import urlsplit


class Category(Enum):
    """What kind of work an activity is, in Deep Work terms."""

    DEEP = "deep"  # cognitively demanding, creates value, hard to replicate
    SHALLOW = "shallow"  # logistics and communication, easy to replicate
    DISTRACTION = "distraction"  # entertainment unrelated to work
    NEUTRAL = "neutral"  # system tools that are neither


@dataclass(frozen=True)
class Segment:
    """A stretch of time with one thing in focus, or with the user away."""

    start: datetime
    end: datetime
    app: str
    title: str = ""
    url: str | None = None
    category: Category | None = None  # None = not classified yet
    away: bool = False
    inputs: float | None = None  # input actions per minute (keys + clicks); None = no input data

    @property
    def duration(self) -> timedelta:
        return self.end - self.start

    @property
    def key(self) -> str:
        """What gets classified: the website's domain in a browser, otherwise the app.

        The same site counts the same in any browser, and every page on it
        shares one answer.
        """
        if self.url:
            parts = urlsplit(self.url)
            if parts.scheme in ("http", "https") and parts.hostname:
                return parts.hostname.removeprefix("www.")
            return f"{self.app} · {parts.scheme or 'page'}"  # browser-internal page
        return self.app


class Level(Enum):
    """How strongly to interrupt the user."""

    QUIET = "quiet"  # tray badge only
    NOTIFY = "notify"  # system notification
    POPUP = "popup"  # floating panel asking for a response


@dataclass(frozen=True)
class Finding:
    """Something a rule noticed that may be worth telling the user."""

    rule: str
    message: str
    level: Level = Level.NOTIFY
