"""Decides when to ask whether to track an app.

Called every few seconds with what is in focus. An app not on the track list that has
been in focus for `ask_track_after` gets a question: whether to track it, and as what
(picking a category tracks it and says how it counts, in one answer). Its name is only
shown, never stored or sent, unless the user says yes ("Don't track" keeps just a hash).

What a tracked app or page *is* (its label, and so its default category) is asked by
core/labeling.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from proki import platforms
from proki.legacy.config import Config
from proki.legacy.core.events import Category, Segment
from proki.legacy.core.store import Store

ASK_LATER = timedelta(hours=2)


@dataclass(frozen=True)
class Question:
    kind: str  # "track"
    key: str  # the app's name


class ClassificationLoop:
    def __init__(self, config: Config, store: Store):
        self.config = config
        self.store = store
        self.ignore_apps = set(platforms.current().SYSTEM_APPS) | set(config.ignore_apps)  # never worth a question
        self.ask_track_after = timedelta(seconds=config.ask_track_after_seconds)
        self.current: Question | None = None
        self.since: datetime | None = None
        self.later: dict[Question, datetime] = {}

    def observe(self, segment: Segment | None, now: datetime) -> Question | None:
        """Update with what is in focus now; return a question for the user, or None."""
        question = self._question_for(segment)
        if question != self.current:
            self.current, self.since = question, now
        if question is None or self.since is None:
            return None
        if now - self.since < self.ask_track_after or self.later.get(question, now) > now:
            return None
        return question

    def answered(self, question: Question, response: str, now: datetime) -> None:
        """Responses: 'later', 'never', or a category value (track it, counting as that)."""
        if response == "later":
            self.later[question] = now + ASK_LATER
        elif response == "never":
            self.store.set_tracking(question.key, False, now)
        else:
            self.store.set_tracking(question.key, True, now)
            self.config.add_tracked_apps([question.key])
            self.store.set_category(question.key, Category(response), "user", now)

    def _question_for(self, segment: Segment | None) -> Question | None:
        if segment is None or segment.away or not segment.app or segment.app in self.ignore_apps:
            return None
        if self.config.is_tracked(segment.app, segment.title, segment.url):
            return None
        if self.config.has_track_rule(segment.app):
            return None  # tracked only for some titles/URLs; the user chose that
        if self.store.get_tracking(segment.app) == "never":
            return None
        return Question("track", segment.app)
