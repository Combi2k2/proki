"""`recorded`: whether ActivityWatch recorded anything (false: it or proki was off)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from proki.core.primitives.base import Primitive
from proki.services import aw


class Recorded(Primitive):
    """Whether ActivityWatch recorded anything at the moment: false while it (or proki,
    which runs it) was off, or the computer asleep."""

    buckets = (aw.WINDOW, aw.INPUT)

    def read(self, rec: aw.Record | None, t: datetime) -> Any:
        if rec is None:
            return None
        return rec[aw.WINDOW].covering(t) is not None or rec[aw.INPUT].covering(t) is not None
