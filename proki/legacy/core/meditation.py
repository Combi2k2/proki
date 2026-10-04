"""Productive meditation (Deep Work, rule 2): a walk spent thinking through one
well-defined problem.

After a good session proki sometimes suggests one (more likely the more deep work it had) (and the tray can start one any
time). The walk is a focus session on an offline "task" (the problem): being
away is the work, and it counts as deep minutes, up to its length (+ the usual
grace). Back at the computer, the user writes down what they figured out.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from proki.legacy.core.backlog import Task
from proki.legacy.rules.walk import SuggestWalk

WALK_TASK_ID = -1  # not in the backlog


@dataclass(frozen=True)
class MeditationParams:
    threshold: float = 35  # deep minutes in the session → 50% chance of suggesting a walk
    softness: float = 8  # 25 min → 22%, 50 min → 87%
    min_deep_minutes: int = 25  # the rule's range: never after a session with less
    lengths: tuple[int, ...] = (15, 30, 45)  # minutes to choose from


def should_suggest(session_deep_minutes: int, params: MeditationParams, rng: random.Random) -> bool:
    return SuggestWalk(params, rng).decide(session_deep_minutes)


def walk_task(problem: str, minutes: int) -> Task:
    """The walk as an offline task, so the session treats time away as the work."""
    return Task(WALK_TASK_ID, None, None, problem, "", None, minutes, kind="deep", offline=True)


def is_walk(task: Task | None) -> bool:
    return task is not None and task.id == WALK_TASK_ID
