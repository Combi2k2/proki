"""The channels: how proki asks you, jev or an LLM, and waits for the answer.

    Popup           you: a question, a message, a page opened
    JevQuestion     jev: named questions, each answered with how likely each answer is
    LLMQuestion     an LLM: a question answered in a type
"""

from proki.channels import jev, llm
from proki.channels.base import Channels, queued
from proki.channels.jev import JevQuestion
from proki.channels.llm import LLMQuestion
from proki.channels.popup import Popup

__all__ = [
    "Channels",
    "JevQuestion",
    "LLMQuestion",
    "Popup",
    "jev",
    "llm",
    "queued"
]
