"""Operators: functions over time series. Each takes streams and gives a stream.

proki's own (no dependency), one file per operator, named after its class
(`ts_mean.py`: `TsMean`). In Python you call the class, `TsMean(keys, 5)`. In an
expression you write its name in snake case, `ts_mean(keys, 5)`.

All times are in minutes: windows `w`, delays `d`, spans `p`.

Every cycle (one value per cycle):
    lift(f, x, y, ...)   f of the values (behind + - * /, comparisons, and / or / not)
    delay(x, d)          x as it was d minutes ago

Over the last w minutes (a "window"):
    ts_sum(x, w)     the total over time: a rate per minute gives a count. True / False
                     gives minutes (ts_sum(in_session, 60): minutes in a session this hour)
    ts_mean(x, w)    the average of the known values
    ts_max(x, w)     the largest (and ts_min(x, w) the smallest)
    ts_count(x, w)   how many times x changed to a new value (for True / False: how many
                     times it became True)
    ts_rank(x, w)    where x's current value stands among the window's, from 0 to 1

Slower (one value per span):
    every(x, p, how)   one value per p minutes, on the local clock: the mean (default),
                       "sum", "max", "min" or "last" of x's values in each span

A slow stream (from `every`) adds one value per span to a window, not one per cycle,
so a long window over it stays small: `ts_rank(every(focus, 60), 30 * 1440)` holds 720
values. When a window starts, it fills itself from its input's table if the input keeps
one, so `ts_mean(every(focus, 5), 7 * 1440)` is right from the start. Operators nest:
`delay(ts_mean(keys, 5), 2)`.
"""

from proki.core.ops.base import Constant, Operator, Queued
from proki.core.ops.delay import Delay
from proki.core.ops.every import Every
from proki.core.ops.lift import Lift
from proki.core.ops.ts_count import TsCount
from proki.core.ops.ts_max import TsMax
from proki.core.ops.ts_mean import TsMean
from proki.core.ops.ts_min import TsMin
from proki.core.ops.ts_rank import TsRank
from proki.core.ops.ts_sum import TsSum

FUNCTIONS = Operator.functions  # what an expression can call, by name: each operator, once imported above

__all__ = [
    "Constant",
    "Operator",
    "Queued",
    "FUNCTIONS",
    "Delay",
    "Every",
    "Lift",
    "TsCount",
    "TsMax",
    "TsMean",
    "TsMin",
    "TsRank",
    "TsSum",
]
