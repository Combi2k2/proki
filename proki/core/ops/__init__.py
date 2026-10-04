"""Time-series operators: they take streams and return streams (signals/base.py).

Our own operators, not Polars, without a dependency; one file per operator, named after
its class (`ts_mean.py`: `TsMean`). Python calls the class (`TsMean(keys, 5)`), an
expression its name in snake case (`ts_mean(keys, 5)`). They know no clock, only the time
of each cycle (`advance(t)`): their queues hold (time, value), and a window over w
minutes holds what came in the last w minutes, whatever the input's period.

Time is in minutes: windows `w`, delays `d` and spans `p` are numbers of minutes.

Pointwise (a value each cycle):
    lift(f, x, y, ...)   f of the values; plain values count as constant streams
    delay(x, d)          x as it was `d` ago

Over a trailing window (t - w, t]:
    ts_sum(x, w)     ∫ x dt: a rate per minute gives a count, true / false gives minutes
    ts_mean(x, w)    mean over the known values of the window
    ts_max(x, w), ts_min(x, w)
    ts_count(x, w)   how many times x changed to a new value in the window (true / false:
                    how many times it became true)
    ts_rank(x, w)    where x's current value stands among the window's, in [0, 1]

Resampling:
    every(x, p, how)   one value per p minutes (clock-aligned spans): the mean (default),
                       "sum", "max", "min" or "last" of x's values in each span

Windows and `delay` take only the input's fresh values (a slow input, from `every`, adds
one per span), and when they start they fill their queue from the input's table, if it
keeps one (its `backfill`): `ts_mean(every(focus, 5), 7 * 1440)` is right from the start.
They nest: `delay(ts_mean(keys, 5), 2)`.
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
