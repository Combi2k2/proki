"""What the system primitives (this folder) share: `Moment`, read from the cycle's time on
this computer's clock, not from a recording."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from proki.services import aw


class Moment:
    """Mixin: from the cycle's time alone, so known even when nothing was recorded."""

    unbounded = "a table of the time needs a window (it's no recording, it would grow without end)"

    def read(self, rec: aw.Record | None, t: datetime) -> Any:
        return self.at(t)

    def at(self, t: datetime) -> Any:
        raise NotImplementedError
