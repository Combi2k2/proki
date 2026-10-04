"""The task backlog: the user's incoming work, grouped by goal.

Tasks keep coming in (with a deadline and the user's own estimate) and the list
grows; nothing is "planned for a day". proki checks each task is atomic (specific,
and doable in one 50-minute session; otherwise the user breaks it down) and, for
each focus session, suggests one goal group to work on so the user doesn't switch
between goals. Group choice = urgency (remaining work ÷ time to the nearest
deadline) × importance (the group's priority).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

SESSION_MINUTES = 50  # the longest a single task may take: one deep-work session
SPECIFIC_ENOUGH = 0.5
MISMATCH_RATIO = 2.5  # openjev's estimate this many times off the user's → ask once to double-check
PRIORITY_WEIGHT = {"high": 2.0, "normal": 1.0, "low": 0.5}
NO_DEADLINE_HOURS = 24 * 30  # a group without deadlines is treated as due in a month


@dataclass(frozen=True)
class Assessment:
    """openjev's view of a task."""

    kind: str | None  # 'deep' or 'shallow'
    minutes: int | None  # its size estimate; None = can't be told
    specific: float  # 0..1: concrete scope and a clear end point?
    offline: float | None = None  # 0..1: can it be done away from a computer?


@dataclass(frozen=True)
class Group:
    id: int
    name: str
    priority: str = "normal"  # 'high', 'normal' or 'low'


@dataclass(frozen=True)
class Task:
    id: int
    group_id: int | None
    parent_id: int | None  # set for the steps of a broken-down task
    title: str
    description: str
    deadline: date | None
    estimate: int  # minutes, the user's own estimate
    kind: str | None = None  # openjev: 'deep' or 'shallow'
    status: str = "open"  # 'open', 'done' or 'dropped'
    position: int = 0
    offline: bool | None = None  # the user's answer: done away from the computer? None = not asked
    jev_offline: float | None = None  # openjev: how likely it can be done offline


def breakdown_reason(estimate: int, assessment: Assessment | None) -> str | None:
    """Why a task should be broken down: 'too_long', 'vague', or None if it's atomic.

    The user's estimate decides the length; openjev only decides vagueness.
    """
    if estimate > SESSION_MINUTES:
        return "too_long"
    if assessment is not None and (assessment.specific < SPECIFIC_ENOUGH or assessment.minutes is None):
        return "vague"
    return None


def estimate_mismatch(estimate: int, assessment: Assessment | None) -> bool:
    """openjev's size estimate is far from the user's (either way)."""
    if assessment is None or assessment.minutes is None or estimate <= 0:
        return False
    ratio = assessment.minutes / estimate
    return ratio >= MISMATCH_RATIO or ratio <= 1 / MISMATCH_RATIO


OFFLINE_LIKELY = 0.5  # openjev at least this sure → ask the user whether they'll do it offline
OFFLINE_GRACE = timedelta(minutes=30)  # away this much longer than the estimate → normal away rules again


def ask_if_offline(task: Task) -> bool:
    """Ask at hand-over whether the task will be done away from the computer."""
    return task.offline is None and (task.jev_offline or 0) >= OFFLINE_LIKELY


def away_is_offline_work(task: Task | None, away_since: datetime, now: datetime) -> bool:
    """Being away counts as working on an offline task, up to its estimate plus a grace period."""
    return bool(task and task.offline) and now - away_since <= timedelta(minutes=task.estimate) + OFFLINE_GRACE


def workable(tasks: list[Task]) -> list[Task]:
    """Open tasks that can be worked on: not the parent of open steps."""
    has_open_steps = {t.parent_id for t in tasks if t.status == "open" and t.parent_id is not None}
    return [t for t in tasks if t.status == "open" and t.id not in has_open_steps]


def urgency(tasks: list[Task], now: datetime) -> float:
    """Remaining estimated hours ÷ hours until the nearest deadline (higher = more urgent)."""
    open_tasks = workable(tasks)
    if not open_tasks:
        return 0.0
    remaining = sum(t.estimate for t in open_tasks) / 60
    deadlines = [t.deadline for t in open_tasks if t.deadline]
    if deadlines:
        due = datetime.combine(min(deadlines), time(23, 59), now.astimezone().tzinfo)
        hours = max((due - now).total_seconds() / 3600, 1.0)  # overdue counts as due within the hour
    else:
        hours = NO_DEADLINE_HOURS
    return remaining / hours


def pick_group(groups: list[Group], tasks: list[Task], now: datetime, exclude: set[int] = frozenset()) -> Group | None:
    """The group to work on this session: urgency × priority, among groups with workable tasks."""
    best, best_score = None, 0.0
    for group in groups:
        if group.id in exclude:
            continue
        score = urgency([t for t in tasks if t.group_id == group.id], now) * PRIORITY_WEIGHT.get(group.priority, 1.0)
        if score > best_score:
            best, best_score = group, score
    return best


def next_task(tasks: list[Task], group_id: int | None) -> Task | None:
    """The group's next task: earliest deadline first, then the order they were added."""
    candidates = [t for t in workable(tasks) if t.group_id == group_id]
    candidates.sort(key=lambda t: (t.deadline or date.max, t.position, t.id))
    return candidates[0] if candidates else None


def due_text(deadline: date | None, today: date) -> str:
    if deadline is None:
        return "no deadline"
    days = (deadline - today).days
    if days < 0:
        return f"overdue by {-days} day{'s' if days != -1 else ''}"
    if days == 0:
        return "due today"
    if days == 1:
        return "due tomorrow"
    return f"due {deadline:%b %d}" if days > 6 else f"due {deadline:%A}"


def minutes_text(minutes: int) -> str:
    return f"{minutes // 60}h {minutes % 60:02d}m" if minutes >= 60 else f"{minutes}m"


def default_deadline(today: date) -> date:
    return today + timedelta(days=7)
