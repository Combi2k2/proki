"""The programs as JSON files, the way proki ships them, made into specs (model/specs.py).

    main.json      {"cycle", "inputs", "variables", "signals", "rules"}: the global scope
    <name>.json    {"desc", "tags", "variables", "signals", "rules", "program"}: a program,
                   and the global variables, signals and rules it brings

    {"program": {"initial": "idle", "variables": [...], "signals": [...], "rules": [...], "states": {
        "idle":   {"desc": "...", "every": 0.1, "next": [{"goto": "asking", "when": ["focus_high"]}]},
        "asking": {"variables": [...], "do": [{"ask": {...}}], "next": "idle"}}}}

    Defaults(folder).specs(names)     main.json and the program files, as specs
    Defaults.parse(main, programs)    JSON already read, as specs
    Defaults.dump(specs, program)     the way back: a program's file (None: main.json)

A global variable may be declared in several files: it's one variable, and a declaration
with a "value" gives its starting value. A state's "do" is a list of actions, each {kind:
params} and its "id" if it has one to keep (else it's given one). Its "next" is a state (one
way out, always taken) or a list of ways out, each "when" a rule or a condition, or a list
of them.

A file's shape is checked as each spec is made (`Spec.parse`), and a mistake names the file.
Whether they make sense is checked when they're built (model/build.py).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, ClassVar

from proki.errors import ConfigError, Inside
from proki.model.build import Specs
from proki.model.specs import (
    ActionSpec,
    BranchSpec,
    InputSpec,
    ProgramSpec,
    RuleSpec,
    SignalSpec,
    Spec,
    StateSpec,
    VariableSpec
)


class Defaults:
    MAIN        : ClassVar[str]      = "main.json"
    MAIN_KEYS   : ClassVar[set[str]] = {"cycle", "inputs", "variables", "signals", "rules"}
    FILE_KEYS   : ClassVar[set[str]] = {"desc", "tags", "variables", "signals", "rules", "program"}
    PROG_KEYS   : ClassVar[set[str]] = {"initial", "variables", "signals", "rules", "states"}
    STATE_KEYS  : ClassVar[set[str]] = {"desc", "variables", "signals", "rules", "do", "every", "next"}
    SCOPED      : ClassVar[dict[str, type[Spec]]] = {    # what each scope may declare
        "variables": VariableSpec,
        "signals"  : SignalSpec,
        "rules"    : RuleSpec,
    }

    def __init__(self, folder: Path):
        self.folder = folder

    def specs(self, names: set[str] | None = None) -> Specs:
        """main.json and the program files (`names`: which programs, all of them by default)."""
        files = sorted(p for p in self.folder.glob("*.json") if p.name != self.MAIN)
        files = filter(lambda p: names is None or p.stem in names, files)
        return self.parse(self.read(self.folder / self.MAIN), {p.stem: self.read(p) for p in files})

    def read(self, path: Path) -> dict:
        """A file's JSON. ConfigError naming the file, and the line of a mistake."""
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as e:
            raise ConfigError(f"not JSON: {e.msg} (line {e.lineno})", path.name) from None
        if not isinstance(data, dict):  raise ConfigError("it's an object: {...}", path.name)
        return data

    # --- JSON into specs ----------------------------------------------------------------------

    @classmethod
    def parse(cls, main: dict, programs: dict[str, dict]) -> Specs:
        """The specs main.json (`main`) and the program files (`programs`, by name) make."""
        specs = Specs()
        with Inside(cls.MAIN):
            cls.check_key(main, cls.MAIN_KEYS, "a section")
            specs.cycle   = main.get("cycle", 10)
            specs.inputs += [InputSpec.parse(e) for e in cls.get_list(main, "inputs")]
            cls.parse_globals(specs, main)
        for name, file in programs.items():
            with Inside(f"{name}.json"):
                cls.parse_program(specs, name, file)
        return specs

    @classmethod
    def parse_globals(cls, specs: Specs, data: dict, program: str | None = None) -> None:
        """A file's global variables, signals and rules (brought by `program`, if any)."""
        owner = {} if program is None else {"program": program}
        for entry in cls.get_list(data, "variables"):
            spec = VariableSpec.parse({**entry, **owner})
            same = [i for i, v in enumerate(specs.variables) if v.scope == "global" and v.name == spec.name]
            if not same:            specs.variables.append(spec)
            elif "value" in entry:  specs.variables[same[0]] = spec    # declared again, with a starting value
        cls.parse_scoped(specs, data, owner, "signals", "rules")

    @classmethod
    def parse_program(cls, specs: Specs, name: str, file: dict) -> None:
        """A program's file: what it brings, the program, its states."""
        cls.check_key(file, cls.FILE_KEYS, "a section")
        cls.parse_globals(specs, file, name)

        body = file.get("program", {})
        if not isinstance(body, dict):
            raise ConfigError(f"program is {{{', '.join(sorted(cls.PROG_KEYS))}}} ({body!r})")
        cls.check_key(body, cls.PROG_KEYS, "program")
        specs.programs.append(ProgramSpec.parse({
            "name"   : name,
            "desc"   : file.get("desc", ""),
            "tags"   : file.get("tags", []),
            "initial": body.get("initial", ""),
        }))
        cls.parse_scoped(specs, body, {"scope": "program", "program": name})

        states = body.get("states", {})
        if not isinstance(states, dict):
            raise ConfigError(f"states is {{name: state}} ({states!r})")
        for state, data in states.items():
            with Inside(f"{name}.{state}"):
                cls.parse_state(specs, name, state, data)

    @classmethod
    def parse_state(cls, specs: Specs, program: str, name: str, body: Any) -> None:
        """A state: its own variables, signals and rules, its actions, its ways out."""
        if not isinstance(body, dict):
            raise ConfigError(f"a state is {{{', '.join(sorted(cls.STATE_KEYS))}}} ({body!r})")
        cls.check_key(body, cls.STATE_KEYS, "a state")
        specs.states.append(StateSpec.parse({
            "program": program,
            "name"   : name,
            "desc"   : body.get("desc", ""),
            "every"  : body.get("every", 1),
        }))

        at = {"program": program, "state": name}
        cls.parse_scoped(specs, body, {"scope": "state", **at})
        cls.parse_actions(specs, body, at)
        cls.parse_branches(specs, body, at)

    @classmethod
    def parse_actions(cls, specs: Specs, body: dict, at: dict) -> None:
        """A state's "do": a list of actions, each {kind: params} and its id."""
        for i, entry in enumerate(cls.get_list(body, "do")):
            act = dict(entry) if isinstance(entry, dict) else {}
            id  = {"id": act.pop("id")} if "id" in act else {}
            kind, params = next(iter(act.items()), (None, None))
            if len(act) != 1 or not isinstance(params, dict):
                raise ConfigError(f"do[{i}]: an action is {{kind: {{params}}}}, and its id if it has one ({entry!r})")

            specs.actions.append(ActionSpec.parse({**at, "kind": kind, "params": params, **id}))

    @classmethod
    def parse_branches(cls, specs: Specs, body: dict, at: dict) -> None:
        """A state's "next": a state (one way out, always taken), or a list of ways out."""
        ways = body.get("next")
        if ways is None:           return
        if isinstance(ways, str):  ways = [{"goto": ways}]
        if not isinstance(ways, list) or not ways:
            raise ConfigError(f"next is a state, or a list of {{goto, when, desc}} ({ways!r})")

        for i, way in enumerate(ways):
            if not isinstance(way, dict):
                raise ConfigError(f"next[{i}]: a way out is {{goto, when, desc}} ({way!r})")

            when = way.get("when", [])
            specs.branches.append(BranchSpec.parse({
                **at,
                **way,
                "when": [when] if isinstance(when, str) else when,
            }))

    @classmethod
    def parse_scoped(cls, specs: Specs, data: dict, mine: dict, *kinds: str) -> None:
        """A section's variables, signals and rules (`kinds`: only these), each `mine`."""
        for kind in kinds or cls.SCOPED:
            getattr(specs, kind).extend(cls.SCOPED[kind].parse({**e, **mine}) for e in cls.get_list(data, kind))

    # --- specs back into JSON -----------------------------------------------------------------

    @classmethod
    def dump(cls, specs: Specs, program: str | None = None) -> dict:
        """The file `specs` make for `program` (None: main.json): what `parse` reads back."""
        if program is None:
            return {
                "cycle" : specs.cycle,
                "inputs": [cls.dump_spec(s) for s in specs.inputs],
                **cls.dump_scoped(specs, "global"),
            }

        spec   = next(p for p in specs.programs if p.name == program)
        states = {s.name: cls.dump_state(specs, s) for s in specs.states if s.program == program}
        return {
            **cls.dump_spec(spec, "name", "initial"),
            **cls.dump_scoped(specs, "global", program),
            "program": {
                "initial": spec.initial,
                **cls.dump_scoped(specs, "program", program),
                "states" : states,
            },
        }

    @classmethod
    def dump_state(cls, specs: Specs, state: StateSpec) -> dict:
        """A state as its program's file writes it (what's empty left out)."""
        here = lambda s: (s.program, s.state) == (state.program, state.name)
        body = {
            "desc" : state.desc,
            **cls.dump_scoped(specs, "state", state.program, state.name),
            "do"   : [{a.kind: a.params} for a in specs.actions if here(a)],
            "every": state.every,
            "next" : [cls.dump_spec(b) for b in specs.branches if here(b)],
        }
        return {k: v for k, v in body.items() if v not in ("", [])}

    @classmethod
    def dump_scoped(cls, specs: Specs, scope: str, program: str | None = None, state: str | None = None) -> dict:
        """The variables, signals and rules a scope declares (a global's `program`: the file
        that brings it), the empty ones left out."""
        found = {kind: [cls.dump_spec(s) for s in getattr(specs, kind)
                        if (s.scope, s.program, s.state) == (scope, program, state)] for kind in cls.SCOPED}
        return {kind: entries for kind, entries in found.items() if entries}

    @staticmethod
    def dump_spec(spec: Spec, *without: str) -> dict:
        """A spec as an entry of its file: what its place says (scope, program, state),
        what's left as it starts, and `without`, left out."""
        implied = {"scope", "program", "state", *without}
        return {key: value for key, value in spec.json(short=True).items() if key not in implied}

    # --- helpers ------------------------------------------------------------------------------

    @staticmethod
    def get_list(data: dict, name: str) -> list:
        """The section `name`, a list (left out: empty)."""
        value = data.get(name)
        if value is None:                return []
        if not isinstance(value, list):  raise ConfigError(f"{name} is a list ({value!r})")
        return value

    @staticmethod
    def check_key(data: dict, keys: set[str], what: str) -> None:
        """ConfigError for a section `data` doesn't take (`keys`: the ones it does)."""
        if unknown := set(data) - keys:
            raise ConfigError(f"{what}: unknown {', '.join(sorted(unknown))} ({', '.join(sorted(keys))})")
