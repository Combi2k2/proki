"""Rules: a measured quantity against a soft threshold (base.py), one module per rule.

    base.py        Rule, RuleParams, AllOf, Cadence
    budget.py      shallow-work budget
    shutdown.py    when to offer the shutdown: time of day × low focus
    focus.py       low focus in a session (and not rising)
    absence.py     whether to ask "what did you do?" about an absence
    reminder.py    routine reminders
    capture.py     time on shallow work / in distraction before "anything worth noting?"
    walk.py        whether to suggest a thinking walk after a session

The older segment rules (fragmentation) and their engine are in legacy/.
"""
