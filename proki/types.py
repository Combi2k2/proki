"""Types: what a value is, said as a JSON Schema, or by a short name for one.

    "number"    {"type": "number"}          "string"    {"type": "string"}
    "integer"   {"type": "integer"}         "array"     {"type": "array"}
    "boolean"   {"type": "boolean"}         "object"    {"type": "object"}
    "time"      {"type": "number", "format": "time"}: minutes since 1970, as `time` is
    "any"       {}: anything

    {"type": "object", "properties": {"hours": {"type": "number"}}, "required": ["hours"]}

Unknown (None) fits any type. A value set that doesn't fit its type is refused.

A field of a list read across it gives each item's, and a field that is a list gives them
all, one list (groups.tasks: every group's tasks).
"""

from __future__ import annotations

import json
from functools import cache
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError


NAMES = {
    "number" : {"type": "number"},
    "integer": {"type": "integer"},
    "boolean": {"type": "boolean"},
    "string" : {"type": "string"},
    "array"  : {"type": "array"},
    "object" : {"type": "object"},
    "time"   : {"type": "number", "format": "time"},
    "any"    : {},
}

Type    = str | dict
NUMBERS = ("number", "integer")   # a time is a number too


def schema(type: Type | None) -> dict:
    """A type as a JSON Schema (None: any). ValueError for a name there isn't, or a schema that
    isn't one."""
    if type is None:            return {}
    if isinstance(type, str):
        if type in NAMES:       return NAMES[type]
        raise ValueError(f"no type {type!r}: {', '.join(NAMES)}, or a JSON Schema")
    if not isinstance(type, dict):
        raise ValueError(f"a type is a name or a JSON Schema ({type!r})")
    if (wrong := checked(json.dumps(type, sort_keys=True))) is not None:
        raise ValueError(f"not a JSON Schema: {wrong}")
    return type


@cache
def checked(said: str) -> str | None:
    """What's wrong with a schema (None: nothing), once for each."""
    try:
        Draft202012Validator.check_schema(json.loads(said))
    except SchemaError as e:
        return e.message
    return None


def typeof(value: Any) -> Type:
    """A constant's type, all it tells: an object's, with each of its fields'; an array's, with
    its items' if they're all of one (unknown: any)."""
    return short(described(value))


def oftype(value: Any, type: Type | None) -> bool:
    """Whether a value is of a type (unknown always is, inside an object or a list too)."""
    return value is None or validator(json.dumps(schema(type), sort_keys=True)).is_valid(known(value))


def known(value: Any) -> Any:
    """A value with its unknown fields and items left out: they fit whatever they'd be."""
    if isinstance(value, dict):         return {k: known(v) for k, v in value.items() if v is not None}
    if isinstance(value, list | tuple): return [known(v) for v in value if v is not None]
    return value


def described(value: Any) -> dict:
    """A constant's type, as a JSON Schema."""
    if isinstance(value, bool):                 return NAMES["boolean"]
    if isinstance(value, int | float):          return NAMES["number"]
    if isinstance(value, str):                  return NAMES["string"]
    if isinstance(value, dict):
        return {"type": "object", "properties": {str(k): described(v) for k, v in value.items()}} if value else NAMES["object"]
    if isinstance(value, list | tuple):
        items = {json.dumps(described(v), sort_keys=True) for v in value if v is not None}
        return {"type": "array", "items": json.loads(items.pop())} if len(items) == 1 else NAMES["array"]
    return NAMES["any"]

 
def field(type: Type, key: str) -> Type:
    """The type of a field of a value of `type`: an object's property's, a list of its items'
    for an array (its column: the items of each, one list, for a field that's a list), else any."""
    made = schema(type)
    if made.get("type") == "array":
        inner = field(itemof(made), key)
        return inner if schema(inner).get("type") == "array" else listof(inner)
    if made.get("type") == "object":    return short(made.get("properties", {}).get(key, {}))
    return "any"


def itemof(type: Type) -> Type:
    """The type of an item of a value of `type` (an array's, else any)."""
    made = schema(type)
    return short(made.get("items", {})) if made.get("type") == "array" else "any"


def listof(type: Type) -> Type:
    """An array of items of `type` (any: an array)."""
    made = schema(type)
    return short({"type": "array", "items": made}) if made else "array"


def short(type: Type) -> Type:
    """A type said by its name, if it has one (a schema, else)."""
    made = schema(type)
    return next((name for name, known in NAMES.items() if known == made), made)


def accept(type: Type | None, given: Type | None) -> bool:
    """Whether what's of type `given` can be what's of `type`, as far as types tell: either
    unknown (any), numbers of any kind (a time, a whole number), the same kind, an object
    whose fields both have do, an array whose items do."""
    made, said = schema(type), schema(given)
    if not made or not said or made == said:  return True
    kinds = made.get("type"), said.get("type")
    if all(kind in NUMBERS for kind in kinds):  return True
    if kinds[0] != kinds[1]:                    return False
    if kinds[0] == "object":
        mine, theirs = made.get("properties", {}), said.get("properties", {})
        return all(accept(mine[key], theirs[key]) for key in mine.keys() & theirs.keys())
    if kinds[0] == "array":
        return accept(made.get("items"), said.get("items"))
    return True


def typename(type: Type | None) -> str:
    """A type, said short: its name, else the name of what it is (an object with fields: object),
    else "schema"."""
    kind = schema(type).get("type")
    return named if isinstance(named := short(type), str) else kind if isinstance(kind, str) and kind in NAMES else "schema"


@cache
def validator(said: str) -> Draft202012Validator:
    return Draft202012Validator(json.loads(said))
