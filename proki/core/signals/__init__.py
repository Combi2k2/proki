"""The signal language: how proki turns what it records into values it can act on.

    Stream          a value a cycle, and the cycles
    Expr            an expression, text like "ts_mean(keys, 5) > 30", and its value, a stream
    Signal          an expression, named
    Variable        a value that's set: by a program, or by you

Every value has a type, as it says, else as it's worked out from what it reads.
"""

from proki.core.signals.stream   import Storage, Stream
from proki.core.signals.signal   import Signal
from proki.core.signals.expr     import Expr
from proki.core.signals.variable import Variable

__all__ = ["Expr", "Signal", "Storage", "Stream", "Variable"]
