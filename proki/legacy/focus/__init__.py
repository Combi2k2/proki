"""Focus intensity, built from small components that can be tuned one at a time.

    window.py      slice the timeline into one window: stretches + switches   (no scoring)
    depth.py       how deep the work in the window was                        → [0, 1]
    stability.py   whether switching stayed within a small working set         → [0, 1]
    continuity.py  whether attention stayed on each item long enough           → [0, 1]
    moment.py      intensity at one moment = depth × stability × continuity
    period.py      summary of a period (hour, block, day) from moment scores
    params.py      every tunable number, in one place (filled from the config)

See docs/components.md for the formulas and what each parameter does.
"""

from proki.legacy.focus.moment import Moment, moment, series
from proki.legacy.focus.params import FocusParams
from proki.legacy.focus.period import Period, summarize

__all__ = ["FocusParams", "Moment", "Period", "moment", "series", "summarize"]
