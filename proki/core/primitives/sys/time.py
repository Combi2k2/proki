"""The time of the cycle:

    daytime     minutes since local midnight (0 to 1440)
    time        minutes since 1970 (never wraps: `time - last_suggested`)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from proki.core.primitives.base import Primitive
from proki.core.primitives.sys.base import Moment


class Daytime(Moment, Primitive):
    _typed = "number"
    desc   = "the time of day, in minutes since midnight (0 to 1440)"

    def at(self, t: datetime) -> Any:
        local = t.astimezone()
        return local.hour * 60 + local.minute + local.second / 60


class Time(Moment, Primitive):
    _typed = "time"
    desc   = "now, in minutes since 1970"

    def at(self, t: datetime) -> Any:
        return t.timestamp() / 60
