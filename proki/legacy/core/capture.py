"""Capturing what's worth keeping from shallow work and distractions.

Outside focus sessions proki doesn't push for focus (the daily quota does that).
Instead, when the user is on something shallow (email, chat) or has been in
distraction (feeds, video) for a while, it asks whether there's anything worth
noting. A note that is a to-do becomes a task, linked to the tab or window it
came from; when the user hasn't gone back there for a while, proki asks whether
the task is finished (and offers to close the tab or window).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from proki.legacy.core.events import Category, Segment
from proki.legacy.rules.base import RuleParams
from proki.legacy.rules.capture import TimeOnIt


@dataclass(frozen=True)
class CaptureParams:
    shallow_after: timedelta = timedelta(seconds=15)  # on a shallow app/site this long (per visit) → ask
    distraction_after: timedelta = timedelta(minutes=5)  # in distraction this long → ask
    distraction_gap: timedelta = timedelta(minutes=1)  # out of distraction this long ends the stretch
    follow_up_after: timedelta = timedelta(minutes=15)  # a task's tab/window not visited this long → "finished?"


@dataclass(frozen=True)
class Source:
    """Where a note or task came from: a browser tab (url) or an app window (app + title)."""

    app: str
    title: str
    url: str | None
    key: str  # website domain or app, as classified
    category: Category | None = None

    @classmethod
    def of(cls, segment: Segment, category: Category | None = None) -> Source:
        return cls(segment.app, segment.title, segment.url, segment.key, category)

    def matches(self, segment: Segment) -> bool:
        """The user is on this tab / window right now."""
        if self.url:
            return segment.url == self.url
        return segment.app == self.app and segment.title == self.title


class CaptureWatch:
    """Decides when to ask "anything worth noting?" (outside sessions).

    Two hard rules (the user's exact lines): 15 s on a shallow visit; 5 min in a
    distraction stretch. Each asks once per visit / stretch.
    """

    def __init__(self, params: CaptureParams = CaptureParams()):
        self.params = params
        self.shallow_rule = TimeOnIt(RuleParams(threshold=params.shallow_after.total_seconds()))
        self.distraction_rule = TimeOnIt(RuleParams(threshold=params.distraction_after.total_seconds()))
        self.visit_key: str | None = None  # the shallow visit: one app/site in focus without a switch
        self.visit_since: datetime | None = None
        self.visit_asked = False
        self.stretch_since: datetime | None = None  # the distraction stretch (any distraction items)
        self.last_distraction: datetime | None = None
        self.stretch_asked = False

    def step(self, now: datetime, segment: Segment | None, category: Category | None, in_session: bool) -> Source | None:
        """Call every few seconds with what's in focus; returns the source to ask about, or None."""
        if in_session or segment is None or segment.away:
            self.visit_key = None
            if segment is None or segment.away:
                self.stretch_since = None  # stepping away ends the stretch
            return None
        if segment.key != self.visit_key:
            self.visit_key, self.visit_since, self.visit_asked = segment.key, now, False

        if category is Category.DISTRACTION:
            if self.stretch_since is None:
                self.stretch_since, self.stretch_asked = now, False
            self.last_distraction = now
            if not self.stretch_asked and self.distraction_rule.decide(now - self.stretch_since):
                self.stretch_asked = True
                return Source.of(segment, category)
        elif self.last_distraction is not None and now - self.last_distraction >= self.params.distraction_gap:
            self.stretch_since = None

        if category is Category.SHALLOW and not self.visit_asked and self.shallow_rule.decide(now - self.visit_since):
            self.visit_asked = True
            return Source.of(segment, category)
        return None


class FollowUps:
    """Tasks that came from a tab/window: "finished?" once the user hasn't been back for a while."""

    def __init__(self, params: CaptureParams = CaptureParams()):
        self.params = params
        self.last_seen: dict[int, datetime] = {}  # task id → last time its tab/window was in focus

    def step(self, now: datetime, segment: Segment | None, tasks: list[tuple[int, Source]]) -> int | None:
        """`tasks`: open tasks with a source. Returns a task id to ask about, or None."""
        due = None
        for task_id, source in tasks:
            seen = self.last_seen.setdefault(task_id, now)  # new (or after a restart): from now
            if segment is not None and not segment.away and source.matches(segment):
                self.last_seen[task_id] = now
            elif due is None and now - seen >= self.params.follow_up_after:
                due = task_id
        return due

    def not_yet(self, task_id: int, now: datetime) -> None:
        """Ask again after another while."""
        self.last_seen[task_id] = now
