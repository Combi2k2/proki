"""The channels: how proki asks you, jev or an LLM, on the message bus (services/nats.py).

A channel is a queue on the bus. One side asks and waits, a worker on the other side
answers. Each file holds both sides of one channel:

    popup.py   "usr": you, through the popup (and its one-way messages: pokes, ...)
    jev.py     "jev": jev's answers to named questions, with how likely each answer is
    llm.py     "llm": an LLM writes JSON for a schema, or text
    base.py    what they share: the bus, and the call that asks and waits

The app sets the bus (`Channels.bus`) and starts the workers (`jev.serve`, `llm.serve`).
The popup's worker is the UI.
"""

from proki.channels import jev, llm
from proki.channels.base import Channels, queued
from proki.channels.popup import Popup

__all__ = ["Channels", "Popup", "jev", "llm", "queued"]
