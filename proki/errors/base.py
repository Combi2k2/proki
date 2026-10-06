"""`ProkiError`, the root of proki's errors: a message, and where it happened.

`where` lists what the error happened in, outermost first. Code that knows more context
adds it on the way out with `within`, so the final message reads from the outside in:

    e.within("config.json", "rule 'focus_high'")
    →  config.json: rule 'focus_high': lhs is missing
"""

from __future__ import annotations

from typing import Self


class ProkiError(Exception):
    """An error proki raises on purpose: `message`, inside the contexts in `where`."""

    def __init__(self, message: str, *where: str):
        super().__init__(message)
        self.message = message
        self.where = list(where)

    def within(self, *where: str) -> Self:
        """Add the contexts `where` around the error (outermost first), and return it, so
        it can be re-raised: `raise e.within("config.json") from None`."""
        self.where[:0] = where
        return self

    def __str__(self) -> str:
        return ": ".join([*self.where, self.message])
