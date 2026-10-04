"""The craftsman approach to tools (Deep Work, rule 3): keep a site or app only if it
clearly helps your core goals more than it costs.

It's about network tools and distractions, not work tools: sites and apps the
user counts as deep work are never asked about. The goal groups stand for the core goals. Whether a site/app serves a goal is learned
from data (core/association.py: its time share while that goal's tasks are active vs.
overall); a note taken there that became a task also counts as having helped. Its
week's time is "unserved" when it serves no goal. A rule
(time that served nothing, soft threshold) picks sites worth asking about; once per
weekly review the user is asked whether one of them substantially helps a goal. The
answer is remembered, and later reviews show how its time changed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from proki.legacy.core.events import Category, Segment
from proki.legacy.rules.base import Rule, RuleParams


@dataclass
class SiteWeek:
    key: str
    minutes: float = 0.0
    serves: set[int] = field(default_factory=set)  # goal groups it contributes to (learned)
    notes_to_tasks: int = 0  # notes taken there that became tasks
    category: Category | None = None  # how it counts (the latest seen)

    @property
    def unserved(self) -> float:
        """This week's minutes if it serves no goal and produced no tasks; else 0."""
        return 0.0 if self.serves or self.notes_to_tasks else self.minutes


def site_weeks(segments: list[Segment], contributes: dict[str, set[int]],
               notes: list[tuple[str, bool]]) -> dict[str, SiteWeek]:
    """`contributes`: window → goal groups (core/association.py); `notes`: (source key, became a task?)."""
    sites: dict[str, SiteWeek] = {}
    for s in segments:
        if s.away:
            continue
        site = sites.setdefault(s.key, SiteWeek(s.key, serves=set(contributes.get(s.key, ()))))
        site.minutes += s.duration.total_seconds() / 60
        site.category = s.category or site.category
    for key, became_task in notes:
        if became_task and key in sites:
            sites[key].notes_to_tasks += 1
    return sites


class WorthAsking(Rule[SiteWeek]):
    """Hours this week that served no goal: 2 h → 50% chance of asking, soft ±30 min."""

    def __init__(self, threshold_hours: float = 2.0, softness_hours: float = 0.5, rng=None):
        super().__init__(RuleParams(threshold=threshold_hours, softness=softness_hours), rng)

    def measure(self, site: SiteWeek) -> float:
        return site.unserved / 60

    def active(self, site: SiteWeek) -> bool:
        return site.category is not Category.DEEP  # work tools aren't what this is about


def pick(sites: dict[str, SiteWeek], judged: set[str], rule: WorthAsking) -> SiteWeek | None:
    """The site to ask about this week: most unserved time first, each sampled by the rule."""
    for site in sorted(sites.values(), key=lambda s: -s.unserved):
        if site.key not in judged and rule.decide(site):
            return site
    return None
