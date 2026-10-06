"""`title`: the window title in focus (window watcher)."""

from __future__ import annotations

from proki.core.primitives.aw.base import Window
from proki.core.primitives.base import Primitive


class Title(Window, Primitive):
    field = "title"
