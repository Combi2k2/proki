"""The programs' model: their specs, and the changes made to them.

    model.add("rule", {"name": "late", "lhs": "clock", "cmp": "gt", "rhs": 1320})
    model.update("state", {"program": "suggest", "name": "idle"}, {"every": 2})
    model.remove("program", {"name": "suggest"})
    model.apply([("add", "state", {...}), ("add", "branch", {...})])    all of them, or none
    model.swap("suggest", specs)                                        a whole program at once

Each change is made on a copy of the specs (`added`, `updated`, `removed`, `swapped`),
built aside (`check`, the engine's: what runs isn't touched), and kept only if it builds
(`keep`). So the model always holds programs that run, and a mistake (ConfigError) says
where it is.

Which spec a change means (`locate`):

    input, program            {"name"}
    variable, signal, rule    {"name", "scope", "program", "state"}: scope global by default
    state                     {"program", "name"}
    branch, action            {"program", "state", "at"}: its place among its state's, from 0

Adding a branch or an action puts it last among its state's, or `at` a place (`place`). A
new program comes with its initial state ("idle" by default), which waits and stays.

An action keeps its id as it changes or moves (removed, then added with it), and a program
swapped in takes the ids of the actions in their places (`carry`): the media library keeps
a poke's or a question's pictures and sounds by it.

Removing takes what it owns too: a program its states, their ways out and actions, its own
and its states' variables, signals and rules, and the global ones it brings. A state its
ways out, actions, variables, signals and rules. What something else still reads stops
it, and the check says what.

Renaming a program or a state renames it in what it owns. What reads it by name (an
expression, a `goto`, a program's initial state) isn't rewritten: the check says what
still reads the old name.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import fields, replace
from typing import Any, ClassVar

from proki.errors import ConfigError
from proki.model.build import Specs
from proki.model.specs import (
    ActionSpec,
    InputSpec,
    ProgramSpec,
    Scoped,
    Spec,
    StateSpec
)

Op = tuple[str, str, dict]  # ("add" | "update" | "remove", kind, data), as `apply` takes them


class Model:
    LISTS : ClassVar[dict[str, str]] = {    # each kind's list in the specs
        "input"   : "inputs",
        "variable": "variables",
        "signal"  : "signals",
        "rule"    : "rules",
        "program" : "programs",
        "state"   : "states",
        "branch"  : "branches",
        "action"  : "actions",
    }
    OPS   : ClassVar[dict[str, str]] = {    # each change, and the method that makes it on a copy
        "add"     : "added",
        "update"  : "updated",
        "remove"  : "removed",
    }
    PLACED: ClassVar[set[str]] = {"branch", "action"}  # found by their place among their state's

    def __init__(
        self,
        specs  : Specs,
        check  : Callable[[Specs], None] = lambda specs: None,
        changed: Callable[[Specs], None] = lambda specs: None,
    ):
        """The model of `specs`. `check` builds specs aside (ConfigError for a mistake),
        `changed` is told the specs a change keeps (the engine runs them)."""
        self.specs   = specs
        self.check   = check
        self.changed = changed

    # --- changes ------------------------------------------------------------------------------

    def add(self, kind: str, data: dict) -> dict:
        return self.apply([("add", kind, data)])[0]

    def update(self, kind: str, ident: dict, changes: dict) -> dict:
        return self.apply([("update", kind, {**ident, "changes": changes})])[0]

    def remove(self, kind: str, ident: dict) -> list[dict]:
        return self.apply([("remove", kind, ident)])[0]

    def apply(self, ops: Iterable[Op]) -> list:
        """Every change in `ops`, in order, then checked once: all of them are kept, or none.
        What each gives: the spec added or updated, or the ones removed (as JSON)."""
        specs, done = self.specs.copy(), []
        for op, kind, data in ops:
            if kind not in Spec.kinds:      raise ConfigError(f"no kind {kind!r} ({', '.join(Spec.kinds)})")
            if op not in self.OPS:          raise ConfigError(f"no change {op!r} ({', '.join(self.OPS)})")
            if not isinstance(data, dict):  raise ConfigError(f"{op} {kind}: its data is an object ({data!r})")
            try:
                done.append(getattr(self, self.OPS[op])(specs, kind, dict(data)))
            except ConfigError as e:
                raise e.within(f"{op} {kind}") from None
        self.keep(specs)
        return done

    def swap(self, program: str | None | list[str | None], part: Specs | list[Specs]) -> None:
        """`program`'s specs replaced by `part`, what its file makes (model/defaults.py):

            swap("suggest", part)                   a program
            swap(None, part)                        the global scope (main.json)
            swap(["suggest", "day"], [p, q])        several: kept together, or none
        """
        progs, parts = (program, part) if isinstance(program, list) else ([program], [part])
        specs = self.specs.copy()
        for prog, part in zip(progs, parts, strict=True):
            self.swapped(specs, prog, part)
        self.keep(specs)

    def keep(self, specs: Specs) -> None:
        """`specs`, checked, in place of these, and told to who runs them (`changed`)."""
        self.check(specs)
        self.specs = specs
        self.changed(specs)

    # --- reading ------------------------------------------------------------------------------

    def get(self, kind: str, ident: dict) -> dict:
        """The spec `ident` means, as JSON."""
        return self.group(self.specs, kind)[self.locate(self.specs, kind, ident)].json()

    def all(self, kind: str, **where: Any) -> list[dict]:
        """The specs of `kind`, as JSON, those whose fields are as `where` says."""
        return [s.json() for s in self.group(self.specs, kind) if all(getattr(s, k, None) == v for k, v in where.items())]

    # --- each change, made on a copy (in place) -----------------------------------------------

    def added(self, specs: Specs, kind: str, data: dict) -> dict:
        """A new spec of `kind`, from `data` (and `at`, a branch's or an action's place)."""
        if kind == "action" and "name" not in data:  # its kind's, as free among its state's: "ask", "ask_2", ...
            taken = [a.name for a in specs.actions if (a.program, a.state) == (data.get("program"), data.get("state"))]
            data  = {**data, "name": ActionSpec.free(str(data.get("kind")), taken)}
        at    = data.pop("at", None) if kind in self.PLACED else None
        spec  = Spec.kinds[kind].parse(data)
        group = self.group(specs, kind)
        self.unique(spec, group)

        if kind in self.PLACED:  group.insert(self.place(group, spec, at), spec)
        else:                    group.append(spec)
        if isinstance(spec, ProgramSpec) and not any((s.program, s.name) == (spec.name, spec.initial) for s in specs.states):
            specs.states.append(StateSpec(program=spec.name, name=spec.initial))  # its initial state: waits, and stays
        return spec.json()

    def updated(self, specs: Specs, kind: str, data: dict) -> dict:
        """The spec `data` means, with its `changes`. Renamed, a program or a state renames
        what it owns."""
        changes = data.pop("changes", {})
        if not isinstance(changes, dict):  raise ConfigError(f"changes is an object ({changes!r})")

        group = self.group(specs, kind)
        i     = self.locate(specs, kind, data)
        old   = group[i]
        new   = Spec.kinds[kind].parse({**old.json(), **changes})
        self.unique(new, [s for s in group if s is not old])

        group[i] = new
        if isinstance(old, ProgramSpec) and new.name != old.name:
            self.rename(specs, lambda s: s.owner() == old.name and s is not new, program=new.name)
        if isinstance(old, StateSpec) and new.name != old.name:
            self.rename(specs, lambda s: self.belong(s, old), state=new.name)
        return new.json()

    def removed(self, specs: Specs, kind: str, data: dict) -> list[dict]:
        """The spec `data` means, and what it owns."""
        spec = self.group(specs, kind).pop(self.locate(specs, kind, data))
        if isinstance(spec, ProgramSpec):    owned = lambda s: s.owner() == spec.name
        elif isinstance(spec, StateSpec):    owned = lambda s: self.belong(s, spec)
        else:                                owned = lambda s: False

        gone = [spec]
        for name in Specs.ORDER:
            gone += [s for s in getattr(specs, name) if owned(s)]
            setattr(specs, name, [s for s in getattr(specs, name) if not owned(s)])
        return [s.json() for s in gone]

    def swapped(self, specs: Specs, program: str | None, part: Specs) -> None:
        """`program`'s specs, `part`'s in their place (`swap`)."""
        if program is None:
            mine = lambda s: isinstance(s, InputSpec) or (isinstance(s, Scoped) and s.scope == "global" and s.program is None)
            specs.cycle = part.cycle
        else:
            mine = lambda s: s.owner() == program

        at  = next((i for i, p in enumerate(specs.programs) if p.name == program), len(specs.programs))
        ids = self.carry([a for a in specs.actions if mine(a)], part.actions)
        for name in Specs.ORDER:
            kept = [s for s in getattr(specs, name) if not mine(s)]
            new  = [s for s in (ids if name == "actions" else getattr(part, name)) if mine(s)]
            if name == "programs":   kept[at:at] = new      # where it was
            elif program is None:    kept = new + kept      # the global scope first, as in main.json
            else:                    kept += new
            setattr(specs, name, kept)

    # --- helpers ------------------------------------------------------------------------------

    @staticmethod
    def locate(specs: Specs, kind: str, ident: dict) -> int:
        """Where the spec `ident` means is, in its list. ConfigError if there's none."""
        group = Model.group(specs, kind)
        if kind in Model.PLACED:
            at   = ident.get("at")
            mine = [i for i, s in enumerate(group) if (s.program, s.state) == (ident.get("program"), ident.get("state"))]
            if isinstance(at, bool) or not isinstance(at, int) or not 0 <= at < len(mine):
                raise ConfigError(f"{ident.get('program')}.{ident.get('state')} has no {kind} at {at!r} ({len(mine)} of them)")
            return mine[at]

        cls  = Spec.kinds[kind]
        need = {"scope": "global", "program": None, "state": None, **ident} if issubclass(cls, Scoped) else dict(ident)
        if unknown := set(need) - {f.name for f in fields(cls)}:
            raise ConfigError(f"a {kind} is found by its fields, not {', '.join(sorted(unknown))}")
        if issubclass(cls, Scoped) and need["scope"] == "global":  # a global one, whoever brings it
            found = [i for i, s in enumerate(group) if s.scope == "global" and s.name == need.get("name")]
        else:
            found = [i for i, s in enumerate(group) if all(getattr(s, k) == v for k, v in need.items())]
        if len(found) != 1:
            raise ConfigError(f"no {kind} {ident}" if not found else f"{ident} means {len(found)} {kind}s")
        return found[0]

    @staticmethod
    def unique(spec: Spec, others: list) -> None:
        """No other spec has `spec`'s key, nor (an action) its id. ConfigError if one does."""
        if spec.key() is not None and any(s.key() == spec.key() for s in others):
            raise ConfigError(f"{spec.where()} is there already")
        if isinstance(spec, ActionSpec) and any(s.id == spec.id for s in others):
            raise ConfigError(f"{spec.where()}: id {spec.id!r} is another action's")

    @staticmethod
    def belong(spec: Spec, state: StateSpec) -> bool:
        """Whether `spec` is `state`'s: one of its ways out, actions, variables, signals or rules."""
        return (getattr(spec, "program", None), getattr(spec, "state", None)) == (state.program, state.name)

    @staticmethod
    def rename(specs: Specs, which: Callable[[Spec], bool], **renamed: str) -> None:
        """The specs `which` says, with their fields `renamed` (a program's or a state's new name)."""
        for name in Specs.ORDER:
            setattr(specs, name, [type(s).parse({**s.json(), **renamed}) if which(s) else s for s in getattr(specs, name)])

    @staticmethod
    def place(group: list, spec: Any, at: Any) -> int:
        """Where a new branch or action goes in its list: last among its state's, or `at`."""
        mine = [i for i, s in enumerate(group) if (s.program, s.state) == (spec.program, spec.state)]
        last = mine[-1] + 1 if mine else len(group)
        if at is None:
            return last
        if isinstance(at, bool) or not isinstance(at, int) or not 0 <= at <= len(mine):
            raise ConfigError(f"at is a place from 0 to {len(mine)} ({at!r})")
        return mine[at] if at < len(mine) else last

    @staticmethod
    def carry(old: list[ActionSpec], new: list[ActionSpec]) -> list[ActionSpec]:
        """`new`, each with the id of the old action in its place (its state's, of its kind)."""
        mine = lambda a, acts: [b for b in acts if (b.program, b.state) == (a.program, a.state)]
        spot = lambda a, acts: (a.program, a.state, a.kind, mine(a, acts).index(a))
        ids  = {spot(a, old): a.id for a in old}
        return [replace(a, id=ids.get(spot(a, new), a.id)) for a in new]

    @staticmethod
    def group(specs: Specs, kind: str) -> list:
        """The list of `kind` in `specs` (the list itself: changing it changes them)."""
        return getattr(specs, Model.LISTS[kind])
