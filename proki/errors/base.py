"""The root of what proki raises on purpose: `ProkiError`, a message and where it happened.

`where` is what the error was in, outermost first; whoever knows more context adds it on
the way out (`e.within("config.json", "rule 'focus_high'")`), so the message reads from the
outside in:

    config.json: rule 'focus_high': lhs is missing
"""

from __future__ import annotations

from typing import Self


class ProkiError(Exception):
    def __init__(self, message: str, *where: str):
        super().__init__(message)
        self.message = message
        self.where = list(where)

    def within(self, *where: str) -> Self:
        """The same error, inside `where` (the contexts around it, outermost first)."""
        self.where[:0] = where
        return self

    def __str__(self) -> str:
        return ": ".join([*self.where, self.message])
