"""`label`: what the app or page is ("video_streaming", "chat", ...); "" for a window
without one yet (known, just not labeled), unknown (None) when no window is."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, ClassVar

from proki.core.primitives.base import Primitive
from proki.core.primitives.proki.base import Labeled


class Label(Labeled, Primitive):
    """`Label.label_of(app, title)` of the window in focus (the app sets it: its labels);
    "" when it has none, so `label in ("email", ...)` is false there, not unknown."""

    label_of: ClassVar[Callable[[str, str], str | None]] = staticmethod(lambda app, title: None)

    def of(self, app: str, title: str) -> Any:
        return Label.label_of(app, title) or ""
