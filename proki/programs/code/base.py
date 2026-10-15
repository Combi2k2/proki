"""What a program in code is made of, and how it reaches the rest.

    Ritual(name, states)        a program in states, as a config one is
    Step                        an action in Python, with its program at hand
    make_branch(goto, **when)   a way out of a state, taken when all of `when` are true now
    make_variable(name, value)  a variable, starting at `value` (the one there is, if any)

    find_variable(name)         a variable, by name
    find_program(name)          a program, by name
    find_rules(*names)          rules, by name

    choose(context, options)    a question whose options each mean something to the program
    popup_open()                whether a question waits for you

Each `find_` raises ConfigError for a name there isn't.

A step keeps what it found on its program, and the ways out read it there:

    State("waiting", do=[Look(self)], every=timedelta(minutes=1), next=[
        make_branch("reminding", due=lambda: self.item is not None),
        make_branch("waiting"),
    ])
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Iterable
from typing import Any, ClassVar

from proki.channels import Popup, queued
from proki.core.actions import Action
from proki.core.programs import Branch, Program, State
from proki.core.rules import Rule
from proki.core.signals import Stream, Variable
from proki.errors import ConfigError
from proki.utils import snake


class Ritual(Program):
    """A program in code, laid out in states as a config one is.

        name        its name, "@" first ("@planner")
        states      its states (none: a single one, "on")
        initial     the state it starts in (None: the first)

        DESC        what it's for (empty: its module's first paragraph)
        TAGS        its tags
    """

    RESERVED = "@"

    DESC: ClassVar[str]             = ""
    TAGS: ClassVar[tuple[str, ...]] = ()

    def __init__(self, name: str, states: Iterable[State] = (), initial: str | None = None):
        doc    = inspect.getmodule(type(self)).__doc__ or ""
        states = list(states) or [State("on")]
        super().__init__(name, {s.name: s for s in states}, initial or states[0].name,
                         desc=self.DESC or " ".join(doc.split("\n\n")[0].split()), tags=self.TAGS)


class Step(Action):
    """An action in Python, of a program in code.

        program     its program, at hand in `apply`
        apply()     what it does, each step its own

    It isn't one of `Action.kinds`, so the config can't write one. It's shown by its name
    (`Remind`: "remind").
    """

    program: Ritual

    def __init_subclass__(cls, **kwargs: Any):
        super(Action, cls).__init_subclass__(**kwargs)  # past Action's: not a kind of the config

    def __init__(self, program: Ritual):
        self.program = program

    def __repr__(self) -> str:
        return snake(type(self).__name__)


Action.kinds.pop(snake(Step.__name__))  # nor is Step itself


def make_branch(goto: str, desc: str = "", **when: Callable[[], Any]) -> Branch:
    """A way out of a state.

        goto        the state it goes to
        desc        why it's taken, in a line
        **when      its conditions, by name: a function each, called as the way is tried

    It's taken when every condition is true now (none: always).
    """
    return Branch(goto, conds=[Check(name, test) for name, test in when.items()], desc=desc)


class Check:
    """A way out's condition in code.

        expr        what it's shown as: its name in `make_branch`
        test        the function it asks
        current()   what `test` says now
    """

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


def find_program(name: str) -> Program:
    """Program `name`. ConfigError if there's none."""
    if name not in Program.registry:  raise ConfigError(f"there's no program {name}")
    return Program.registry[name]


def find_rules(*names: str) -> list[Rule]:
    """Rules `names`. ConfigError for one there isn't."""
    if missing := [name for name in names if name not in Rule.registry]:
        raise ConfigError(f"there's no rule {', '.join(missing)}")
    return [Rule.registry[name] for name in names]


def popup_open() -> bool:
    """Whether a question waits for you."""
    return queued("usr") > 0


async def choose(context: str, options: list[tuple[str, str]], timeout: float = 24 * 3600, **show: Any) -> str | None:
    """A question whose options each mean something to the program.

        context     the question
        options     (label, what it means), in order
        timeout     seconds it waits for your answer
        **show      what's shown with it, as for `Popup.ask`

    What the option you picked means (None: no answer).
    """
    index = await Popup.ask(context, [label for label, _ in options], timeout, **show)
    return None if index is None else options[index][1]
