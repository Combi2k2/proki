"""The day of the cycle, local:

    weekday     0 Monday to 6 Sunday
    dd          the day of the month, 1 to 31
    mm          the month, 1 January to 12 December
    yy          the year, all of it: 2026
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from proki.core.primitives.base import Primitive
from proki.core.primitives.sys.base import Moment


class Weekday(Moment, Primitive):
    _typed = "integer"
    desc   = "the day of the week, 0 Monday to 6 Sunday"

    def at(self, t: datetime) -> Any:
        return t.astimezone().weekday()


class Dd(Moment, Primitive):
    _typed = "integer"
    desc   = "the day of the month, 1 to 31"

    def at(self, t: datetime) -> Any:
        return t.astimezone().day


class Mm(Moment, Primitive):
    _typed = "integer"
    desc   = "the month, 1 January to 12 December"

    def at(self, t: datetime) -> Any:
        return t.astimezone().month


class Yy(Moment, Primitive):
    _typed = "integer"
    desc   = "the year, all of it: 2026"

    def at(self, t: datetime) -> Any:
        return t.astimezone().year
