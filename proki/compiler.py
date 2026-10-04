"""Compiles proki's config (a JSON file) into what runs. `CONFIG` ships the defaults; the
app keeps an editable copy next to its config.

    "cycle":   10
        seconds between cycles (optional, 10 by default): every stream moves on once a cycle

    "inputs":  [{"name": "app", "backfill": 1440}, ...]
        the primitives read from ActivityWatch (core/signals/primitive.py), by name;
        `backfill`: how many minutes of itself it keeps as a table (none if left out)

    "variables": [{"name": "last_suggested", "value": null},
                  {"name": "deadline_eod", "value": "time - clock + 1440"}, ...]
        app state: a value actions and flows set (core/signals/variable.py), starting at
        `value` (a constant, or an expression worked out on its first cycle); its latest
        value is kept across restarts

    "signals": [{"name": "keys_5m", "expr": "ts_mean(keys, 5)", "backfill": false,
                 "window": minutes, "persist": false}, ...]
        a signal needs a name and an expr; the rest is optional

    "rules":   [{"name": "focus_high", "lhs": "focus_5m", "cmp": "gt", "rhs": 0.5, "softness": 0.1,
                 "level": 1}, ...]
        a soft comparison of two expressions, the chance of firing now (core/rules.py);
        rules vote by `level`, the highest first

An expression can read the inputs, the variables and the other signals, in any order.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from proki.core.rules import Rule
from proki.core.signals import ExprError, Primitive, Signal, Stream, Variable

CONFIG = Path(__file__).resolve().parent / "assets" / "config.json"
FIELDS = {
    "inputs": {"name", "backfill"},
    "variables": {"name", "value"},
    "signals": {"name", "expr", "backfill", "window", "persist"},
    "rules": {"name", "lhs", "cmp", "rhs", "softness", "level"},
}


@dataclass
class Program:
    inputs: list[Primitive]
    variables: list[Variable]
    signals: list[Signal]
    rules: list[Rule]

    @property
    def streams(self) -> list[Stream]:
        return [*self.inputs, *self.variables, *self.signals]


def compile_config(path: Path = CONFIG) -> Program:
    """What a config defines: streams (in `Stream.registry`) and rules (`Rule.registry`); raises
    `ValueError` on a mistake, naming the file and the entry."""
    data = json.loads(path.read_text())
    if unknown := set(data) - set(FIELDS) - {"cycle"}:
        raise ValueError(f"{path.name}: unknown section {', '.join(sorted(unknown))}")
    cycle = data.get("cycle", 10)
    if isinstance(cycle, bool) or not isinstance(cycle, int | float) or cycle <= 0:
        raise ValueError(f"{path.name}: cycle is in seconds ({cycle!r})")
    Stream.cycle = timedelta(seconds=cycle)
    names: set[str] = set()

    def named(entry: dict, section: str) -> str:
        name = entry.get("name")
        if not name:
            raise ValueError(f"{path.name}: an entry of {section} needs a name ({entry})")
        if name in names:
            raise ValueError(f"{path.name}: {name!r} is defined twice")
        if unknown := set(entry) - FIELDS[section]:
            raise ValueError(f"{path.name}: {name!r}: unknown {', '.join(sorted(unknown))}")
        names.add(name)
        return name

    inputs: list[Primitive] = []
    for spec in data.get("inputs", []):
        name = named(spec, "inputs")
        if name not in Primitive.kinds:
            raise ValueError(f"{path.name}: no input is called {name!r} ({', '.join(Primitive.kinds)})")
        backfill = spec.get("backfill")
        if backfill is not None and (isinstance(backfill, bool) or not isinstance(backfill, int | float) or backfill <= 0):
            raise ValueError(f"{path.name}: input {name!r}: backfill is in minutes ({backfill!r})")
        inputs.append(Primitive.kinds[name](backfill=backfill is not None,
                                            window=timedelta(minutes=backfill) if backfill else None))

    variables: list[Variable] = []
    for spec in data.get("variables", []):
        name = named(spec, "variables")
        value = spec.get("value")
        if value is not None and not isinstance(value, bool | int | float | str):
            raise ValueError(f"{path.name}: variable {name!r}: a value is a number, true / false, null or an expression ({value!r})")
        try:
            variables.append(Variable(name, value))
        except ValueError as e:
            raise ValueError(f"{path.name}: variable {name!r}: {e}") from None

    signals: list[Signal] = []
    for spec in data.get("signals", []):
        name = named(spec, "signals")
        if "expr" not in spec:
            raise ValueError(f"{path.name}: signal {name!r} needs an expr")
        window = timedelta(minutes=spec["window"]) if spec.get("window") is not None else None
        try:
            signals.append(Signal(name, spec["expr"], backfill=spec.get("backfill", False), window=window,
                                  persist=spec.get("persist", False)))
        except ValueError as e:
            raise ValueError(f"{path.name}: signal {name!r}: {e}") from None

    rules: list[Rule] = []
    for spec in data.get("rules", []):
        name = named(spec, "rules")
        try:
            rules.append(Rule(name, spec.get("lhs"), spec.get("cmp"), spec.get("rhs"),
                              softness=spec.get("softness", 0.0), level=spec.get("level", 1)))
        except ValueError as e:
            raise ValueError(f"{path.name}: {e}") from None

    for signal in signals:  # every name an expression reads is defined
        try:
            signal.inputs
        except ExprError as e:
            raise ValueError(f"{path.name}: signal {signal.name!r}: {e}") from None
    for variable in variables:
        try:
            variable.start and variable.start.inputs
        except ExprError as e:
            raise ValueError(f"{path.name}: variable {variable.name!r}: {e}") from None
    return Program(inputs, variables, signals, rules)


def editable_copy(path: Path) -> Path:
    """`path`, made from the shipped defaults the first time (it's yours to edit then), and
    kept in sync with them: what the shipped config has and yours doesn't (an entry of a
    section, by name, or a setting like "cycle") is added to yours; what you have stays as
    you wrote it, changed or removed entries of the shipped config don't touch yours."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(CONFIG, path)
        return path
    mine, added = merge(json.loads(path.read_text()), json.loads(CONFIG.read_text()))
    if added:
        path.write_text(dump(mine))
    return path


def merge(mine: dict, shipped: dict) -> tuple[dict, list[str]]:
    """`mine` with what `shipped` has and it doesn't; and what was added."""
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
