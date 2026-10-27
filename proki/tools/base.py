"""A tool: something a store can do, said for whoever uses it, the app or an AI agent."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Tool:
    """A tool, by its name.

        desc        what it does, for whoever calls it
        args        each argument's JSON schema, by name
        run         what it does with them: its answer as JSON (None: done)
        required    the arguments it can't go without
        readonly    it only reads
        undoable    what it changes can't be had back
    """

    name     : str
    desc     : str
    args     : dict
    run      : Callable[[dict], Any]
    required : tuple[str, ...] = ()
    readonly : bool            = False
    undoable : bool            = False
