"""Expressions: what signals, rules, a variable's starting value and actions are written in.
They look like Python, but proki reads them itself, never runs them:

    ts_mean(keys + mouse_click, 5)                    typing and clicking, the last 5 minutes
    ts_sum(label == "Videos", 60)                     minutes on videos this hour
    ts_mean(focus, 2) - delay(ts_mean(focus, 2), 2)   how focus moved, 2 minutes on 2
    ts_count(app, 30) > 20 and not session.active     switching a lot, out of a session

What one can hold:

    values       numbers, text in quotes, True / False, None (unknown), a list of them:
                 ['Something new']
    names        inputs, signals and variables: focus, session.active
    arithmetic   + - * / // %; + also joins two texts, or two lists:
                 groups.name + ['Something new']
    comparisons  == != < <= > >=; `in` / `not in` a tuple of values: app in ('Code', 'Xcode')
    unknowns     x is None, x is not None (never unknown themselves)
    logic        and, or, not; a if test else b
    operators    ts_mean, every, delay, min, max, ... called by name
    a field      of a value: answer.hours; of a list, every item's, as a list (a column):
                 groups.name
    an item      of a list by its place: groups[0], groups[-1] (the last); a part of one:
                 queue[1:] (all but the first), queue[:3]

Time is in minutes: windows, delays, rates (keys is presses per minute).

A value that can't be worked out is unknown: an unknown input, a missing field or item, a
division by zero, text where a number goes. Anything worked out from an unknown value is
unknown too, unless `and` / `or` is settled by the other side (`True or unknown` is True),
and `a if test else b` is unknown if the test is.

What each gives:

    a name                    its value, of its type
    arithmetic, operators     a number (text + text: a text; list + list: a list)
    comparisons, logic        true or false
    a if t else b, [a, b]     a and b's type, if they share one (a list of it)
    a field, an item          as its value's or its list's type says

A mistake the text shows is an ExprError as proki reads it: an unknown name, a missing
argument, `"a" + 1`, a window that isn't a number.
"""

from __future__ import annotations

import ast
import operator
from functools import lru_cache
from typing import Any

from proki.core import ops
from proki.core.signals.stream import Stream
from proki.types import field, itemof, listof, typeof, typename
from proki.errors import ExprError
from proki.utils import snake


@lru_cache(maxsize=256)
def parse(expr: str) -> ast.expr:
    """The expression, read. ExprError if it isn't written right."""
    try:
        return ast.parse(expr, mode="eval").body
    except SyntaxError as e:
        raise ExprError(f"can't read {expr!r}: {e.msg}") from None


class Expr(str):
    """An expression: `keys > 5`, `work.tasks[0].status`. ExprError if it isn't one."""

    def __new__(cls, text: Any) -> Expr:
        made      = super().__new__(cls, str(text))
        made.tree = parse(made)
        return made

    @property
    def lvalue(self) -> bool:
        """Whether it can be set: `x`, `x.a`, `xs[0].a`."""
        node = self.tree
        while isinstance(node, ast.Attribute | ast.Subscript):
            node = node.value
        return isinstance(node, ast.Name)

    @property
    def rvalue(self) -> bool:
        """Whether it can be worked out: any expression can."""
        return True

    @property
    def window(self) -> str | None:
        """Its first window: "ts_mean" (None: none, or only by a signal's name)."""
        def walk(stream: Stream) -> str | None:
            if stream.name and Stream.registry.get(stream.name) is stream:
                return None  # a named stream: it moves on every cycle anyway
            if not isinstance(stream, ops.Lift | ops.Constant):
                return snake(type(stream).__name__)
            return next((w for i in stream.inputs if (w := walk(i)) is not None), None)

        return walk(self.stream())

    @property
    def type(self) -> Any:
        """Its type."""
        return self.stream().type

    def value(self) -> Any:
        """Its value now (None: unknown)."""
        return self.stream().current()

    def stream(self) -> Stream:
        """Its value, as a stream: a new one each call. ExprError for a mistake the text shows."""
        try:
            result = _build(self.tree)
        except ExprError:
            raise
        except (TypeError, ValueError, ArithmeticError) as e:  # a wrong argument, `"a" + 1`, ...
            raise ExprError(f"{self!r}: {e}") from None
        return result if isinstance(result, Stream) else ops.Constant(result)


def _lift(f: Any, *args: Any, unknown: bool = False, type: Any = "any") -> Any:
    """`f` of the arguments: of values alone, worked out now (`7 * 1440`, a number a window
    takes), else each cycle. Any unknown makes it unknown, unless `unknown`: `f` reads
    unknowns itself (and / or)."""
    if any(isinstance(a, Stream) for a in args):
        return ops.Lift(f, *args, unknown=unknown, type=type)
    return None if not unknown and any(a is None for a in args) else f(*args)


def _type(x: Any, of: Any) -> Any:
    """The type of a part of an expression: a stream's (`of`), else its value's."""
    return of(x) if isinstance(x, Stream) else typeof(x)


def _pluck(value: Any, key: str) -> Any:
    """A field of a value: an object's; of a list, each item's, as a list (one list of them
    all, for a field that's a list); else unknown."""
    if isinstance(value, dict):         return value.get(key)
    if not isinstance(value, list | tuple):  return None
    got = [_pluck(v, key) for v in value]
    if not any(isinstance(g, list | tuple) for g in got):  return got
    return [x for g in got if g is not None for x in (g if isinstance(g, list | tuple) else [g])]


def _index(value: Any, at: Any) -> Any:
    """An item of a list by its place (-1: the last), else unknown."""
    if isinstance(value, list | tuple) and type(at) is int and -len(value) <= at < len(value):
        return value[at]
    return None


END = 2**62  # a part's end, when it says none: the list's


def _slice(value: Any, start: Any, end: Any) -> Any:
    """A part of a list, from `start` up to `end` (-1: the last), else unknown."""
    if isinstance(value, list | tuple) and type(start) is int and type(end) is int:
        return list(value[start:end])
    return None


def _constant(node: ast.expr) -> bool:
    """Whether a list or a tuple is of plain values (-1 too), or of lists of them."""
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return isinstance(node.operand, ast.Constant) and isinstance(node.operand.value, int | float)
    return isinstance(node, ast.Constant) or isinstance(node, ast.List | ast.Tuple) and all(map(_constant, node.elts))


def _listed(items: list, of: Any) -> Any:
    """What a list of values gives: a list of their type, if they share one."""
    types = {str(_type(x, of)) for x in items}
    return listof(_type(items[0], of) if len(types) == 1 else "any")


def _joined(sides: tuple, of: Any) -> Any:
    """What + gives: text + text a text, a list + a list a list (of their items' type, if they
    share one), else a number. A side of any type is taken as the other's."""
    types = [t for x in sides if (t := _type(x, of)) not in ("any", {})]
    if not types:
        return "any"
    if all(t == "string" for t in types):
        return "string"
    if all(typename(t) == "array" for t in types):
        items = {str(itemof(t)) for t in types}
        return listof(itemof(types[0]) if len(items) == 1 else "any")
    return "number"


def _divide(f: Any) -> Any:
    """/ // %: unknown by zero."""
    return lambda a, b: None if b == 0 else f(a, b)


def _and(*values: Any) -> Any:
    """`and`: False if any value is false, else unknown if any is unknown, else True."""
    if any(v is not None and not v for v in values):
        return False
    return None if None in values else True


def _if(test: Any, body: Any, orelse: Any) -> Any:
    """`body if test else orelse`: unknown if the test is."""
    return None if test is None else body if test else orelse


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
    ast.In: lambda a, b: a in b, ast.NotIn: lambda a, b: a not in b,
    ast.Is: operator.is_, ast.IsNot: operator.is_not,
}


def _build(node: ast.expr) -> Any:
    """A part of an expression, as a value or a stream. ExprError for anything an expression
    can't hold."""
    match node:
        case ast.Constant(value=value) if value is None or isinstance(value, (int, float, str, bool)):
            return value
        case ast.Tuple() if _constant(node):
            return ast.literal_eval(node)  # for `in`: label in ("Code editor", "Terminal")
        case ast.List() if _constant(node):
            return ast.literal_eval(node)  # ['Something new'], [['Something new', 'what it means']]
        case ast.List(elts=elts):  # a list of values: [guess.label, 'Something new']
            items = [_build(e) for e in elts]
            return _lift(lambda *vs: list(vs), *items, unknown=True, type=lambda of: _listed(items, of))
        case ast.Name(id=name):
            if name not in Stream.registry:
                raise ExprError(f"unknown name {name!r}")
            return Stream.registry[name]
        case ast.Attribute() if (name := ast.unparse(node)) in Stream.registry:
            return Stream.registry[name]
        case ast.Attribute(value=value, attr=key):  # a field of a value: the longest name there is, then its keys
            made = _build(value)
            return _lift(lambda v: _pluck(v, key), made, type=lambda of: field(_type(made, of), key))
        case ast.Subscript(value=value, slice=ast.Slice(lower=lower, upper=upper, step=None)):  # a part of a list: xs[1:]
            made = _build(value)
            ends = _build(lower) if lower else 0, _build(upper) if upper else END
            return _lift(_slice, made, *ends, type=lambda of: _type(made, of))
        case ast.Subscript(value=value, slice=index):  # an item of a list, by its place
            made = _build(value)
            return _lift(_index, made, _build(index), type=lambda of: itemof(_type(made, of)))
        case ast.Call(func=ast.Name(id=name), args=args, keywords=[]) if name in ops.FUNCTIONS:
            return ops.FUNCTIONS[name](*(_build(a) for a in args))
        case ast.BinOp(left=left, op=op, right=right) if type(op) in BINARY:
            sides = _build(left), _build(right)
            return _lift(BINARY[type(op)], *sides, type=(lambda of: _joined(sides, of)) if isinstance(op, ast.Add) else "number")
        case ast.UnaryOp(op=ast.USub(), operand=operand):   return _lift(operator.neg, _build(operand), type="number")
        case ast.UnaryOp(op=ast.Not(), operand=operand):    return _lift(operator.not_, _build(operand), type="boolean")
        case ast.BoolOp(op=op, values=values):
            return _lift(_and if isinstance(op, ast.And) else _or, *(_build(v) for v in values), unknown=True, type="boolean")
        case ast.Compare(left=left, ops=comparisons, comparators=rights) if all(type(c) in COMPARE for c in comparisons):
            operands = [_build(left), *(_build(r) for r in rights)]
            fs = [COMPARE[type(c)] for c in comparisons]
            known = any(type(c) in (ast.Is, ast.IsNot) for c in comparisons)  # `is None` reads unknown values itself
            return _lift(lambda *vs: all(f(a, b) for f, a, b in zip(fs, vs, vs[1:])), *operands, unknown=known, type="boolean")
        case ast.IfExp(test=test, body=body, orelse=orelse):
            branches = _build(body), _build(orelse)
            same = lambda of: _type(branches[0], of) if _type(branches[0], of) == _type(branches[1], of) else "any"
            return _lift(_if, _build(test), *branches, unknown=True, type=same)
    raise ExprError(f"not allowed in an expression: {ast.unparse(node)}")
