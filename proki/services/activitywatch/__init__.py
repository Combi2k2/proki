"""ActivityWatch, the tracker proki is built on (imported as `aw`: proki/services).

    server.py   runs the server and watchers, so ActivityWatch's own tray app isn't needed
    client.py   the server's REST API, what the watchers record, and how to look up a
                moment in it (only core/signals/primitive.py reads a `Record`)
    utils.py    finding the programs (`aw_detect`), checking the server (`aw_health`)
"""

# what `aw.` gives
from proki.services.activitywatch.client import (
    AFK,
    HOLD,
    INPUT,
    WEBTAB,
    WINDOW,
    ActivityWatchClient,
    Event,
    Events,
    Record,
)
from proki.services.activitywatch.server import ActivityWatchSupervisor
from proki.services.activitywatch.utils import aw_detect, aw_health

__all__ = [
    "ActivityWatchSupervisor",
    "ActivityWatchClient",
    "aw_detect",
    "aw_health",
    "AFK",
    "HOLD",
    "INPUT",
    "WEBTAB",
    "WINDOW",
    "Event",
    "Events",
    "Record",
]
