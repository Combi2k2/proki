"""Programs: state machines running side by side, each in one state at a time.

A program is a set of named states. It starts in its `initial` state. Each state can take
actions as it's entered, and has one way out.

    "counting": {"do": [{"add": {"name": "active_today", "expr": "active"}}],
                 "every": 1, "next": "counting"}

A state has:

    do      actions taken when the state is entered (core/actions/), in order
    every   minutes to wait before trying `next` (default 1). It's then tried again every
            `every` minutes until it leads somewhere
    next    where to go: a state's name, or branches tried in order, like if / elif / else:
                [{"goto": "x", "if": ["rule_a", "rule_b"]}, {"goto": "y", "if": "answer == 1"},
                 {"goto": "z"}]
            `if` is a list of rules, voted together (`Rule.vote`), or an expression that's
            true or false. The first branch that passes is taken, and a branch without "if"
            always passes (the else). If none passes, the program stays and tries again
            after `every`. Without `next`, the program goes back to its "idle" state.

Going to a state, even the same one, enters it again: its `do` runs again. That's how a
state loops (`"next": "counting"` above counts every minute).

A question (the `ask` action) doesn't hold the program: its answer comes later into a
variable, and the state's `next` waits for it (a rule on an unknown value doesn't pass).

Variables are global. Declaring one in a state only says where it's used, and it keeps
its value when the state is left. Programs always run: each start begins every program at
its `initial` state (only variables carry over). `Program.tick(now)` moves every program
on, once a cycle.

A program written in code (proki/programs/) is a subclass with its own `step`, and maybe
a `poll` too: between cycles, every few seconds (`Program.poll_all`), for what's in focus
right now. Both can read `Program.context`, what the app gives programs each turn.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, ClassVar

from proki.core.actions import Action
from proki.core.rules import Rule
from proki.core.signals import Signal, Variable
from proki.errors import ProgramError

IDLE = "idle"  # where a state without `next` goes


@dataclass
class Branch:
    """One branch of a `next`: go to `goto` if its rules vote yes, or its condition (an
    expression, as a hidden signal) is true. Neither: always."""

    goto: str
    rules: list[Rule] = field(default_factory=list)
    condition: Signal | None = None

    def passes(self) -> bool:
        if self.condition is not None:
            value = self.condition.current()
            return value is not None and bool(value)
        return Rule.vote(self.rules)


@dataclass
class State:
    name: str
    variables: list[Variable] = field(default_factory=list)
    do: list[Action] = field(default_factory=list)
    every: timedelta = timedelta(minutes=1)
    next: list[Branch] | None = None


class Program:
    registry: ClassVar[dict[str, Program]] = {}  # every program, by name
    context: ClassVar[Any] = None  # what the app gives programs in code, each turn

    def __init__(self, name: str, states: dict[str, State], initial: str):
        if not name:    raise ProgramError("program name can't be empty")
        if "." in name: raise ProgramError(f"program {name!r}: a name without dots")
        if initial not in states:
            raise ProgramError(f"program {name!r}: initial {initial!r} isn't one of its states")
        self.name, self.states, self.initial = name, states, initial
        self.current = initial
        self.entered: datetime | None = None  # when the current state was entered (None: not started)
        self.tried: datetime | None = None  # when its `next` was last tried
        Program.registry[name] = self

    def step(self, now: datetime) -> None:
        """One turn: start in the initial state, or try the current state's `next` when it's due."""
        if self.entered is None:
            self.enter(self.initial, now)
            return
        state = self.states[self.current]
        if now - (self.tried or self.entered) < state.every:
            return
        self.tried = now
        if state.next is None:
            self.enter(IDLE, now)
            return
        for branch in state.next:
            if branch.passes():
                self.enter(branch.goto, now)
                return

    def enter(self, name: str, now: datetime) -> None:
        """Go to state `name` (again, if it's the current one), and take its actions."""
        self.current, self.entered, self.tried = name, now, None
        for action in self.states[name].do:
            action.apply()

    def poll(self, now: datetime) -> None:
        """Between cycles (programs in code)."""

    @classmethod
    def tick(cls, now: datetime) -> None:
        """Every program, one turn each."""
        for program in list(cls.registry.values()):
            program.step(now)

    @classmethod
    def poll_all(cls, now: datetime) -> None:
        for program in list(cls.registry.values()):
            program.poll(now)

    def __repr__(self) -> str:
        return f"<Program {self.name} in {self.current}>"
