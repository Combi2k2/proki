"""`depth`: how deep the work in focus is (1 deep, 0.25 shallow, ...), from the category of
its label. Unknown for a window without a label.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, ClassVar

from proki.core.primitives.base import Primitive
from proki.core.primitives.proki.base import Labeled


class Depth(Labeled, Primitive):
    """How deep the window in focus is: `Depth.depth_of(app, url)`, a function the app
    plugs in (it maps the window's label to its category's depth)."""

    _typed = "number"
    desc   = "how deep the work in focus is, 0 to 1: 1 deep, 0.25 shallow (from its label)"

    depth_of: ClassVar[Callable[[str, str | None], float | None]] = staticmethod(lambda app, url: None)

    def of(self, app: str, url: str | None) -> Any:
        return Depth.depth_of(app, url)
