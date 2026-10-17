"""Types: a field's, by its hint, and a value's. And a row (a dataclass) as JSON, as a tool
takes it (tools/), its fields' types the table's too (programs/code/base.py).

    hinted(hint)        a field's type, and whether it can be None
    typeof(value)       what sort of value: "bool", "number", "str", ...
    schema(row)         a dataclass's fields as JSON schemas, by name
    needed(row)         its fields with no default: the ones a new row needs
    typed(row, args)    arguments as JSON gives them, as its fields are
    plain(row)          a row as JSON
"""

from __future__ import annotations

import types
import typing
from collections.abc import Iterable
from dataclasses import MISSING, asdict, fields
from datetime import datetime
from typing import Any

SCHEMAS = {
    str      : {"type": "string"},
    int      : {"type": "integer"},
    float    : {"type": "number"},
    bool     : {"type": "boolean"},
    datetime : {"type": "string", "format": "date-time"}
}


def hinted(hint: Any) -> tuple[Any, bool]:
    """A field's type, and whether it can be None: `str | None` gives (str, True)."""
    if typing.get_origin(hint) in (typing.Union, types.UnionType):
        args = [a for a in typing.get_args(hint) if a is not type(None)]
        return (args[0] if len(args) == 1 else Any), len(args) < len(typing.get_args(hint))
    return hint, False


def typeof(value: Any) -> str:
    """What sort of value: "bool", "number", "str", "NoneType", ... (1 and 1.0 alike)."""
    return "bool" if isinstance(value, bool) else "number" if isinstance(value, int | float) else type(value).__name__


# --- a dataclass, as JSON ---------------------------------------------------------------------

def schema(row: type, without: Iterable[str] = ()) -> dict:
    """A dataclass's fields as JSON schemas, by name: a time as ISO text, a list as its items',
    one that can be None as null too."""
    names, shapes = {f.name for f in fields(row)} - set(without), {}
    for name, hint in typing.get_type_hints(row).items():
        if name not in names:  continue
        made, optional = hinted(hint)
        if typing.get_origin(made) is list:  shape = {"type": "array", "items": SCHEMAS.get(typing.get_args(made)[0], {})}
        else:                                shape = dict(SCHEMAS.get(made, {}))
        if optional and "type" in shape:     shape["type"] = [shape["type"], "null"]
        shapes[name] = shape
    return shapes


def needed(row: type, without: Iterable[str] = ()) -> tuple[str, ...]:
    """A dataclass's fields with no default: the ones a new row needs."""
    return tuple(f.name for f in fields(row)
                 if f.name not in without and f.default is MISSING and f.default_factory is MISSING)


def typed(row: type, args: dict) -> dict:
    """Arguments as JSON gives them, as `row`'s fields are: a time from its ISO text."""
    times = {name for name, hint in typing.get_type_hints(row).items() if hinted(hint)[0] is datetime}
    return {name: datetime.fromisoformat(value) if name in times and isinstance(value, str) else value
            for name, value in args.items()}


def plain(row: Any) -> dict:
    """A row as JSON: its times as ISO text."""
    return {name: value.isoformat() if isinstance(value, datetime) else value for name, value in asdict(row).items()}
