"""Programs: state machines running side by side, each in one state at a time.

    "asking": {
        "do":    [{"ask_usr": {"context": "Start a session?", "options": ["Start", "Not now"], "result": "answer"}}],
        "every": 0.1,
        "next":  [{"goto": "starting", "when": ["focus_high", "answer == 0"]}, {"goto": "waiting"}]
    }

Entering a state runs its `do`. Every `every` minutes (1 by default), its `next` is tried
like if / elif / else: a branch passes when its conditions are true and its rules vote yes.
A branch without `when` always passes; a state without `next` goes back to `initial`.

A state's variables start over when it's left; a program's when it starts over.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import ClassVar

from proki.core.actions import Action
from proki.core.rules import Rule
from proki.core.signals import Signal, Stream, Variable
from proki.errors import ProgramError


@dataclass
class Branch:
    """A way out of a state: taken when every condition is true and the rules vote yes; with
    neither, always."""

    goto  : str
    rules : list[Rule]   = field(default_factory=list)
    conds : list[Signal] = field(default_factory=list)
    desc  : str          = ""                            # why it's taken, in a line

    def passes(self) -> bool:
        """Whether it's taken now."""
        if not all(_condition_now(cond) for cond in self.conds):  # unknown isn't true
            return False
        return Rule.vote(self.rules)


def _condition_now(cond: Signal) -> bool:
    """Read a branch after its actions, even if the editor read it while an ask waited.

    Keep named inputs' cycle values; only the condition's own expression cache is
    refreshed. A variable itself reads its latest value without a cache.
    """
    def clear(stream: Stream) -> None:
        if stream is not cond and stream.name and Stream.registry.get(stream.name) is stream:
            return
        stream._cached = False
        for input in stream.inputs:
            clear(input)

    clear(cond)
    return bool(cond.current())


@dataclass
class State:
    """A state: what it does when entered, how often it tries its way out, and where to."""

    name  : str
    desc  : str            = ""
    vars  : list[Variable] = field(default_factory=list)   # its own
    rules : list[Rule]     = field(default_factory=list)   # its own
    do    : list[Action]   = field(default_factory=list)
    every : timedelta      = timedelta(minutes=1)
    next  : list[Branch]   = field(default_factory=list)   # never empty: the builder makes a name, or nothing, a branch that always passes


class Program:
    """A program (see above), in the state `current`. ProgramError for a name that isn't
    letters, digits and _, or an `initial` that isn't one of its states."""

    RESERVED : ClassVar[str] = ""                  # what its name starts with: "@" for a program in code
    registry : ClassVar[dict[str, Program]] = {}   # every program, by name
    now      : ClassVar[datetime | None] = None    # the cycle being run

    def __init__(self, name: str, states: dict[str, State], initial: str, desc: str = "", tags: Iterable[str] = (),
                 title: str = "", icon: str = ""):
        bare = name.removeprefix(self.RESERVED) if name.startswith(self.RESERVED) else ""
        if not (bare.isascii() and bare.isidentifier()):
            raise ProgramError(f"program {name!r}: a name is ASCII letters, digits and _, not starting with a digit")
        if initial not in states:
            raise ProgramError(f"program {name!r}: initial {initial!r} isn't one of its states")

        self.title   = title                                         # front end name 
        self.icon    = icon                                          # its icon's name (empty: one its tags pick)
        self.name    = name
        self.desc    = desc                                          # what it's for, in a line
        self.tags    = list(tags)                                    # words to find it by
        self.states  = states
        self.initial = initial
        self.current = initial
        self.vars    : list[Variable] = []                           # its own
        self.rules   : list[Rule]     = []                           # its own
        self.task    : asyncio.Task | None = None                    # its life, from its first cycle on
        self.wake    : tuple[datetime, asyncio.Future] | None = None # while it waits: until when, and what wakes it
        self.on      = True                                          # off: the cycles leave it alone
        Program.registry[name] = self

    async def run(self) -> None:
        """Its life (see above), from `initial`, its variables and its states' as they start."""
        for variable in [*self.vars, *(v for state in self.states.values() for v in state.vars)]:
            variable.reset()
        name, cycle, seen = self.initial, None, set()   # seen: the states entered this cycle
        while True:
            if name in seen and cycle == Program.now:
                await self.until(Program.now)  # a state once a cycle at most: again, the next
            if cycle != Program.now:
                cycle, seen = Program.now, set()
            seen.add(name)
            state, entered = self.states[name], Program.now
            self.current = name
            await self.act(state.do)
            if state.every:
                await self.until(entered + state.every)

            while (goto := self.choose(state)) is None:
                await self.until(Program.now + state.every)
            for variable in state.vars:  # leaving it: its variables start over
                variable.reset()
            name = goto

    async def act(self, actions: list[Action]) -> None:
        """The actions, in order. One that fails is reported, and the rest still run."""
        for action in actions:
            try:
                await action.apply()
            except Exception as e:
                print(f"{self.name}.{self.current}: {action!r} failed ({e.__class__.__name__}: {e})", flush=True)

    def choose(self, state: State) -> str | None:
        """Where the first branch that passes goes (None: none does yet); the ones after it
        aren't tried."""
        for branch in state.next:
            if branch.passes():  return branch.goto
        return None

    async def until(self, t: datetime) -> None:
        """Waits for the first cycle after this one at or past `t`."""
        self.wake = (t, asyncio.get_running_loop().create_future())
        await self.wake[1]

    @classmethod
    def tick(cls, now: datetime) -> None:
        """A new cycle at `now`: the programs not started yet start, the ones whose wait is over
        go on. None is waited for."""
        cls.now = now
        for program in list(cls.registry.values()):
            if not program.on:
                continue
            if program.task is None:
                program.task = asyncio.get_running_loop().create_task(program.run())
            elif program.wake is not None and program.wake[0] <= now:
                wake, program.wake = program.wake[1], None
                wake.set_result(None)

    def switch(self, on: bool) -> None:
        """Off: it stops where it is. On: it starts over at `initial`, the next cycle."""
        if on == self.on:  return
        if self.task is not None:
            self.task.cancel()
        self.on, self.task, self.wake, self.current = on, None, None, self.initial

    @classmethod
    def stop(cls) -> None:
        """Every program stopped (proki quitting)."""
        for program in cls.registry.values():
            if program.task is not None:
                program.task.cancel()

    def __repr__(self) -> str:
        return f"<Program {self.name} in {self.current}>"
