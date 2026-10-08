"""The craftsman check (the legacy craftsman flow's) (core/craftsman.py): once per weekly review,
"does this site substantially help any of your goals?", and a 30-day test after a no."""

from __future__ import annotations

from datetime import datetime, timezone

from proki.core.ui import Ui
from proki.legacy.core.craftsman import SiteWeek
from proki.legacy.core.store import Store
from proki.legacy.core.backlog import Group, minutes_text
from proki.programs.base import Ritual, program


class Craftsman(Ritual):
    def __init__(self, store: Store):
        super().__init__("craftsman")
        self.store = store

    def ask(self, site: SiteWeek, groups: list[Group]) -> None:
        goals = sorted(groups, key=lambda g: {"high": 0, "normal": 1, "low": 2}.get(g.priority, 1))[:4]
        Ui.ask(
            f"{site.key} took {minutes_text(int(site.minutes))} this week, and {minutes_text(int(site.unserved))} "
            "of it served none of your goals. Does it substantially help any of them?",
            lambda a: self._answer(site, a),
            [(g.name, f"goal:{g.id}") for g in goals] + [("A little", "little"), ("No", "no")],
        )

    def _answer(self, site: SiteWeek, answer: str) -> None:
        now = datetime.now(timezone.utc)
        if answer.startswith("goal:"):
            self.store.set_verdict(site.key, "serves", int(answer.removeprefix("goal:")), site.minutes, now)
            return
        self.store.set_verdict(site.key, answer, None, site.minutes, now)
        if answer == "no" and not self.store.experiments(("running",)):
            Ui.ask(f"Then it costs more than it gives. Try 30 days without {site.key}?",
                           lambda a: program("experiment").start_for(site.key) if a == "yes" else None,
                           [("Start the 30-day test", "yes"), ("Not now", "no")])



def verdict_lines(sites: dict[str, SiteWeek], verdicts: dict[str, tuple[str, int | None, float]],
                  names: dict[int, str]) -> list[str]:
    """For the weekly review: how the time on judged sites changed."""
    lines = []
    for key, (verdict, group, then) in sorted(verdicts.items(), key=lambda kv: -kv[1][2]):
        now = sites[key].minutes if key in sites else 0
        judged = {"serves": f"serves {names.get(group, 'a goal')}", "little": "helps a little", "no": "doesn't help"}[verdict]
        lines.append(f"{key} ({judged}): {minutes_text(int(now))} this week ({minutes_text(int(then))} when you judged it)")
    return lines[:3]
