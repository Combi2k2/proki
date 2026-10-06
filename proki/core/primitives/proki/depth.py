"""`depth`: how deep the work in focus is (1 deep, 0.25 shallow, ...), from the category of
its label. Unknown for a window without a label.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, ClassVar

from proki.core.primitives.base import Primitive
from proki.core.primitives.proki.base import Labeled


class Depth(Labeled, Primitive):
    """How deep the window in focus is: `Depth.depth_of(app, title)`, a function the app
    plugs in (it maps the window's label to its category's depth)."""

    depth_of: ClassVar[Callable[[str, str], float | None]] = staticmethod(lambda app, title: None)

    def of(self, app: str, title: str) -> Any:
        return Depth.depth_of(app, title)
