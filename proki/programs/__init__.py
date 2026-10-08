"""Programs written in code, for what doesn't fit the config yet (core/programs.py): each a
`Program` in `Program.registry`, one file each; the config reads their variables. Most
are the legacy flows moved over (base.py: `Ritual`), talking to the user through
core/ui.py instead of the Qt popup.

    plan        which task to work on, handed over when a session starts (plan.py)
    session     focus sessions: pokes, wrap-up, away alarm, sprint / walk / grand gesture
    shutdown    the shutdown ritual: notes, wrap-up, weekly review, "shutdown complete"
    routines    after an absence: were you away, and what was it?
    reminders   "around 12:30 is usually time for: a meal"
    rhythm      the deep-work block reminder
    capture     "anything worth noting?", notes into tasks, "finished?" for a tab's task
    meditation  the thinking walk
    grand       the grand gesture
    sprint      the sprint's "time's up"
    experiment  the 30-day test
    craftsman   "does this site help any of your goals?"

Written in the config instead (assets/programs/): day, suggest, budget, hub, bedtime,
morning, evening.
"""

from proki.programs.base import Ritual, program, rules, variable
from proki.programs.capture import Capture
from proki.programs.craftsman import Craftsman
from proki.programs.experiment import ThirtyDayTest
from proki.programs.grand import Grand
from proki.programs.meditation import Meditation
from proki.programs.plan import Plan, TaskStore
from proki.programs.reminders import Reminders
from proki.programs.rhythm import Rhythm
from proki.programs.routines import Routines
from proki.programs.session import Session
from proki.programs.shutdown import Shutdown
from proki.programs.sprint import Sprint

__all__ = ["Capture", "Craftsman", "Grand", "Meditation", "Plan", "Reminders", "Rhythm",
           "Ritual", "Routines", "Session", "Shutdown", "Sprint", "TaskStore", "ThirtyDayTest", "program", "rules",
           "variable"]
