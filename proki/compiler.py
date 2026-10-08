"""Compiles proki's config (a JSON file) into what runs. `CONFIG` ships the defaults. The
app keeps an editable copy next to its config.

    "cycle":   10
        seconds between cycles (optional, 10 by default): every stream moves on once a cycle

    "inputs":  [{"name": "app", "backfill": 1440}, ...]
        the primitives read from ActivityWatch (core/primitives/), by name.
        `backfill`: how many minutes of itself it keeps as a table (none if left out)

    "variables": [{"name": "last_suggested", "value": null},
                  {"name": "deadline_eod", "value": "time - clock + 1440"}, ...]
        app state: a value actions and programs set (core/signals/variable.py), starting at
        `value` (a constant, or an expression worked out on its first cycle). Its latest
        value is kept across restarts

    "signals": [{"name": "keys_5m", "expr": "ts_mean(keys, 5)", "backfill": 60, "persist": false}, ...]
        a signal needs a name and an expr. The rest is optional: `backfill`, how many
        minutes of itself it keeps as a table (none if left out), like an input's.
        `persist`, the table is also saved (it needs a backfill)

    "rules":   [{"name": "focus_high", "lhs": "focus_5m", "cmp": "gt", "rhs": 0.5, "softness": 0.1,
                 "level": 1}, ...]
        a soft comparison of two expressions, the chance of firing now (core/rules.py).
        Rules vote by `level`, the highest first

    "programs": [{"name": "day", "initial": "idle", "states": {
                    "idle":    {"next": [{"goto": "new_day", "if": ["eod"]}]},
                    "new_day": {"do": [{"set": {"name": "deadline_eod", "expr": "deadline_eod + 1440"}}]}}}, ...]
        state machines running side by side (core/programs.py). Each state may take actions
        as it's entered ("do"), waits "every" minutes (1 by default), then takes its exit:
        "next" (a state, or if / elif / else branches, each "if" a list of rules or an
        expression), or none (back to "idle"). A question is an action ("ask"): its answer
        comes back later as a number in a variable, and "next" branches on it. Some programs are written in code
        (proki/programs/: "plan"). The config can read their variables, not name a program
        the same

Each program can have a file of its own, in `programs/` next to the config
(`programs/suggest.json`): the program, and the variables, signals and rules it brings

    {"variables": [...], "signals": [...], "rules": [...], "program": {"initial": "idle", "states": {...}}}

The program takes the file's name.

which count as if they were in the config (one namespace: a name is defined once, in
the config or in one file).

Variables are global: one declared again (in another state, or at the top) is the same
variable, and a declaration with a value gives its starting value. Every program starts
at its initial state and runs until proki stops. An expression can read the inputs, the
variables and the other signals, in any order.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from collections.abc import Iterable
from typing import Any

from proki.core.actions import Action
from proki.core.programs import IDLE, Branch, Program, State
from proki.core.rules import Rule
from proki.core.primitives import Primitive
from proki.core.signals import Signal, Stream, Variable
from proki.errors import ConfigError, ExprError, ProgramError

CONFIG = Path(__file__).resolve().parent / "assets" / "config.json"
PROGRAM_FILE = {"variables", "signals", "rules", "program"}
FIELDS = {
    "inputs": {"name", "backfill"},
    "variables": {"name", "value"},
    "signals": {"name", "expr", "backfill", "persist"},
    "rules": {"name", "lhs", "cmp", "rhs", "softness", "level"},
    "programs": {"name", "initial", "states"},
}
STATE_FIELDS = {"variables", "do", "every", "next"}


@dataclass
class Compiled:
    inputs: list[Primitive]
    variables: list[Variable]
    signals: list[Signal]
    rules: list[Rule]
    programs: list[Program]

    @property
    def streams(self) -> list[Stream]:
        return [*self.inputs, *self.variables, *self.signals]


def compile_config(path: Path = CONFIG, programs: Iterable[str] | None = None) -> Compiled:
    """What a config defines: streams (in `Stream.registry`), rules (`Rule.registry`) and
    programs (`Program.registry`), with its program files (`programs`: which ones, by name,
    all of them by default). Raises `ConfigError` on a mistake, naming the file and the entry (`where`)."""
    data = with_programs(json.loads(path.read_text()), path.parent / "programs", programs)
    if unknown := set(data) - set(FIELDS) - {"cycle"}:
        raise ConfigError(f"unknown section {', '.join(sorted(unknown))}", path.name)
    cycle = data.get("cycle", 10)
    if isinstance(cycle, bool) or not isinstance(cycle, int | float) or cycle <= 0:
        raise ConfigError(f"cycle is in seconds ({cycle!r})", path.name)
    Stream.cycle = timedelta(seconds=cycle)
    names: set[str] = set()

    def named(entry: dict, section: str) -> str:
        name = entry.get("name")
        if not name:
            raise ConfigError(f"an entry of {section} needs a name ({entry})", path.name)
        if name in names:
            raise ConfigError(f"{name!r} is defined twice", path.name)
        if unknown := set(entry) - FIELDS[section]:
            raise ConfigError(f"{name!r}: unknown {', '.join(sorted(unknown))}", path.name)
        names.add(name)
        return name

    def minutes(entry: dict, what: str) -> float | None:
        """An entry's `backfill`: minutes, or None if left out."""
        backfill = entry.get("backfill")
        if backfill is not None and (isinstance(backfill, bool) or not isinstance(backfill, int | float) or backfill <= 0):
            raise ConfigError(f"{what}: backfill is in minutes ({backfill!r})", path.name)
        return backfill

    inputs: list[Primitive] = []
    for spec in data.get("inputs", []):
        name = named(spec, "inputs")
        if name not in Primitive.kinds:
            raise ConfigError(f"no input is called {name!r} ({', '.join(Primitive.kinds)})", path.name)
        backfill = minutes(spec, f"input {name!r}")
        inputs.append(Primitive.kinds[name](backfill=backfill is not None,
                                            window=timedelta(minutes=backfill) if backfill else None))

    # variables are global: every declaration of a name (at the top, or in a state) is the
    # same variable. One with a value gives its starting value, one without keeps it
    starts: dict[str, Any] = {}

    def declare(spec: dict) -> str:
        name = spec.get("name")
        if not name:
            raise ConfigError(f"a variable needs a name ({spec})", path.name)
        if unknown := set(spec) - FIELDS["variables"]:
            raise ConfigError(f"variable {name!r}: unknown {', '.join(sorted(unknown))}", path.name)
        if name not in starts:
            if name in names:
                raise ConfigError(f"{name!r} is defined twice", path.name)
            names.add(name)
            starts[name] = None
        if "value" in spec:
            value = spec["value"]
            if value is not None and not isinstance(value, bool | int | float | str):
                raise ConfigError(f"variable {name!r}: a value is a number, true / false, null or an expression ({value!r})", path.name)
            starts[name] = value
        return name

    for spec in data.get("variables", []):
        declare(spec)
    declared_in = {(spec.get("name"), state): [declare(v) for v in body.get("variables", [])]
                   for spec in data.get("programs", []) for state, body in spec.get("states", {}).items()}
    variables: list[Variable] = []
    for name, value in starts.items():
        try:
            variables.append(Variable(name, value))
        except ConfigError as e:
            raise e.within(path.name, f"variable {name!r}") from None

    def program(spec: dict) -> Program:
        """A program and its states, still empty (their actions and exits come after the rules)."""
        name = named(spec, "programs")
        if name in Program.registry:
            raise ConfigError(f"{name!r} is a program in proki's code (proki/programs/)", path.name)
        states: dict[str, State] = {}
        for state, body in spec.get("states", {}).items():
            if unknown := set(body) - STATE_FIELDS:
                raise ConfigError(f"{name}.{state}: unknown {', '.join(sorted(unknown))}", path.name)
            own = [Stream.registry[v] for v in declared_in[(name, state)]]
            states[state] = State(state, own)
        try:
            return Program(name, states, spec.get("initial", ""))
        except ConfigError as e:
            raise e.within(path.name) from None

    made = {spec.get("name"): program(spec) for spec in data.get("programs", [])}

    def filled(spec: dict) -> Program:
        """The program's states, filled in: their actions ("do"), "every" and exit."""
        made_program = made[spec["name"]]
        for name, body in spec.get("states", {}).items():
            try:
                fill_state(made_program, made_program.states[name], body)
            except ConfigError as e:
                raise e.within(path.name, f"{made_program.name}.{name}") from None
        return made_program

    def fill_state(made_program: Program, state: State, body: dict) -> None:
        def known(goto: Any) -> str:
            if goto not in made_program.states:
                raise ProgramError(f"{made_program.name} has no state {goto!r}")
            return goto

        state.do = [Action.parse(a) for a in body.get("do", [])]
        every = body.get("every", 1)
        if isinstance(every, bool) or not isinstance(every, int | float) or every <= 0:
            raise ProgramError(f"every is in minutes, more than 0 ({every!r})")
        state.every = timedelta(minutes=every)
        if "next" in body:
            state.next = branches(body["next"], known, f"{made_program.name}.{state.name}")
        elif IDLE not in made_program.states:
            raise ProgramError(f"no next, and no {IDLE!r} state to go back to")

    def branches(next_: Any, known: Any, where: str) -> list[Branch]:
        """`next`: a state's name, or [{"goto": state, "if": [rules] or "expr"}, ...] tried in order."""
        if isinstance(next_, str):
            return [Branch(known(next_))]
        if not isinstance(next_, list) or not next_:
            raise ProgramError(f"next is a state, or a list of {{goto, if}} ({next_!r})")
        made_branches = []
        for i, entry in enumerate(next_):
            if not isinstance(entry, dict) or "goto" not in entry or set(entry) - {"if", "goto"}:
                raise ProgramError(f"next: a branch is {{goto: state, if: [rules] or expr}} ({entry!r})")
            if made_branches and not made_branches[-1].rules and made_branches[-1].condition is None:
                raise ProgramError(f"next: the branch to {entry['goto']!r} comes after the else, so it's never taken")
            when = entry.get("if")
            if isinstance(when, str) and when in Rule.registry:
                raise ProgramError(f"next: {when!r} is a rule, so it goes in a list: [{when!r}]")
            if isinstance(when, str) and when:  # an expression: a hidden signal, true or false
                condition = Signal(f"{where}.next{i}", when)
                condition.inputs  # compiled now: a mistake shows here
                made_branches.append(Branch(known(entry["goto"]), condition=condition))
                continue
            if "if" in entry and (not isinstance(when, list) or not when):
                raise ProgramError(f"next: if is a list of rules, or an expression ({when!r})")
            if missing := [r for r in when or [] if r not in Rule.registry]:
                raise ProgramError(f"next: no rule {', '.join(map(str, missing))}")
            made_branches.append(Branch(known(entry["goto"]), [Rule.registry[r] for r in when or []]))
        return made_branches

    signals: list[Signal] = []
    for spec in data.get("signals", []):
        name = named(spec, "signals")
        if "expr" not in spec:
            raise ConfigError(f"signal {name!r} needs an expr", path.name)
        backfill = minutes(spec, f"signal {name!r}")
        if spec.get("persist") and backfill is None:
            raise ConfigError(f"signal {name!r}: persist needs a backfill (how many minutes to keep)", path.name)
        try:
            signals.append(Signal(name, spec["expr"], backfill=backfill is not None,
                                  window=timedelta(minutes=backfill) if backfill else None,
                                  persist=spec.get("persist", False)))
        except ConfigError as e:
            raise e.within(path.name, f"signal {name!r}") from None

    rules: list[Rule] = []
    for spec in data.get("rules", []):
        name = named(spec, "rules")
        try:
            rules.append(Rule(name, spec.get("lhs"), spec.get("cmp"), spec.get("rhs"),
                              softness=spec.get("softness", 0.0), level=spec.get("level", 1)))
        except ConfigError as e:
            raise e.within(path.name) from None

    for signal in signals:  # every name an expression reads is defined
        try:
            signal.inputs
        except ExprError as e:
            raise e.within(path.name, f"signal {signal.name!r}") from None
    for variable in variables:
        try:
            variable.start and variable.start.inputs
        except ExprError as e:
            raise e.within(path.name, f"variable {variable.name!r}") from None
    if loop := circular([*signals, *(v.start for v in variables if v.start)]):
        raise ExprError(f"{' → '.join(loop)}: a signal can't read itself", path.name)
    programs = [filled(spec) for spec in data.get("programs", [])]
    return Compiled(inputs, variables, signals, rules, programs)


def with_programs(data: dict, folder: Path, names: Iterable[str] | None = None) -> dict:
    """The config with what its program files bring (`names`: which ones, all of them by default)."""
    data = {**data, **{section: list(data.get(section, [])) for section in ("variables", "signals", "rules", "programs")}}
    wanted = None if names is None else set(names)
    for file in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        if wanted is not None and file.stem not in wanted:
            continue
        spec = json.loads(file.read_text())
        if unknown := set(spec) - PROGRAM_FILE:
            raise ConfigError(f"unknown {', '.join(sorted(unknown))} ({', '.join(sorted(PROGRAM_FILE))})", f"programs/{file.name}")
        program = spec.get("program", {})
        if program.get("name", file.stem) != file.stem:
            raise ConfigError(f"its program is named after the file ({file.stem!r})", f"programs/{file.name}")
        for section in ("variables", "signals", "rules"):
            data[section] += spec.get(section, [])
        data["programs"].append({"name": file.stem, **program})
    return data


def circular(streams: Iterable[Stream]) -> list[str] | None:
    """The names around a loop of streams reading each other (a → b → a), if there is one."""
    done: set[Stream] = set()
    path: list[Stream] = []

    def visit(stream: Stream) -> list[str] | None:
        if stream in done:
            return None
        if stream in path:
            loop = path[path.index(stream):] + [stream]
            return [s.name for s in loop if s.name]
        path.append(stream)
        for i in stream.inputs:
            if found := visit(i):
                return found
        path.pop()
        done.add(stream)
        return None

    for stream in streams:
        if found := visit(stream):
            return found
    return None


def editable_copy(path: Path) -> Path:
    """`path`, made from the shipped defaults the first time (it's yours to edit then), and
    kept in sync with them: what the shipped config has and yours doesn't (an entry of a
    section, by name, or a setting like "cycle") is added to yours. What you have stays as
    you wrote it, changed or removed entries of the shipped config don't touch yours.

    A program file of yours in an older form whose program ships is replaced by the shipped
    one, and yours is kept beside it as `<name>.json.old` (`.old2`, ... if that's taken)."""
    shipped_programs, my_programs = CONFIG.parent / "programs", path.parent / "programs"
    my_programs.mkdir(parents=True, exist_ok=True)
    moved = []
    for file in sorted(shipped_programs.glob("*.json")):
        if not (my_programs / file.name).exists():  # a program file you don't have yet
            shutil.copyfile(file, my_programs / file.name)
            moved.append(json.loads(file.read_text()))
    if not path.exists():
        shutil.copyfile(CONFIG, path)
        return path
    for file in sorted(my_programs.glob("*.json")):  # program files you have: today's form too
        spec = json.loads(file.read_text())
        if old_form(spec) and (shipped_programs / file.name).exists():
            kept, n = file.with_name(file.name + ".old"), 1
            while kept.exists():  # an earlier one is kept too
                n += 1
                kept = file.with_name(f"{file.name}.old{n}")
            file.rename(kept)  # kept, beside the shipped one
            shutil.copyfile(shipped_programs / file.name, file)
            continue
        spec, changed = upgrade(spec)
        if changed:
            file.write_text(json.dumps(spec, indent=2) + "\n")
    mine = json.loads(path.read_text())
    mine, upgraded = upgrade(mine)
    mine, removed = without(mine, moved)
    mine, added = merge(mine, json.loads(CONFIG.read_text()))
    if added or removed or upgraded:
        path.write_text(dump(mine))
    return path


RENAMED = {"sector": "label"}  # inputs renamed since: old name → new


def upgrade(mine: dict) -> tuple[dict, list[str]]:
    """A config (or program file) in today's form, and what changed: a signal's
    `"backfill": true, "window": W` is `"backfill": W` now. Renamed inputs (`RENAMED`) by
    their new name, in "inputs" and in every expression (not in what's shown to you). An
    ask's "return" is called "result"."""
    upgraded = []
    for entry in mine.get("signals", []):
        if isinstance(entry, dict) and entry.get("backfill") is True and "window" in entry:
            entry["backfill"] = entry.pop("window")
            upgraded.append(entry.get("name"))
    for entry in mine.get("inputs", []):
        if isinstance(entry, dict) and entry.get("name") in RENAMED:
            entry["name"] = RENAMED[entry["name"]]
            upgraded.append(entry["name"])
    pattern = re.compile(rf"\b({'|'.join(RENAMED)})\b")

    def renamed(value: Any) -> Any:
        if isinstance(value, str):
            return pattern.sub(lambda m: RENAMED[m.group(1)], value)
        if isinstance(value, list):
            return [renamed(v) for v in value]
        if isinstance(value, dict):  # what's shown to you (a question, its options) stays as written
            return {k: v if k in ("text", "context", "option", "options") else renamed(v) for k, v in value.items()}
        return value

    for section in ("signals", "variables", "rules", "programs", "program"):
        if section in mine and (new := renamed(mine[section])) != mine[section]:
            mine[section] = new
            upgraded.append(section)
    for spec in [*mine.get("programs", []), mine.get("program", {})]:  # an ask's "return" is "result" now
        for body in spec.get("states", {}).values() if isinstance(spec, dict) else []:
            for action in body.get("do", []) if isinstance(body, dict) else []:
                ask = action.get("ask") if isinstance(action, dict) else None
                if isinstance(ask, dict) and "return" in ask and "result" not in ask:
                    ask["result"] = ask.pop("return")
                    upgraded.append("ask: result")
    return mine, upgraded


def old_form(spec: dict) -> bool:
    """Whether a program file is in an older form (states with reactions, "actions", or a
    state's "ask"), which today's states replace: a shipped one is replaced by the shipped file."""
    program = spec.get("program", {})
    return any("actions" in body or "ask" in body for body in program.get("states", {}).values() if isinstance(body, dict))


def without(mine: dict, files: list[dict]) -> tuple[dict, list[str]]:
    """`mine` without the entries that moved into program files: those exactly as the
    file has them (what was copied from the shipped config). One you changed stays (and
    is then defined twice, which compiling says)."""
    moved = {(section, json.dumps(entry, sort_keys=True)) for spec in files
             for section, entries in [*((s, spec.get(s, [])) for s in ("variables", "signals", "rules")),
                                      ("programs", [spec["program"]])]
             for entry in entries}
    kept, removed = dict(mine), []
    for section in ("variables", "signals", "rules", "programs"):
        if section in mine:
            kept[section] = [e for e in mine[section] if (section, json.dumps(e, sort_keys=True)) not in moved]
            removed += [e.get("name") for e in mine[section] if (section, json.dumps(e, sort_keys=True)) in moved]
    return kept, removed


def merge(mine: dict, shipped: dict) -> tuple[dict, list[str]]:
    """`mine` with what `shipped` has and it doesn't, and a list of what was added."""
    merged, added = dict(mine), []
    for key, value in shipped.items():
        if key not in merged:
            merged[key] = value
            added.append(key)
        elif isinstance(value, list) and isinstance(merged[key], list):
            have = {entry.get("name") for entry in merged[key] if isinstance(entry, dict)}
            new = [entry for entry in value if entry.get("name") not in have]
            merged[key] = merged[key] + new
            added += [f"{key}.{entry['name']}" for entry in new]
    return merged, added


def dump(config: dict) -> str:
    """The config as JSON, one entry a line (like the shipped file)."""
    parts = []
    for key, value in config.items():
        if isinstance(value, list):
            entries = ",\n".join(f"    {json.dumps(entry)}" for entry in value)
            parts.append(f'  {json.dumps(key)}: [\n{entries}\n  ]' if value else f'  {json.dumps(key)}: []')
        else:
            parts.append(f"  {json.dumps(key)}: {json.dumps(value)}")
    return "{\n" + ",\n".join(parts) + "\n}\n"
