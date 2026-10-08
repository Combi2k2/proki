"""`url`: the tab's address, while a browser is in focus (browser extension)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from proki.core.primitives.aw.base import Recording, focused
from proki.core.primitives.base import Primitive
from proki.platforms import current as platform
from proki.services import aw


BROWSER_APPS = platform().BROWSER_APPS


class Url(Primitive):
    """The address of the tab in focus, while a browser app is in focus (else unknown).

    The browser extension reports a tab change right away, but a tab you stay on only now
    and then, so the current tab is its latest event, however old."""

    buckets = (aw.WINDOW, aw.WEBTAB)

    def read(self, t: datetime) -> Any:
        e = focused(t)
        if e is None or e.data.get("app") not in BROWSER_APPS:
            return None
        tab = Recording.rec[aw.WEBTAB].latest(t)
        return tab.data.get("url") if tab else None
