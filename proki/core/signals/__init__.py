"""The signal language: how proki turns what it records into values it can act on.

    Stream          a value per cycle, and how the cycles run
    compile_expr    an expression, text like "ts_mean(keys, 5) > 30", made a stream
    Signal          an expression, named
    Variable        state a program keeps, set by its actions

Every value has a type, as it says or as it's worked out from what it reads. What streams
are built from: the inputs (what's recorded, and the clock), and the operators (ts_mean,
every, ...).
"""

from proki.core.signals.stream   import NEVER, Storage, Stream, Value
from proki.core.signals.signal   import Signal
from proki.core.signals.variable import Variable, VariableStore
from proki.core.signals.expr     import compile_expr, parse

__all__ = [
    "NEVER",
    "Storage",
    "Stream",
    "Value",
    "Signal",
    "Variable",
    "VariableStore",
    "compile_expr",
    "parse",
]
