"""What a window's label (core/labels.py) means for the timeline.

- **Watching is not away.** No input while a video site or a call is in focus
  means watching or listening, not being away: the away time right after it
  becomes time on that site (with its category), up to `WATCH_LIMIT` (after that,
  e.g. a video left playing, it's away again).
- **Tools take their context.** A quick search or an AI-assistant question counts
  as part of what the user is working on: tool time takes the category of the
  work just before it. Switching to it still counts as switching.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from typing import Callable

from proki.core.events import Segment

WATCH_KINDS = {"video_streaming", "video_calls"}
TOOL_KINDS = {"search_engine", "ai_assistant"}
WATCH_LIMIT = timedelta(hours=3)
TOOL_CONTEXT = timedelta(minutes=10)  # the work before must have been this recent to lend its category

KindOf = Callable[[Segment], "str | None"]


def watching_is_not_away(segments: list[Segment], kind_of: KindOf, limit: timedelta = WATCH_LIMIT) -> list[Segment]:
    result: list[Segment] = []
    for segment in sorted(segments, key=lambda s: s.start):
        previous = result[-1] if result else None
        if (segment.away and previous is not None and not previous.away
                and segment.start - previous.end <= timedelta(minutes=1) and kind_of(previous) in WATCH_KINDS):
            watched_until = min(segment.end, segment.start + limit)
            result.append(replace(previous, start=segment.start, end=watched_until))
            if watched_until < segment.end:
                result.append(replace(segment, start=watched_until))
            continue
        result.append(segment)
    return result


def tools_take_context(segments: list[Segment], kind_of: KindOf, reach: timedelta = TOOL_CONTEXT) -> list[Segment]:
    result: list[Segment] = []
    context: Segment | None = None  # the last non-tool work
    for segment in sorted(segments, key=lambda s: s.start):
        if segment.away:
            result.append(segment)
            continue
        if kind_of(segment) in TOOL_KINDS:
            if context is not None and segment.start - context.end <= reach and context.category is not None:
                segment = replace(segment, category=context.category)
            result.append(segment)
            continue
        context = segment
        result.append(segment)
    return result
