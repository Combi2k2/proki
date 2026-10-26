"""What a program in code is made of, and how it reaches the rest.

    Ritual(name, states)        a program in states, as a config one is
    Step(program)               an action in Python, with its program at hand
    make_branch(goto, **when)   a way out of a state, taken when all of `when` are true now
    make_variable(name, value)  a variable, starting at `value` (the one there is, if any)
    find_variable(name)         a variable, by name (ConfigError if there's none)
    Live(name, read)            a variable worked out as it's read

    ask_usr(context, options)   your answer: the option you picked, or what you typed
    popup_open()                whether a question waits for you

A step keeps what it found on its program, and the ways out read it there:

    State("waiting", do=[Look(self)], every=timedelta(minutes=1), next=[
        make_branch("reminding", due=lambda: self.item is not None),
        make_branch("waiting"),
    ])
"""

from __future__ import annotations

import inspect
import itertools
from collections.abc import Callable, Iterable
from typing import Any, ClassVar

from proki.channels import Popup, queued
from proki.channels.base import Options
from proki.core.actions import Action
from proki.core.programs import Branch, Program, State
from proki.core.signals import Stream, Variable
from proki.errors import ConfigError, VariableError
from proki.utils import snake


class Ritual(Program):
    """A program in code, laid out in states as a config one is.

        name        its name, "@" first
        states      its states (none: a single one, "on")
        initial     the state it starts in (None: the first)

        DESC        what it's for (empty: its module's first paragraph)
        TAGS        its tags
        TITLE       what the app calls it (empty: its name)
        ICON        its icon's name (empty: one its tags pick)
    """

    RESERVED = "@"

    DESC : ClassVar[str]             = ""
    TAGS : ClassVar[tuple[str, ...]] = ()
    TITLE: ClassVar[str]             = ""
    ICON : ClassVar[str]             = ""

    def __init__(self, name: str, states: Iterable[State] = (), initial: str | None = None):
        states = list(states) or [State("on")]
        doc    = inspect.getmodule(type(self)).__doc__ or ""
        desc   = self.DESC or " ".join(doc.split("\n\n")[0].split())
        super().__init__(name, {s.name: s for s in states}, initial or states[0].name,
                         desc=desc, tags=self.TAGS, title=self.TITLE, icon=self.ICON)
        for state in states:  # a step's name is its own in its state ("confirm", "confirm_2")
            taken = set()
            for step in (s for s in state.do if isinstance(s, Step)):
                step.name = _unique(step.name, taken)
                step.id   = f"{name}.{state.name}.{step.name}"
                taken.add(step.name)


def _unique(name: str, taken: set[str]) -> str:
    return next(n for i in itertools.count(1) if (n := f"{name}_{i}" if i > 1 else name) not in taken)


class Step(Action):
    """An action in Python, of a program in code. The config can't write one.

        program     its program, at hand in `apply`
        apply()     what it does, each step its own
        name        its class's, in snake case (`AskLabel`: "ask_label")
        desc        its docstring's first line
        id          "program.state.name": its picks in the media library
    """

    program: Ritual
    name   : str

    def __init_subclass__(cls, **kwargs: Any):
        super(Action, cls).__init_subclass__(**kwargs)  # past Action's: not a kind the config writes

    def __init__(self, program: Ritual):
        self.program = program
        self.name    = snake(type(self).__name__)

    @property
    def desc(self) -> str:
        return (type(self).__doc__ or "").strip().split("\n")[0]

    def __repr__(self) -> str:
        return self.name


Action.kinds.pop(snake(Step.__name__))  # nor is Step itself


def make_branch(goto: str, desc: str = "", **when: Callable[[], Any]) -> Branch:
    """A way out of a state, taken when every condition is true now (none: always).

        goto        the state it goes to
        desc        why it's taken, in a line
        **when      its conditions, by name: a function each, called as the way is tried
    """
    return Branch(goto, conds=[Check(name, test) for name, test in when.items()], desc=desc)


class Check:
    """A way out's condition: shown as `expr`, and true now when `test` says so."""

    def __init__(self, expr: str, test: Callable[[], Any]):
        self.expr, self.test = expr, test

    def current(self) -> Any:
        return self.test()


def make_variable(name: str, value: Any = None) -> Variable:
    """Variable `name`, starting at `value`: the one there is, if there's one already."""
    found = Stream.registry.get(name)
    return found if isinstance(found, Variable) else Variable(name, value)


def find_variable(name: str) -> Variable:
    """Variable `name`. ConfigError if there's none."""
    found = Stream.registry.get(name)
    if not isinstance(found, Variable):  raise ConfigError(f"there's no variable {name}")
    return found


class Live(Variable):
    """A variable worked out by `read` each time it's read, and never set."""

    def __init__(self, name: str, read: Callable[[], Any], desc: str = "", type: str | dict = "any"):
        super().__init__(name, None, desc, type=type)
        self.read = read

    def compute(self) -> Any:
        return self.read()

    def set(self, value: Any) -> None:
        raise VariableError(f"{self.name} is read only")

    def reset(self) -> None:
        pass


def popup_open() -> bool:
    """Whether a question waits for you."""
    return queued("usr") > 0


async def ask_usr(context: str, options: Options | None = None, timeout: float = 24 * 3600,
                  selected: int | None = None, immediate: bool = False, **show: Any) -> int | str | None:
    """Your answer: the index of the option you picked, or with no options what you typed (None: no answer).

        context     the question
        options     "Start", or ("Start", what it means), in order
        timeout     seconds it waits for your answer
        selected    the index of the option picked already, if any
        immediate   it's to answer now: no "Later"
        **show      what's shown with it (`id`, `urgent`, ...)
    """
    return await Popup.ask(context, options, timeout, selected=selected, immediate=immediate or None, **show)
