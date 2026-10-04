"""Turns raw ActivityWatch data into one ordered list of segments."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from proki.core.events import Segment
from proki.platforms import current as platform

BROWSER_APPS = platform().BROWSER_APPS


@dataclass(frozen=True)
class Tab:
    """The active browser tab, from the ActivityWatch web extension."""

    start: datetime
    end: datetime
    url: str
    title: str


Interval = tuple[datetime, datetime]


def build(windows: list[Segment], away: list[Interval], tabs: list[Tab]) -> list[Segment]:
    """Remove away time from window segments, attach browser tabs, add away segments."""
    segments = []
    for window in windows:
        for start, end in _subtract(window.start, window.end, away):
            piece = replace(window, start=start, end=end)
            if window.app in BROWSER_APPS:
                tab = _best_overlap(tabs, start, end)
                if tab:
                    piece = replace(piece, url=tab.url, title=tab.title or piece.title)
            segments.append(piece)
    segments += [Segment(start, end, "(away)", away=True) for start, end in away]
    return sorted(segments, key=lambda s: s.start)


def _subtract(start: datetime, end: datetime, intervals: list[Interval]) -> list[Interval]:
    pieces = [(start, end)]
    for cut_start, cut_end in intervals:
        remaining = []
        for s, e in pieces:
            if cut_end <= s or cut_start >= e:
                remaining.append((s, e))
                continue
            if s < cut_start:
                remaining.append((s, cut_start))
            if cut_end < e:
                remaining.append((cut_end, e))
        pieces = remaining
    return [(s, e) for s, e in pieces if e > s]


def _best_overlap(tabs: list[Tab], start: datetime, end: datetime) -> Tab | None:
    best, best_overlap = None, 0.0
    for tab in tabs:
        overlap = (min(end, tab.end) - max(start, tab.start)).total_seconds()
        if overlap > best_overlap:
            best, best_overlap = tab, overlap
    return best


InputEvent = tuple[datetime, datetime, float]  # start, end, input actions in it


def input_actions(data: dict) -> float:
    """aw-watcher-input counts both key-down and key-up: half the presses, plus clicks."""
    return data.get("presses", 0) / 2 + data.get("clicks", 0)


def attach_inputs(segments: list[Segment], inputs: list[InputEvent]) -> list[Segment]:
    """Each segment's input actions per minute (from aw-watcher-input); unchanged without input data."""
    if not inputs:
        return segments
    inputs = sorted(inputs)
    result = []
    for segment in segments:
        minutes = segment.duration.total_seconds() / 60
        if segment.away or minutes <= 0:
            result.append(segment)
            continue
        actions = 0.0
        for start, end, count in inputs:
            if start >= segment.end:
                break
            overlap = (min(end, segment.end) - max(start, segment.start)).total_seconds()
            length = (end - start).total_seconds()
            if overlap > 0 and length > 0:
                actions += count * overlap / length
        result.append(replace(segment, inputs=actions / minutes))
    return result


def _merged_inputs(a: Segment, b: Segment) -> float | None:
    if a.inputs is None or b.inputs is None:
        return a.inputs if b.inputs is None else b.inputs
    ma, mb = a.duration.total_seconds(), b.duration.total_seconds()
    return (a.inputs * ma + b.inputs * mb) / (ma + mb) if ma + mb else a.inputs


def merge(segments: list[Segment], max_gap: timedelta = timedelta(seconds=5)) -> list[Segment]:
    """Join back-to-back segments that look the same (e.g. a title that keeps
    changing inside an untracked app), allowing small gaps between them."""
    merged: list[Segment] = []
    for segment in segments:
        last = merged[-1] if merged else None
        if (
            last
            and (last.app, last.title, last.url, last.category, last.away)
            == (segment.app, segment.title, segment.url, segment.category, segment.away)
            and segment.start - last.end <= max_gap
        ):
            merged[-1] = replace(last, end=max(last.end, segment.end), inputs=_merged_inputs(last, segment))
        else:
            merged.append(segment)
    return merged
