"""Specs: what you write for each node of the programs, one dataclass per kind.

    InputSpec      a primitive the programs read
    VariableSpec   app state, global or a program's or a state's
    SignalSpec     a named expression, global or a program's or a state's
    RuleSpec       a soft comparison, global or a program's or a state's
    ProgramSpec    a state machine
    StateSpec      one of its states
    BranchSpec     one way out of a state, in order
    ActionSpec     one action a state takes as it's entered, in order

A spec keeps what you wrote, as you wrote it. Names stay short: a way out of state
`asking` of program `suggest` says `answer == 0`, and only when the programs are built
does `answer` become `suggest.asking.answer` (model/build.py).

Each kind is a class, found by its name in `Spec.kinds` ("rule" → RuleSpec), and each
moves between JSON and Python the same way:

    RuleSpec.parse(data)    JSON → a RuleSpec, its fields checked: none unknown, none
                            missing, each of its type (`Hint`). ConfigError if not
    RuleSpec.schema()       those same checks, as JSON Schema: what the tools show the UI
                            or an LLM, so they know what to send
    rule.json()             a RuleSpec → JSON (for the database, and the tools' answers)

Whether a spec makes sense (an expression that reads an unknown name, a rule that
compares nothing) is up to core/, when it's built.

Where a variable, a signal or a rule lives (`scope`), and who owns it (`program`): a global
one may be brought by a program, and goes with it.

    scope "global"    program: the program that brings it, or none
    scope "program"   program: its program
    scope "state"     program and state: its state
"""

from __future__ import annotations

import types
import typing
import uuid
from dataclasses import MISSING, Field, dataclass, field, fields
from typing import Any, ClassVar, Literal

from proki.utils import ident
from proki.errors import (
    Inside,
    ConfigError,
    ProgramError,
    RuleError,
    SignalError,
    VariableError
)

ScopeName = Literal["global", "program", "state"]
Compare   = Literal["gt", "ge", "lt", "le", "eq", "ne"]  # core/rules.py: COMPARE


class Hint:
    """A field's type (its hint), as JSON has it: what fits it, how a mistake says it, and
    how JSON Schema writes it."""

    @staticmethod
    def fits(value: Any, hint: Any) -> bool:
        """Whether `value`, from JSON, is of the type `hint`."""
        origin, args = typing.get_origin(hint), typing.get_args(hint)
        if origin is Literal:                               return value in args
        if origin in (typing.Union, types.UnionType):       return any(Hint.fits(value, a) for a in args)
        if origin is list:                                  return isinstance(value, list) and all(Hint.fits(v, args[0]) for v in value)
        if origin is dict:                                  return isinstance(value, dict)
        if hint is type(None):                              return value is None
        if hint is Any:                                     return True
        if hint is bool:                                    return isinstance(value, bool)
        if hint is float:                                   return isinstance(value, int | float) and not isinstance(value, bool)
        if hint is int:                                     return isinstance(value, int) and not isinstance(value, bool)
        return isinstance(value, hint)

    @staticmethod
    def shown(hint: Any) -> str:
        """The type, as a mistake says it: "a number", "one of gt, ge, ..."."""
        origin, args = typing.get_origin(hint), typing.get_args(hint)
        if origin is Literal:                               return f"one of {', '.join(map(str, args))}"
        if origin in (typing.Union, types.UnionType):       return " or ".join(Hint.shown(a) for a in args)
        if origin is list:                                  return f"a list of {Hint.shown(args[0]).removeprefix('a ')}s"
        return {
            str         : "a text",
            float       : "a number",
            int         : "a whole number",
            bool        : "true or false",
            type(None)  : "null",
            dict        : "an object",
        }.get(origin or hint, "anything")

    @staticmethod
    def typed(hint: Any) -> dict:
        """The type, as JSON Schema."""
        origin, args = typing.get_origin(hint), typing.get_args(hint)
        if origin is Literal:                               return {"enum": list(args)}
        if origin in (typing.Union, types.UnionType):       return {"anyOf": [Hint.typed(a) for a in args]}
        if origin is list:                                  return {"type": "array", "items": Hint.typed(args[0])}
        if origin is dict:                                  return {"type": "object"}
        if hint is Any:                                     return {}
        return {"type": {
            str         : "string",
            float       : "number",
            int         : "integer",
            bool        : "boolean",
            type(None)  : "null",
        }[hint]}


def doc(text: str) -> Any:
    """A field's description, for its schema."""
    return {"doc": text}


@dataclass(frozen=True, kw_only=True)
class Spec:
    """What every spec shares: its `KIND` ("input", "variable", ...), what it is (`DOCS`),
    the error a mistake in it raises (`ERROR`), and its `key`, unique among the specs of its
    kind (None for a branch or an action: they're found by their place among their state's)."""

    KIND    : ClassVar[str] = ""
    DOCS    : ClassVar[str] = ""
    ERROR   : ClassVar[type[ConfigError]] = ProgramError                        # errors/config.py
    NAMES   : ClassVar[tuple[str, ...]]   = ("name", "program", "state", "goto")  # the fields that name something

    kinds: ClassVar[dict[str, type[Spec]]] = {}  # every kind, by its KIND

    def __init_subclass__(cls, **kwargs: Any):
        super().__init_subclass__(**kwargs)
        if cls.KIND:
            Spec.kinds[cls.KIND] = cls

    # --- what a spec says of itself -----------------------------------------------------------

    def key(self) -> tuple | None:
        return None

    def owner(self) -> str | None:
        """The program it goes with (removed with it), if any."""
        return getattr(self, "program", None)

    def where(self) -> str:
        """Where it is, to say in a mistake: "rule 'focus_high'", "suggest.asking: way out to 'idle'"."""
        raise NotImplementedError

    def inside(self) -> Inside:
        """A mistake made inside is said to be at this spec (`where`)."""
        return Inside(self.where())

    def json(self, short: bool = False) -> dict:
        """The spec as JSON: {field: value}, what `parse` takes. `short`: without the fields
        left as they start (what `parse` gives them anyway)."""
        return {
            f.name: getattr(self, f.name) for f in fields(self)
            if not short or getattr(self, f.name) != Spec.start(f)
        }

    # --- its fields ---------------------------------------------------------------------------

    @staticmethod
    def needed(f: Field) -> bool:
        """Whether a field has to be given (it has no default)."""
        return f.default is MISSING and f.default_factory is MISSING

    @staticmethod
    def start(f: Field) -> Any:
        """A field's default, what it starts as (MISSING: it has none)."""
        return f.default_factory() if f.default_factory is not MISSING else f.default

    # --- from JSON ----------------------------------------------------------------------------

    @classmethod
    def parse(cls, data: Any) -> Spec:
        """A `cls` from JSON `data`, its shape checked: `ERROR` for an unknown field, a
        missing one, one of the wrong type, or a name that can't name anything."""
        known = {f.name: f for f in fields(cls)}
        if not isinstance(data, dict):
            raise cls.ERROR(f"a {cls.KIND} is {{{', '.join(known)}}} ({data!r})")

        title = f"{cls.KIND} {data['name']!r}" if isinstance(data.get("name"), str) else f"a {cls.KIND}"
        hints = typing.get_type_hints(cls)

        if unknown := set(data) - set(known):
            raise cls.ERROR(f"{title}: unknown {', '.join(sorted(unknown))} ({', '.join(known)})")
        for key, f in known.items():
            if key not in data and Spec.needed(f):
                raise cls.ERROR(f"{title}: {key} is missing")
            if key in data and not Hint.fits(data[key], hints[key]):
                raise cls.ERROR(f"{title}: {key} is {Hint.shown(hints[key])} ({data[key]!r})")

        spec = cls(**{key: data[key] for key in known if key in data})

        for field in cls.NAMES:
            value = getattr(spec, field, None)
            if value is not None and not ident(value):
                raise cls.ERROR(
                    f"{cls.KIND} {field} {value!r}: a name is letters, "
                    f"digits and _, not starting with a digit"
                )

        return spec

    @classmethod
    def schema(cls) -> dict:
        """The shape `parse` checks, as JSON Schema: each field's type and description, and
        the ones it needs."""
        hints = typing.get_type_hints(cls)
        return {
            "type"                  : "object",
            "description"           : cls.DOCS,
            "properties"            : {f.name: {**Hint.typed(hints[f.name]), "description": f.metadata.get("doc", "")}
                                     for f in fields(cls)},
            "required"              : [f.name for f in fields(cls) if Spec.needed(f)],
            "additionalProperties"  : False,
        }


@dataclass(frozen=True, kw_only=True)
class InputSpec(Spec):
    KIND : ClassVar[str] = "input"
    DOCS : ClassVar[str] = "A primitive the programs read (core/primitives/), by its name."
    ERROR: ClassVar[type[ConfigError]] = SignalError

    name        : str          = field(metadata=doc("the primitive's name: app, keys, clock, ..."))
    backfill    : float | None = field(default=None, metadata=doc("minutes of itself it keeps as a table (none if left out)"))

    def key(self) -> tuple:
        return (self.name,)

    def where(self) -> str:
        return f"input {self.name!r}"


@dataclass(frozen=True, kw_only=True)
class Scoped(Spec):
    """A variable, a signal or a rule: its `name`, in its `scope`."""

    name    : str        = field(metadata=doc("its name in its scope, a name as in Python"))
    desc    : str        = field(default="", metadata=doc("what it's for, in a line"))
    scope   : ScopeName  = field(default="global", metadata=doc("where it's found: global, its program's, or its state's"))
    state   : str | None = field(default=None, metadata=doc("its state (scope state)"))
    program : str | None = field(default=None, metadata=doc("its program (scope program or state), or the one that brings a global one"))

    def __post_init__(self) -> None:
        needs = {
            "global"    : not self.state,
            "program"   : self.program and not self.state,
            "state"     : self.program and self.state,
        }
        takes = {
            "global"    : "no state (a program, if one brings it)",
            "program"   : "its program, and no state",
            "state"     : "its program and its state",
        }
        if not needs[self.scope]:
            raise ConfigError(f"{self.KIND} {self.name!r}: scope {self.scope} takes {takes[self.scope]}")

    def key(self) -> tuple:
        return (self.full(),)

    def full(self) -> str:
        """Its full name: suggest.asking.answer, suggest.left, count."""
        return {
            "global" : "",
            "program": f"{self.program}.",
            "state"  : f"{self.program}.{self.state}.",
        }[self.scope] + self.name

    def where(self) -> str:
        return f"{self.KIND} {self.full()!r}"


@dataclass(frozen=True, kw_only=True)
class VariableSpec(Scoped):
    KIND : ClassVar[str] = "variable"
    DOCS : ClassVar[str] = ("App state, set by actions. A global one is kept across restarts, a program's starts over "
                            "with the program, a state's when the state is left.")
    ERROR: ClassVar[type[ConfigError]] = VariableError

    value: bool | float | str | None = field(default=None, metadata=doc(
        "where it starts: a number, true / false, null, or an expression worked out on its first cycle"))


@dataclass(frozen=True, kw_only=True)
class SignalSpec(Scoped):
    KIND : ClassVar[str] = "signal"
    DOCS : ClassVar[str] = ("A named expression over inputs, variables and other signals, global or a program's or a "
                            "state's (reading what's seen from there).")
    ERROR: ClassVar[type[ConfigError]] = SignalError

    expr    : str          = field(metadata=doc("what it is: an expression, e.g. ts_mean(keys, 5)"))
    backfill: float | None = field(default=None, metadata=doc("minutes of itself it keeps as a table (none if left out)"))
    persist : bool         = field(default=False, metadata=doc("the table is saved too, across restarts (a metric). Needs a backfill"))


@dataclass(frozen=True, kw_only=True)
class RuleSpec(Scoped):
    KIND : ClassVar[str] = "rule"
    DOCS : ClassVar[str] = "A soft comparison of two expressions: the chance of firing now (core/rules.py)."
    ERROR: ClassVar[type[ConfigError]] = RuleError

    lhs     : str | float = field(metadata=doc("the left side, an expression"))
    cmp     : Compare     = field(metadata=doc("how the sides compare"))
    rhs     : str | float = field(metadata=doc("the right side, an expression"))
    softness: float       = field(default=0.0, metadata=doc("how soft the comparison is (0: hard)"))
    level   : int         = field(default=1, metadata=doc("rules vote by level, the highest first"))


@dataclass(frozen=True, kw_only=True)
class ProgramSpec(Spec):
    KIND : ClassVar[str] = "program"
    DOCS : ClassVar[str] = "A state machine. It starts in its initial state."

    name   : str       = field(metadata=doc("its name, a name as in Python"))
    desc   : str       = field(default="", metadata=doc("what it's for, in a line"))
    tags   : list[str] = field(default_factory=list, metadata=doc("words to find it by"))
    initial: str       = field(default="idle", metadata=doc("the state it starts in"))

    def __post_init__(self) -> None:
        if not all(self.tags):
            raise ConfigError(f"program {self.name!r}: a tag is a word ({self.tags!r})")

    def key(self) -> tuple:
        return (self.name,)

    def owner(self) -> str | None:
        return self.name

    def where(self) -> str:
        return f"program {self.name!r}"


@dataclass(frozen=True, kw_only=True)
class StateSpec(Spec):
    KIND : ClassVar[str] = "state"
    DOCS : ClassVar[str] = ("A state of a program: it takes its actions as it's entered, then every `every` minutes "
                            "tries its ways out, in order. None: back to the program's initial state.")

    program: str   = field(metadata=doc("its program"))
    name   : str   = field(metadata=doc("its name, a name as in Python"))
    desc   : str   = field(default="", metadata=doc("what it's waiting for, in a line"))
    every  : float = field(default=1.0, metadata=doc("minutes between tries of its ways out"))

    def key(self) -> tuple:
        return (self.program, self.name)

    def where(self) -> str:
        return f"{self.program}.{self.name}"


@dataclass(frozen=True, kw_only=True)
class BranchSpec(Spec):
    """A way out. Its place among its state's is the order of the specs."""

    KIND : ClassVar[str] = "branch"
    DOCS : ClassVar[str] = ("One way out of a state, tried in order: all its conditions must be true, then its rules "
                            "vote. Neither: it always passes (the else, last).")

    program: str       = field(metadata=doc("its program"))
    state  : str       = field(metadata=doc("the state it leaves"))
    goto   : str       = field(metadata=doc("the state it goes to, of the same program"))
    when   : list[str] = field(default_factory=list, metadata=doc("rules (by name) and conditions (expressions). Empty: always (the else)"))
    desc   : str       = field(default="", metadata=doc("why it's taken, in a line"))

    def where(self) -> str:
        return f"{self.program}.{self.state}: way out to {self.goto!r}"


@dataclass(frozen=True, kw_only=True)
class ActionSpec(Spec):
    """An action. Its place among its state's is the order of the specs."""

    KIND : ClassVar[str] = "action"
    DOCS : ClassVar[str] = "One action a state takes as it's entered, in order (core/actions/): its kind, and its params."

    id     : str            = field(default_factory=lambda: uuid.uuid4().hex[:8],
                                    metadata=doc("what it's known by: the media library keeps its picks by it"))
    program: str            = field(metadata=doc("its program"))
    state  : str            = field(metadata=doc("its state"))
    kind   : str            = field(metadata=doc("set, add, sub, ask, poke, lock, open"))
    params : dict[str, Any] = field(default_factory=dict, metadata=doc("the kind's params, by name"))

    def where(self) -> str:
        return f"{self.program}.{self.state}: {self.kind}"
