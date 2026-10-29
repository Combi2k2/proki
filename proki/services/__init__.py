"""The services proki uses, each knowing only its own service:

    aw            ActivityWatch: what its watchers recorded
    nats          a message bus, over NATS or in one process
    supervisor    a service's programs, run and kept running
    jev           jev: questions answered with how likely each answer is
    llm           an LLM: an answer in text or JSON
    media         the media library: pictures and sounds, and pools to draw them from
"""

from proki.services import activitywatch as aw
from proki.services import jev, nats

__all__ = ["aw", "jev", "nats"]