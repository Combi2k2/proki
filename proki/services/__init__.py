"""The services proki uses. Each knows its own service, not proki: what proki asks of it,
and when, is said where it's used.

    activitywatch.py ActivityWatch, as `aw`: its API, and what its watchers recorded
    nats.py          a message bus, over NATS or in one process
    supervisor.py    runs a service's programs: its server, and the ones that need it
    jev.py           jev, a structured-decision API
    llm.py           LLMs, one client for every service that speaks the OpenAI API
    media.py         a media library: pictures and sounds, and pools to draw them from
"""

from proki.services import activitywatch as aw
from proki.services import jev, nats

__all__ = ["aw", "jev", "nats"]