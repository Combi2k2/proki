"""Actions: the steps a program takes as it enters a state (a state's "do"). They are things
done, never jumps: where a program goes next is the state's own exit (core/programs.py).

One file each, in a folder by what they act on: var/ a variable, ask/ a question, ui/ the
UI. A folder's
base.py is what its actions share, the top base.py `Action`. A kind's name is its class's
in snake case (`Poke` in ui/poke.py: "poke"), and its params are its keyword arguments:
{kind: {param: value}}.

A variable, by an expression's value when the action is taken (one variable each):
    set     {"set": {"name": "deadline_eod", "expr": "deadline_eod + 1440"}}
    add     {"add": {"name": "active_today", "expr": "active"}}     (true / false add 1 / 0)
    sub     {"sub": {"name": "budget", "expr": "minutes"}}

A question, its answer later in a variable (ask/):
    ask     {"ask": {"channel": "usr", "context": "Start a session?", "options": [{"option": "Start"},
             {"option": "Not now"}], "result": "suggest_answer", "default": 1}}

The UI, one way (nothing comes back):
    poke    {"poke": {"text": "{h:.0f} h left today", "values": {"h": "..."}}}
    alarm   {"alarm": {"name": "bedtime", "on": true}}   ring (true) until turned off (false)
    lock    {"lock": {}}                                 lock the screen
    open    {"open": {"view": "task_form"}}              a view: task_form, task_board
"""

from proki.core.actions.base import Action
from proki.core.actions.ask import Ask
from proki.core.actions.ui import Alarm, Lock, Open, Poke
from proki.core.actions.var import Add, Set, Sub

KINDS = Action.kinds  # what the config can write, by name: each action, once imported above

__all__ = ["Action", "KINDS", "Add", "Alarm", "Ask", "Lock", "Open", "Poke", "Set", "Sub"]
