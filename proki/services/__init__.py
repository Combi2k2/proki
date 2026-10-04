"""Outside services proki talks to.

    activitywatch/   ActivityWatch, as `aw`: runs its server and watchers (so its own tray
                     app isn't needed), and reads what they recorded
    jev.py           openjev, the structured-decision API (optional)
"""

from proki.services import activitywatch as aw
from proki.services import jev

__all__ = ["aw", "jev"]