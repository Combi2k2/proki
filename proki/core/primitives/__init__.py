"""Primitives: the streams the others are built from, one file each, in a folder by where
they come from: aw/ what ActivityWatch recorded, sys/ the computer's clock, proki/ what
proki works out from the window in focus (its labels); each folder's base.py is what its
primitives share. `Primitive` and the cycles' `run` are in base.py. A kind's name is its
class's in snake case (`MouseMove` in aw/mouse_move.py: "mouse_move"), not its file's.

The one place that reads ActivityWatch (legacy/core/collector.py still does too, until
the rest of proki moves onto signals), through services/activitywatch (`aw`: the server's API, and
how the watchers store data). Which primitives exist, and how much history each
keeps, is the config's "inputs" (proki/compiler.py).

    recorded           whether ActivityWatch recorded anything (false: it or proki was off)

    about the app, window or tab in focus
        app            the app                                    window watcher
        title          the window title                           window watcher
        url            the tab's address, while a browser is in focus   browser extension
        label          what the app or page is ("video_streaming", "chat", ...), from the
                       app and the window title (in a browser, the title names the page);
                       "" for a window without a label yet
        depth          how deep it is, from its label's category (`Depth.depth_of`, set by the app)

    about the time (of the cycle, not from ActivityWatch)
        clock          minutes since local midnight (0 to 1440)
        weekday        0 Monday to 6 Sunday, local
        time           minutes since 1970 (never wraps: `time - last_suggested`)

    about input, per minute over each cycle's time frame (aw-watcher-input, an event every ~5 s)
        keys           key presses (the watcher counts down and up: its `presses` / 2)
        mouse_move     mouse movement, in pixels
        mouse_click    mouse clicks
        mouse_scroll   scrolling, in scroll units

ActivityWatch keeps events (timestamp, duration, data) and merges identical
neighbours, so a value holds over each event, with gaps where nothing was recorded
(unknown: None). A primitive's value in a cycle comes from the event holding at the
cycle's moment.

This package drives the cycles (core/signals/stream.py; `run` in base.py): `Primitive.run(now)` fetches what
ActivityWatch recorded since the last cycle and ticks every stream through the cycles up
to `now`, one every 10 s. The first time, it starts as far back as the longest table
(the config's `backfill`), so every table starts full; then ActivityWatch's events are
let go: a primitive with a table keeps its own history. After a pause (proki not
running, the computer asleep), the cycles in between are run from what was recorded;
`recorded` is false where nothing was.
"""

from proki.core.primitives.base import Primitive
from proki.core.primitives.aw import App, Keys, MouseClick, MouseMove, MouseScroll, Recorded, Title, Url
from proki.core.primitives.sys import Clock, Time, Weekday
from proki.core.primitives.proki import Depth, Label

__all__ = ["Primitive", "App", "Clock", "Depth", "Keys", "MouseClick", "MouseMove", "MouseScroll", "Label", "Recorded", "Time", "Title", "Url", "Weekday"]
