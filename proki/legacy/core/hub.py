"""Hub-and-spoke (Deep Work, rule 1): collaboration (email, chat, calls) happens
outside deep sessions. During a focus session, being on a contact site or app for
`after` (a hard rule, like the capture questions) → a reminder, once per visit.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from proki.core.events import Segment
from proki.legacy.rules.base import RuleParams
from proki.legacy.rules.capture import TimeOnIt

CONTACT_KINDS = {"email", "team_chat", "video_calls"}


class HubWatch:
    def __init__(self, after: timedelta = timedelta(seconds=15)):
        self.rule = TimeOnIt(RuleParams(threshold=after.total_seconds()))
        self.visit: tuple[str, datetime] | None = None  # (key, since)
        self.reminded = False

    def step(self, now: datetime, segment: Segment | None, kind: str | None, in_session: bool) -> bool:
        """True once per visit to a contact site/app during a session, after `after` on it."""
        if not in_session or segment is None or segment.away or kind not in CONTACT_KINDS:
            self.visit, self.reminded = None, False
            return False
        if self.visit is None or self.visit[0] != segment.key:
            self.visit, self.reminded = (segment.key, now), False
        if not self.reminded and self.rule.decide(now - self.visit[1]):
            self.reminded = True
            return True
        return False
