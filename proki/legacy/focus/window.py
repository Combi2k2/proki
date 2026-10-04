"""Cuts one window [end - horizon, end] out of the timeline. No scoring here."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from proki.core.events import Category, Segment


@dataclass(frozen=True)
class Stretch:
    """Continuous time on one item (app or website), clipped to the window."""

    item: str
    category: Category | None
    seconds: float
    inputs: float | None = None  # input actions per minute (time-weighted); None = no input data


@dataclass(frozen=True)
class Switch:
    """Moving from one item to another inside the window."""

    at: datetime
    to_item: str
    to_category: Category | None
    since_last_use: timedelta | None  # how long ago `to_item` was last in focus; None if never


@dataclass(frozen=True)
class Window:
    end: datetime
    horizon: timedelta
    stretches: list[Stretch]
    switches: list[Switch]

    @property
    def active_seconds(self) -> float:
        return sum(s.seconds for s in self.stretches)


def slice_window(segments: list[Segment], end: datetime, horizon: timedelta) -> Window:
    """Stretches and switches in [end - horizon, end].

    `segments` should reach back before the window (ideally 2 × horizon), so
    `since_last_use` is known for switches early in the window. Away time is
    left out; coming back from being away is not a switch. A title change on
    the same item (a new page on the same site) is not a switch either.
    """
    start = end - horizon
    stretches: list[Stretch] = []
    switches: list[Switch] = []
    last_use: dict[str, datetime] = {}
    previous: str | None = None

    for segment in sorted(segments, key=lambda s: s.start):
        if segment.start >= end:
            break
        if segment.away:
            previous = None
            continue
        item = segment.key
        continuing = item == previous
        if previous is not None and not continuing and segment.start >= start:
            seen = last_use.get(item)
            switches.append(
                Switch(segment.start, item, segment.category, segment.start - seen if seen else None)
            )
        previous = item
        last_use[item] = min(segment.end, end)

        seconds = (min(segment.end, end) - max(segment.start, start)).total_seconds()
        if seconds <= 0:
            continue
        if continuing and stretches and stretches[-1].item == item:
            last = stretches[-1]
            inputs = last.inputs if segment.inputs is None else segment.inputs if last.inputs is None else (
                (last.inputs * last.seconds + segment.inputs * seconds) / (last.seconds + seconds))
            stretches[-1] = Stretch(item, segment.category, last.seconds + seconds, inputs)
        else:
            stretches.append(Stretch(item, segment.category, seconds, segment.inputs))

    return Window(end, horizon, stretches, switches)
