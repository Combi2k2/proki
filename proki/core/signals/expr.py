"""Expressions: the text of the signal language, compiled into a tree of streams.

Signals, rules, a variable's starting value and actions all use expressions. They are
written in Python's syntax, but read by proki itself, not run by Python:

    ts_mean(keys + mouse_click, 5)
    ts_sum(label == "video_streaming", 60)
    ts_mean(focus_2m, 2) - delay(ts_mean(focus_2m, 2), 2)
    ts_count(app, 30) > 20 and not in_session

What an expression can contain:
    numbers, text in quotes, True / False
    + - * / // %, comparisons (== != < <= > >=), `in` / `not in` a tuple of constants
    and, or, not
    the operators of core/ops/ (ts_mean, every, delay, ...)
    names of inputs, signals and variables

Time is always in minutes: windows, delays, and rates (keys is presses per minute).

Unknown values: a value that can't be worked out is None (unknown). That includes an
unknown input, a division by zero, and text where a number goes. Anything worked out
from an unknown value is unknown too, except `and` / `or` when one side already settles
the answer (`True or unknown` is True).

Mistakes visible in the text itself (an unknown name, a missing argument, `"a" + 1`, a
window that isn't a number) raise ExprError when the expression is compiled.
"""

from __future__ import annotations

import ast
import operator
from functools import lru_cache
from typing import Any

from proki.core import ops
from proki.core.signals.stream import Stream
from proki.errors import ExprError


@lru_cache(maxsize=256)
def parse(expr: str) -> ast.expr:
    """The expression's syntax tree. ExprError if it isn't valid syntax."""
    try:
        return ast.parse(expr, mode="eval").body
    except SyntaxError as e:
        raise ExprError(f"can't read {expr!r}: {e.msg}") from None


def compile_expr(expr: str) -> Stream:
    """The expression as a stream, its names looked up in `Stream.registry`. Any mistake
    the text shows becomes an ExprError naming the expression."""
    try:
        result = _build(parse(expr))
    except ExprError:
        raise
    except (TypeError, ValueError, ArithmeticError) as e:  # a wrong argument, `"a" + 1`, ...
        raise ExprError(f"{expr!r}: {e}") from None
    return result if isinstance(result, Stream) else ops.Constant(result)


def _lift(f: Any, *args: Any, unknown: bool = False) -> Any:
    """`f` applied to the arguments. If they're all constants, it's worked out right away
    (so `7 * 1440` is a plain number, usable as a window). Otherwise it's a stream that
    applies `f` each cycle (ops.Lift). `unknown=True`: `f` handles unknown arguments
    itself (and / or). Otherwise any unknown argument makes the result unknown."""
    if any(isinstance(a, Stream) for a in args):
        return ops.Lift(f, *args, unknown=unknown)
    return None if not unknown and any(a is None for a in args) else f(*args)


def _divide(f: Any) -> Any:
    """Division (/ // %) that gives unknown instead of failing when dividing by zero."""
    return lambda a, b: None if b == 0 else f(a, b)


def _and(*values: Any) -> Any:
    """`and`: False if any value is false, else unknown if any is unknown, else True."""
    if any(v is not None and not v for v in values):
        return False
    return None if None in values else True


def _or(*values: Any) -> Any:
    """`or`: True if any value is true, else unknown if any is unknown, else False."""
    if any(v is not None and v for v in values):
        return True
    return None if None in values else False


BINARY = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: _divide(operator.truediv),
    ast.FloorDiv: _divide(operator.floordiv),
    ast.Mod: _divide(operator.mod),
}
COMPARE = {
    ast.Lt: operator.lt, ast.LtE: operator.le,
    ast.Gt: operator.gt, ast.GtE: operator.ge,
    ast.Eq: operator.eq, ast.NotEq: operator.ne,
    ast.In: lambda a, b: a in b, ast.NotIn: lambda a, b: a not in b
}


def _build(node: ast.expr) -> Any:
    """One node of the syntax tree as a constant or a stream. ExprError for anything an
    expression can't contain."""
    match node:
        case ast.Constant(value=value) if isinstance(value, (int, float, str, bool)):
            return value
        case ast.Tuple(elts=elts) if all(isinstance(e, ast.Constant) for e in elts):
            return tuple(_build(e) for e in elts)  # for `in`: label in ("ide", "terminal")
        case ast.Name(id=name):
            if name not in Stream.registry:
                raise ExprError(f"unknown name {name!r}")
            return Stream.registry[name]
        case ast.Call(func=ast.Name(id=name), args=args, keywords=[]) if name in ops.FUNCTIONS:
            return ops.FUNCTIONS[name](*(_build(a) for a in args))
        case ast.BinOp(left=left, op=op, right=right) if type(op) in BINARY:
            return _lift(BINARY[type(op)], _build(left), _build(right))
        case ast.UnaryOp(op=ast.USub(), operand=operand):   return _lift(operator.neg, _build(operand))
        case ast.UnaryOp(op=ast.Not(), operand=operand):    return _lift(operator.not_, _build(operand))
        case ast.BoolOp(op=op, values=values):
            return _lift(_and if isinstance(op, ast.And) else _or, *(_build(v) for v in values), unknown=True)
        case ast.Compare(left=left, ops=comparisons, comparators=rights) if all(type(c) in COMPARE for c in comparisons):
            operands = [_build(left), *(_build(r) for r in rights)]
            fs = [COMPARE[type(c)] for c in comparisons]
            return _lift(lambda *vs: all(f(a, b) for f, a, b in zip(fs, vs, vs[1:])), *operands)
    raise ExprError(f"not allowed in an expression: {ast.unparse(node)}")
