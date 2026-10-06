"""The signal language: how proki turns what it records into numbers it can act on.

    stream.py     Stream: a value per cycle, and how the cycles run
    expr.py       expressions: text like "ts_mean(keys, 5) > 30", compiled into streams
    signal.py     Signal: a named expression
    variable.py   Variable: app state that actions set (in_session, deadline_eod, ...)

The primitives they're built from (app, keys, clock, ...) are in core/primitives/, the
operators (ts_mean, every, ...) in core/ops/.
"""

from proki.core.signals.stream import NEVER, Storage, Stream, Value
from proki.core.signals.expr import compile_expr, parse
from proki.core.signals.signal import Signal
from proki.core.signals.variable import Variable, VariableStore

__all__ = [
    "NEVER", "Storage", "Stream", "Value",
    "Signal", "compile_expr", "parse",
    "Variable", "VariableStore",
]
