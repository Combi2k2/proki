"""Scoreboard text for the tray menu (plain functions, no Qt)."""

from __future__ import annotations

from datetime import datetime

from proki.legacy.metrics.history import SessionSummary
from proki.legacy.core.schedule import Block
from proki.legacy.metrics.day import DayScore

ACTIVITY_ORDER = ["deep", "offline", "shallow", "distraction", "neutral", "unclassified", "untracked", "away"]


def duration(minutes: int) -> str:
    return f"{minutes // 60}h {minutes % 60:02d}m" if minutes >= 60 else f"{minutes}m"


def scoreboard_lines(day: DayScore, threshold: float) -> list[str]:
    bar_len = 10
    filled = int(day.goal_progress * bar_len)  # full only once the goal is actually reached
    activities = " · ".join(
        f"{name.capitalize()} {duration(day.minutes_by_activity[name])}"
        for name in ACTIVITY_ORDER
        if day.minutes_by_activity.get(name)
    )
    return [
        f"Today: {day.deep_minutes} min of deep work (focus ≥ {threshold})",
        f"Longest streak {day.longest_streak} min · current streak {day.current_streak} min",
        f"Goal {day.deep_minutes}/{day.goal_minutes} min  {'▓' * filled}{'░' * (bar_len - filled)}  {day.goal_progress:.0%}",
        f"Time on: {activities}" if activities else "Time on: nothing recorded yet",
    ]


def rhythm_lines(block: Block | None, now: datetime, chain: int, sessions: list[SessionSummary]) -> list[str]:
    lines = []
    if block is None:
        lines.append("No deep-work block today")
    else:
        span = f"{block.start.astimezone():%H:%M}–{block.end.astimezone():%H:%M}"
        if now < block.start:
            lines.append(f"Deep-work block today: {span}")
        elif now < block.end:
            lines.append(f"Deep-work block now: {span}")
        else:
            lines.append(f"Deep-work block today was {span}")
    lines.append(f"Chain: {chain} day{'s' if chain != 1 else ''} in a row")
    if sessions:
        deep = sum(s.deep_minutes for s in sessions)
        lines.append(f"Sessions today: {len(sessions)} · {deep} min deep")
    return lines


def task_lines(group, task, done_today: int) -> list[str]:
    """What's been done today (never what's left) and what's next."""
    lines = [f"Done today: {done_today} task{'s' if done_today != 1 else ''}"]
    if task is not None:
        where = f" · {group.name}" if group else ""
        lines.append(f"Next: {task.title} (~{duration(task.estimate)}){where}")
    return lines


def sleep_lines(off: datetime | None, up: datetime | None) -> list[str]:
    """Last night's last activity and this morning's first."""
    if off is None and up is None:
        return []
    fmt = lambda t: f"{t.astimezone():%H:%M}" if t else "–"
    return [f"Last night: off at {fmt(off)} · up at {fmt(up)}"]


def consistency_lines(result) -> list[str]:
    """How consistently sessions start at the usual time (core/consistency.py)."""
    if result.usual is None:
        return ["Start time: not enough days yet"]
    return [f"Start time: usually {result.usual:%H:%M} · on time {result.consistent_days} of the last {result.days} days"]


def budget_lines(today, limit: float) -> list[str]:
    """The shallow-work budget (core/budget.py `ShallowShare`)."""
    if not today.active:
        return []
    return [f"Shallow today: {duration(today.shallow)} · {today.share:.0%} (limit {limit:.0%})"]
