"""Primitives: the basic streams everything else is built from, read from what ActivityWatch
recorded or from the clock.

One file per primitive, in a folder by where it comes from:

    aw/      what ActivityWatch recorded
    sys/     this computer's clock
    proki/   what proki works out about the window in focus (its label)

Each folder's base.py holds what its primitives share. The top base.py holds `Primitive`
and `run`, which drives the cycles. A primitive's name is its class's in snake case
(`MouseMove` in aw/mouse_move.py is "mouse_move").

The primitives:

    recorded       whether ActivityWatch recorded anything (False: it or proki was off,
                   or the computer was asleep)

    the app, window or tab in focus
        app        the app                                         window watcher
        title      the window title                                window watcher
        url        the tab's address, while a browser is in focus  browser extension
        label      what the app or page is ("video_streaming", "chat", ...), from the app
                   and the window title, or "" for a window without a label yet
        depth      how deep the work is, from the label's category (`Depth.depth_of`)

    the time (of the cycle, not from ActivityWatch)
        clock      minutes since local midnight (0 to 1440)
        weekday    0 Monday to 6 Sunday, local
        time       minutes since 1970 (never wraps: `time - last_suggested`)

    input, per minute, over each cycle (aw-watcher-input sends an event every ~5 s)
        keys           key presses (the watcher counts down and up, so its `presses` / 2)
        mouse_move     mouse movement, in pixels
        mouse_click    mouse clicks
        mouse_scroll   scrolling, in scroll units

Which primitives exist, and how much history each keeps, is the config's "inputs"
(proki/compiler.py).

How values are read: ActivityWatch stores events (start, duration, data), and a value
holds for the length of its event. A primitive's value in a cycle comes from the event
holding at that moment. Where nothing was recorded, it's unknown (None).

How the cycles run (`Primitive.run(now)`, every 10 s): fetch what ActivityWatch recorded
since the last cycle, then run each cycle up to now. On the first run, it starts a day
back (the longest table), so every table starts full. After a pause (proki off, the
computer asleep), the cycles in between are run from the recording, and `recorded` is
False where nothing was.

Signals read ActivityWatch only through here.
"""

from proki.core.primitives.base import Primitive
from proki.core.primitives.aw import App, Keys, MouseClick, MouseMove, MouseScroll, Recorded, Title, Url
from proki.core.primitives.sys import Clock, Time, Weekday
from proki.core.primitives.proki import Depth, Label

__all__ = ["Primitive", "App", "Clock", "Depth", "Keys", "MouseClick", "MouseMove", "MouseScroll", "Label", "Recorded", "Time", "Title", "Url", "Weekday"]
