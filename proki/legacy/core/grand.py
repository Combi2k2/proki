"""The grand gesture (Deep Work, rule 1): a big, unusual investment in one deep task,
like a day somewhere new, which makes the task feel important.

In proki: one long session (half or full day) on one thing, with relaxed rules: the
wrap-up comes only at the end, and real breaks are allowed (a longer away alarm and
auto-end). Afterwards the user notes what they got done.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import timedelta

from proki.legacy.core.session import SessionParams


@dataclass(frozen=True)
class GrandParams:
    lengths: tuple[tuple[str, int], ...] = (("Half day (4 h)", 4), ("Full day (8 h)", 8))
    away_alarm_after: timedelta = timedelta(minutes=20)  # breaks are part of a long day
    away_end_after: timedelta = timedelta(minutes=45)


def grand_session(base: SessionParams, hours: int, params: GrandParams = GrandParams()) -> SessionParams:
    """The session rules for a grand gesture of `hours`."""
    return replace(base, wrap_up=timedelta(hours=hours), away_alarm_after=params.away_alarm_after,
                   away_end_after=params.away_end_after)
