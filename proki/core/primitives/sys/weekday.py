"""`weekday`: 0 Monday to 6 Sunday, local."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from proki.core.primitives.base import Primitive
from proki.core.primitives.sys.base import Moment


class Weekday(Moment, Primitive):
    def at(self, t: datetime) -> Any:
        return t.astimezone().weekday()
