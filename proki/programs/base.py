"""What programs written in code share: `Ritual`, a program that keeps its state in code (one
state by default) and moves on with what the app gives it each turn (`Program.context`:
the legacy app's timeline for now, `FlowContext`), the way the legacy flows did:

    tick(ctx)   every cycle: the recent timeline, proki's state, the signals' values
    watch(ctx)  every few seconds: what's in focus right now

They talk to the user through `Ui` (core/ui.py), call slow things through `Later`
(core/later.py), reach each other by name (`program("session")`), and read the config's
rules by name (`rules(...)`).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from proki.core.programs import Program, State
from proki.core.rules import Rule
from proki.core.signals import Stream, Variable
from proki.errors import ConfigError


class Ritual(Program):
    def __init__(self, name: str, states: tuple[str, ...] = ("on",), initial: str | None = None):
        super().__init__(name, {s: State(s) for s in states}, initial or states[0])

    def step(self, now: datetime) -> None:
        if self.context is not None:
            self.tick(self.context)

    def poll(self, now: datetime) -> None:
        if self.context is not None:
            self.watch(self.context)

    def tick(self, ctx: Any) -> None:
        """Every cycle."""

    def watch(self, ctx: Any) -> None:
        """Every few seconds."""


def program(name: str) -> Any:
    """Another program, by name (None if it isn't running)."""
    return Program.registry.get(name)


def rules(*names: str) -> list[Rule]:
    """The config's rules, by name (they live in config.json or a program's file)."""
    if missing := [name for name in names if name not in Rule.registry]:
        raise ConfigError(f"the config has no rule {', '.join(missing)}")
    return [Rule.registry[name] for name in names]


def variable(name: str, value: Any = None) -> Variable:
    """The config's variable `name`, made (starting at `value`) if the config has none."""
    found = Stream.registry.get(name)
    return found if isinstance(found, Variable) else Variable(name, value)
