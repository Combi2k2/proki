"""Actions: the steps a program takes as it enters a state (a state's "do"). They are things
done, never jumps: where a program goes next is the state's own exit (core/programs.py).

One file by what they act on, each with its kinds' examples:

    base.py   `Action`, and what the kinds share (`Context`: what's said)
    var.py    a variable, by an expression's value: set, add, sub
    ask.py    a question to you, jev or an LLM, its answer later in a variable: ask
    ui.py     the UI, one way: poke (ringing, with alarm), lock, open

A kind's name is its class's in snake case (`Poke`: "poke"), and its params are its
keyword arguments: {kind: {param: value}}.
"""

from proki.core.actions.base import Action
from proki.core.actions.ask import Ask
from proki.core.actions.var import Add, Set, Sub
from proki.core.actions.ui import Lock, Open, Poke

KINDS = Action.kinds  # what the config can write, by name: each action, once imported above

__all__ = ["Action", "KINDS", "Add", "Ask", "Lock", "Open", "Poke", "Set", "Sub"]
