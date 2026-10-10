"""Programs: state machines running side by side, each in one state at a time.

A program is a set of named states. It starts in its `initial` state, which is also where
it goes back to when a state has no way out. A state does its actions when it's entered,
then waits, then tries its one way out.

    "asking": {
        "do":    [{"ask": {"channel": "usr", "context": "Start a session?",
                           "options": [{"option": "Start"}, {"option": "Not now"}], "result": "$answer"}}],
        "every": 0.1,
        "next":  [{"goto": "starting", "if": "$answer == 0"}, {"goto": "waiting"}]
    }

A state has:

    variables   its own (a program can have its own too)
    rules       its own, for its `next` to vote on (a program can have its own too)
    do          actions taken in order when the state is entered (core/actions/)
    every       minutes between tries of `next` (1 by default)
    next        where to go: branches tried in order. Never empty: written as a state's name,
                or left out (back to `initial`), the compiler makes it a branch that always passes

A branch goes to its `goto` if it passes. Its `if` is a list of rules and conditions,
or one of them:

    {"goto": "starting", "if": ["focus_high", "$answer == 0", "not in_session"]}

    rules        names of rules, voted together (`Rule.vote`): soft, by level
    conditions   expressions, each true or false: hard, like a rule with no softness above
                 every level. All of them must be true, then the rules vote

A branch without `if` always passes (the else). An unknown condition isn't true.

A program's life (`run`), one task per program:

    1. enter a state: its actions run, in order. A question waits here for its answer
    2. wait until `every` has passed since it was entered
    3. try `next`, like if / elif / else: the first branch that passes is entered (back to
       1). None passes: wait `every` more, and try again

Each program goes on with its job on its own: nothing waits for another program. Time is
the engine's: a program waits for cycles, not seconds (`until`), and each cycle the engine
wakes the ones whose wait is over (`tick`). So a program is never asked anything while it
waits, a branch always sees this cycle's values, and a replay or a test moves time as
fast as it likes. Entering a state, even the one it's in, runs its `do` again. That's how
a state loops.

Variables and rules: a state reads its own, its program's and the global ones, by their
full names (`suggest.asking.answer`), which the compiler writes out (proki/compiler/). Only
variables carry over a restart: each start begins every program at its `initial` state.

A program written in code (proki/programs/) has a `run` of its own: `Ritual`'s calls its
`step` once a cycle (programs/base.py).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import ClassVar

from proki.core.signals import Signal, Variable
from proki.core.actions import Action
from proki.core.rules import Rule
from proki.errors import ProgramError

@dataclass
class Branch:
    """One branch of a `next` (see above): every condition (an expression, as a hidden
    signal) is true, then its rules vote yes. Neither: it always passes."""

    goto: str
    rules: list[Rule] = field(default_factory=list)
    conds: list[Signal] = field(default_factory=list)

    def passes(self) -> bool:
        values = [cond.current() for cond in self.conds]
        if not all(value is not None and bool(value) for value in values):  return False  # unknown isn't true

        return Rule.vote(self.rules)


@dataclass
class State:
    """A state of a program (see above). `vars` and `rules` are its own."""

    name: str
    vars: list[Variable] = field(default_factory=list)
    rules: list[Rule] = field(default_factory=list)
    do: list[Action] = field(default_factory=list)
    every: timedelta = timedelta(minutes=1)
    next: list[Branch] = field(default_factory=list)


class Program:
    registry: ClassVar[dict[str, Program]] = {}  # every program, by name
    now: ClassVar[datetime | None] = None  # the cycle being run (`tick`)

    def __init__(self, name: str, states: dict[str, State], initial: str):
        if not name.isascii():      raise ProgramError(f"program {name!r}: a name is letters, digits and _, not starting with a digit")
        if not name.isidentifier(): raise ProgramError(f"program {name!r}: a name is letters, digits and _, not starting with a digit")
        if initial not in states:   raise ProgramError(f"program {name!r}: initial {initial!r} isn't one of its states")

        self.name = name
        self.states = states
        self.initial = initial
        self.vars: list[Variable] = []  # its own (each state has its own too)
        self.rules: list[Rule] = []
        self.current = initial
        self.task: asyncio.Task | None = None  # its `run`, from its first cycle on
        self.wake: tuple[datetime, asyncio.Future] | None = None  # while it waits for a cycle: when, and what wakes it
        Program.registry[name] = self

    async def run(self) -> None:
        """Its life (see above), from its initial state on."""
        name = self.initial
        while True:
            state, entered = self.states[name], Program.now
            self.current = name
            await self.act(state.do)
            await self.until(entered + state.every)
            
            while (goto := self.choose(state)) is None:
                await self.until(Program.now + state.every)
            name = goto

    async def act(self, actions: list[Action]) -> None:
        """The actions, in order. One that fails is reported, and the rest still run."""
        for action in actions:
            try:
                await action.apply()
            except Exception as e:
                print(f"{self.name}.{self.current}: {action!r} failed ({e.__class__.__name__}: {e})", flush=True)

    def choose(self, state: State) -> str | None:
        """The state the first branch that passes goes to, or None when none does yet. Later
        branches aren't tried, so their rules aren't drawn."""
        for branch in state.next:
            if branch.passes():  return branch.goto
        return None

    async def until(self, t: datetime) -> None:
        """Wait for the first cycle after this one at or past `t` (`tick` wakes it)."""
        self.wake = (t, asyncio.get_running_loop().create_future())
        await self.wake[1]

    @classmethod
    def tick(cls, now: datetime) -> None:
        """A new cycle: start the programs that haven't started, and wake the ones whose wait
        is over. It doesn't wait for them: each goes on with its job on its own."""
        cls.now = now
        for program in list(cls.registry.values()):
            if program.task is None:
                program.task = asyncio.get_running_loop().create_task(program.run())
            elif program.wake is not None and program.wake[0] <= now:
                wake, program.wake = program.wake[1], None
                wake.set_result(None)

    @classmethod
    def stop(cls) -> None:
        """Stop every program (when proki quits, or between tests)."""
        for program in cls.registry.values():
            if program.task is not None: 
                program.task.cancel()

    def __repr__(self) -> str:
        return f"<Program {self.name} in {self.current}>"
