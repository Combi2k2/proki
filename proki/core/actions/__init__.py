"""Actions, by what they act on:

    a variable    set, add, sub
    a list        append, remove
    a question    ask_usr, ask_jev, ask_llm
    the UI        poke, lock, open
"""

from proki.core.actions.base import Action, Context, LValue
from proki.core.actions.ui   import Lock, Open, Poke
from proki.core.actions.var  import Add, Set, Sub, Append, Remove
from proki.core.actions.ask  import AskJev, AskLlm, AskUsr

ACTIONS = Action.kinds  # every kind, by name, once imported above

__all__ = [
    "ACTIONS",
    "Action",
    "Set",
    "Add",
    "Sub",
    "Append",
    "Remove",
    "AskJev",
    "AskLlm",
    "AskUsr",
    "Lock",
    "Open",
    "Poke",
    "Context",
    "LValue",
]
