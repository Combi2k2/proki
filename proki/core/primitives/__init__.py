"""Primitives: the basic streams everything else is built from, read from what your computer
recorded, or from its clock.

    running         whether anything was recorded (false: proki was off, or the computer asleep)

    the app, window or tab in focus
        app_name        the app
        app_title       the window's title
        tab_url         the tab's address, while a browser is in focus
        label           what the app or page is ("Videos", "Chat", ...), or "" for one with no
                        label yet
        depth           how deep the work is, from its label's category

    the time of the cycle
        daytime         minutes since local midnight (0 to 1440)
        time            minutes since 1970 (never wraps: `time - last_suggested`)
        weekday         0 Monday to 6 Sunday
        dd, mm, yy      the day of the month (1 to 31), the month (1 to 12), the year (2026)

    input, per minute, over each cycle
        keys_pressed    keys pressed
        mouse_move      mouse movement, in pixels
        mouse_click     mouse clicks
        mouse_scroll    scrolling, in scroll units

A primitive is in a folder by where it comes from, each folder with what its primitives
share. Which ones run, and how much of its past each keeps, is the config's "inputs".

How values are read: what's recorded comes as events (a start, a length, data), and a value
holds for its event's length. A primitive's value in a cycle is the event's holding at that
moment. Where nothing was recorded, it's unknown (None).

How the cycles run (`Primitive.run(now)`, once a cycle): what was recorded since the last one
is fetched, then each cycle up to now is run. The first run starts a day back (the longest
table), so every table starts full. After a pause (proki off, the computer asleep), the
cycles in between are run from what was recorded, `running` false where nothing was.

Signals read what was recorded only through here.
"""

from proki.core.primitives.base  import Primitive
from proki.core.primitives.proki import Depth, Label
from proki.core.primitives.aw    import App, Keys, MouseClick, MouseMove, MouseScroll, Recorded, Recording, Title, Url
from proki.core.primitives.sys   import Daytime, Dd, Mm, Time, Weekday, Yy

__all__ = [
    "Primitive", "Recording",
    "App", "Title", "Url", "Recorded", "Keys", "MouseClick", "MouseMove", "MouseScroll",
    "Depth", "Label",
    "Daytime", "Time", "Weekday", "Dd", "Mm", "Yy",
]
