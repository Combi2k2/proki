"""Primitives from what ActivityWatch recorded: the window, the browser tab, input. Their base.py holds what they share."""

from proki.core.primitives.aw.app_name import App
from proki.core.primitives.aw.app_title import Title
from proki.core.primitives.aw.keys import Keys
from proki.core.primitives.aw.mouse_click import MouseClick
from proki.core.primitives.aw.mouse_move import MouseMove
from proki.core.primitives.aw.mouse_scroll import MouseScroll
from proki.core.primitives.aw.recorded import Recorded
from proki.core.primitives.aw.tab_url import Url

__all__ = ["App", "Keys", "MouseClick", "MouseMove", "MouseScroll", "Recorded", "Title", "Url"]
