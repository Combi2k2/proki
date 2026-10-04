"""The weekly review (4DX #4, a cadence of accountability).

Once a week, in the shutdown ritual of the week's last workday (or the next
shutdown, if that one was missed), the user sees how the week went (deep work
per day against the daily goal, per goal group with its priority, the chain,
start-time consistency) and answers one question: what will you change next
week? Their answer is shown again at the next review.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from proki.legacy.core.backlog import minutes_text
from proki.legacy.core.shutdown import DAY_NAMES


def week_start(day: date) -> date:
    """The Monday of the week."""
    return day - timedelta(days=day.weekday())


def review_due(today: date, last_reviewed_week: date | None, workdays: tuple[str, ...]) -> bool:
    """On the week's last workday (once per week), or any day after a missed review."""
    this_week = week_start(today)
    if last_reviewed_week is not None and last_reviewed_week >= this_week:
        return False  # already reviewed this week
    last_workday = max((DAY_NAMES.index(d) for d in workdays), default=4)
    if today.weekday() >= last_workday:
        return True
    # missed last week's review (it was reviewed before, but not last week)
    return last_reviewed_week is not None and last_reviewed_week < this_week - timedelta(days=7)


@dataclass(frozen=True)
class WeekFacts:
    deep_by_day: dict[date, int]  # this week's days so far → deep minutes
    daily_goal: int  # the current base quota (minutes)
    by_group: list[tuple[str, str, int]]  # (goal group, priority, deep minutes in its sessions), most first
    chain: int
    consistency: str  # the tray's start-time line
    last_answer: str | None = None  # last review's "what will you change?"
    shallow: tuple[int, int] | None = None  # (shallow minutes, active minutes) on this week's workdays
    shallow_limit: float = 0.30
    top_deep: list[tuple[str, int]] = field(default_factory=list)  # deep sites/apps by minutes, most first (the vital few)
    tools: list[str] = field(default_factory=list)  # craftsman check: judged sites and their time now
    workdays: tuple[str, ...] = field(default=("mon", "tue", "wed", "thu", "fri"))


def review_text(f: WeekFacts) -> str:
    total = sum(f.deep_by_day.values())
    lines = [f"This week: {minutes_text(total)} of deep work."]
    days = " · ".join(f"{d:%a} {minutes_text(m)}" for d, m in sorted(f.deep_by_day.items()))
    if days:
        lines.append(days)
    workdays = [d for d in f.deep_by_day if DAY_NAMES[d.weekday()] in f.workdays]
    reached = sum(1 for d in workdays if f.deep_by_day[d] >= f.daily_goal)
    lines.append(f"Daily goal ({minutes_text(f.daily_goal)}) reached on {reached} of {len(workdays)} workdays.")
    if f.by_group:
        lines.append("By goal: " + " · ".join(f"{name} ({priority}) {minutes_text(m)}" for name, priority, m in f.by_group))
        neglected = [name for name, priority, m in f.by_group if priority == "high" and m == 0]
        if neglected:
            lines.append(f"No deep work on high-priority {', '.join(neglected)} this week.")
    if f.top_deep:
        lines.append("Most deep hours: " + " · ".join(f"{key} {minutes_text(m)}" for key, m in f.top_deep[:3]))
    if f.tools:
        lines.append("Tools you judged: " + "; ".join(f.tools))
    if f.shallow and f.shallow[1]:
        share = f.shallow[0] / f.shallow[1]
        lines.append(f"Shallow work: {share:.0%} of your time at the computer on workdays (limit {f.shallow_limit:.0%}).")
    lines.append(f"Chain: {f.chain} day{'s' if f.chain != 1 else ''} in a row. {f.consistency}")
    if f.last_answer:
        lines.append(f"Last week you said you'd change: “{f.last_answer}”")
    return "\n".join(lines)
