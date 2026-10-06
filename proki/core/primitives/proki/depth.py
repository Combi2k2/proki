"""`depth`: how deep what's in focus is, from its label's category."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, ClassVar

from proki.core.primitives.base import Primitive
from proki.core.primitives.proki.base import Labeled


class Depth(Labeled, Primitive):
    """How deep what's in focus is, from `Depth.depth_of(app, title)` (its label's
    category; the app sets it)."""

    depth_of: ClassVar[Callable[[str, str], float | None]] = staticmethod(lambda app, title: None)

    def of(self, app: str, title: str) -> Any:
        return Depth.depth_of(app, title)
