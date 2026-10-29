"""Operators: what an expression calls by name, each of values that change over time,
giving one: `ts_mean(keys, 5)`. All times are in minutes: windows `w`, delays `d`, spans `p`.

Each cycle:
    delay(x, d)          x as it was d minutes ago
    min(x, y, ...)       the smallest of the values (and max(x, y, ...) the largest)
    clip(x, lo, hi)      x, kept between lo and hi
    str(x)               x as text: 40, not 40.0

Of a list (its known items; a column like tasks.deadline is one):
    min(xs), max(xs)     the smallest item, the largest
    argmin(xs)           the place of the smallest (and argmax(xs) the largest's): tasks[argmin(tasks.deadline)]
    sort(xs, keys)       the items, least first: by their own, or by `keys`'s (sort(tasks, tasks.deadline))
    len(xs)              how many items
    index(xs, x)         the place of x: work.tasks[index(work.tasks.id, item.id)]
    zip(xs, ys, ...)     lists side by side: zip(groups.name, groups.desc), each [name, desc]
    where(xs, keep)      the items whose keep is known and not false: where(tasks, tasks.start);
                         where(xs, keys, x) the ones whose keys is x: where(tasks, tasks.group, 3)
    choices(x)           the values x's type allows: choices(work.group.tags)

Over the last w minutes (a window):
    ts_sum(x, w)         the total over time: a rate per minute gives a count, True / False
                         gives minutes (ts_sum(session.active, 60): minutes in a session this hour)
    ts_mean(x, w)        the average of the known values
    ts_max(x, w)         the largest (and ts_min(x, w) the smallest)
    ts_count(x, w)       how many times x changed to a new value (True / False: became True)
    ts_rank(x, w)        where x's value now stands among the window's, from 0 to 1
    ts_corr(x, y, w)     how closely x and y move together, from -1 to 1

Slower:
    every(x, p, how)     one value per p minutes, on your clock: the mean (default), "sum",
                         "max", "min" or "last" of each span's values

A window over a slow stream holds one value per span, so a long one stays small:
`ts_rank(every(focus, 60), 30 * 1440)` holds 720. A window over a stream that keeps its past
is full from the start: `ts_mean(every(focus, 5), 7 * 1440)`. Operators nest:
`delay(ts_mean(keys, 5), 2)`.
"""

from proki.core.ops.argmax   import Argmax
from proki.core.ops.argmin   import Argmin
from proki.core.ops.base     import Constant, Operator
from proki.core.ops.choices  import Choices
from proki.core.ops.clip     import Clip
from proki.core.ops.delay    import Delay
from proki.core.ops.every    import Every
from proki.core.ops.index    import Index
from proki.core.ops.len      import Len
from proki.core.ops.lift     import Lift
from proki.core.ops.max      import Max
from proki.core.ops.min      import Min
from proki.core.ops.sort     import Sort
from proki.core.ops.str      import Str
from proki.core.ops.ts_corr  import TsCorr
from proki.core.ops.ts_count import TsCount
from proki.core.ops.ts_max   import TsMax
from proki.core.ops.ts_mean  import TsMean
from proki.core.ops.ts_min   import TsMin
from proki.core.ops.ts_rank  import TsRank
from proki.core.ops.ts_sum   import TsSum
from proki.core.ops.where    import Where
from proki.core.ops.zip      import Zip

FUNCTIONS = Operator.functions  # what an expression can call, by name: each operator above

__all__ = ["FUNCTIONS", "Constant", "Lift"]
