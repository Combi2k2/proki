"""`tab_url`: the tab's address, while a browser is in focus (browser extension)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from proki.core.primitives.aw.base import tab_url
from proki.core.primitives.base import Primitive
from proki.services import aw


class Url(Primitive):
    """The address of the tab in focus, while a browser app is in focus (else unknown)."""

    _typed = "string"
    desc   = "the address of the browser tab in focus (unknown outside a browser)"
    name   = "tab_url"

    buckets = (aw.WINDOW, aw.WEBTAB)

    def read(self, t: datetime) -> Any:
        return tab_url(t)
