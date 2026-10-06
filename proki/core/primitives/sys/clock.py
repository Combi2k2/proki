"""`clock`: minutes since local midnight (0 to 1440)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from proki.core.primitives.base import Primitive
from proki.core.primitives.sys.base import Moment


class Clock(Moment, Primitive):
    def at(self, t: datetime) -> Any:
        local = t.astimezone()
        return local.hour * 60 + local.minute + local.second / 60
