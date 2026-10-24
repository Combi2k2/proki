"""The signal language: how proki turns what it records into values it can act on.

    Stream          a value a cycle, and the cycles
    compile_expr    an expression, text like "ts_mean(keys, 5) > 30", as a stream
    Signal          an expression, named
    Variable        a value that's set: by a program, or by you

Every value has a type, as it says, else as it's worked out from what it reads.
"""

from proki.core.signals.stream   import Storage, Stream
from proki.core.signals.signal   import Signal
from proki.core.signals.variable import Variable
from proki.core.signals.expr     import compile_expr

__all__ = ["Signal", "Storage", "Stream", "Variable", "compile_expr"]
