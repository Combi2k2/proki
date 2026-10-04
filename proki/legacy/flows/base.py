"""Flows: what proki does over time, each a sequence of actions (popups, alarms, records).

A `Flow` reacts to two clocks; both hooks do nothing unless a flow overrides them:

- `tick(ctx)`: every 15 seconds, with the recent timeline (sessions, morning,
  bedtime, reminders, budget, shutdown offer, ...);
- `poll(ctx)`: every 2 seconds, with what's in focus right now (capture, slips,
  hub-and-spoke, moving the shutdown ritual on, ...).

Flows can also be started by the user (tray items) or by another flow; those
entry points are ordinary methods of each flow.

`FlowContext` holds what flows need to decide: the moment, proki's state, who is active,
the session, what's in focus now, and the signals' values.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime

from proki.core.events import Category, Segment
from proki.core.rules import Rule
from proki.core.signals import Value


@dataclass
class FlowContext:
    now: datetime
    state: dict[str, Value] = field(default_factory=dict)  # proki's own values (in_session, ...)
    segments: list[Segment] = field(default_factory=list)  # tick: the recent timeline (prepared), oldest first
    latest: Segment | None = None  # what's in focus now (or away)
    active: bool = False  # at the computer now (recent input, not away)
    away_since: datetime | None = None  # the last input before the current absence (None while active)
    in_session: bool = False
    current: Segment | None = None  # poll: what's in focus right now (or away)
    category: Category | None = None  # poll: how `current` counts
    kind: str | None = None  # poll: what `current` is, its label (core/labels.py)
    values: Mapping[str, Value] | None = field(default=None, repr=False)  # the signals' values, by name (tick)


class Flow:
    name: str = "flow"

    def tick(self, ctx: FlowContext) -> None:
        """Every tick (15 s)."""

    def poll(self, ctx: FlowContext) -> None:
        """Every poll (2 s)."""


def config_rules(flow: str, *names: str) -> list[Rule]:
    """The rules of config.json a legacy flow decides by (`Rule.vote`), by name."""
    if missing := [name for name in names if name not in Rule.registry]:
        raise ValueError(f"config.json has no rule {', '.join(missing)} (the {flow} flow needs it)")
    return [Rule.registry[name] for name in names]
