"""Outside services proki talks to.

    activitywatch.py ActivityWatch, as `aw`: its API, and what its watchers recorded
    nats.py          NATS, the message bus questions and UI messages go over
    supervisor.py    runs the programs of ActivityWatch and NATS (Supervisor)
    jev.py           openjev, the structured-decision API (optional)
    llm.py           LLMs, one client for every family that speaks the OpenAI API
"""

from proki.services import activitywatch as aw
from proki.services import jev, nats

__all__ = ["aw", "jev", "nats"]