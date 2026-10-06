"""What the clock primitives (this folder) share: `Moment`, a value read from the cycle's
time on this computer's clock, so it's known even when nothing was recorded.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from proki.services import aw


class Moment:
    """Mixin: a value worked out from the cycle's time alone (`at`)."""

    unbounded = "a table of the time needs a window (otherwise it would grow without end)"

    def read(self, rec: aw.Record | None, t: datetime) -> Any:
        return self.at(t)

    def at(self, t: datetime) -> Any:
        raise NotImplementedError
