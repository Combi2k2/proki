"""`time`: minutes since 1970 (never wraps: `time - last_suggested`)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from proki.core.primitives.base import Primitive
from proki.core.primitives.sys.base import Moment


class Time(Moment, Primitive):
    def at(self, t: datetime) -> Any:
        return t.timestamp() / 60
