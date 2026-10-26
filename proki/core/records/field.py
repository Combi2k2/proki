"""A field of yours, and how its asks are put to jev or the LLM: each asked of a record once,
and again only when what it'd ask changes, or it had no answer an hour ago.

    Field       a field of yours: its key, what it is, its sources and its type
    Preface     what jev's or the LLM's questions are read under, for every record
    Store       where a kind of record keeps its fields of yours, or its prefaces
    Cache       where each ask's last question and its answer are kept
    Asker       a table's asks out, one at a time on each channel, each answer kept as it comes
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, TypeVar

from proki.channels import JevQuestion, LLMQuestion
from proki.core.signals import Expr
from proki.types import Type, listof, oftype, schema
from proki.utils import ident

SOURCES = ("expr", "jev", "llm", "user", "auto")
ASKS    = ("jev", "llm")
KEPT    = ("user", "auto")          # the sources kept with a record
TIMEOUT = {"jev": 2, "llm": 60}     # seconds, unless the ask says
RETRY   = timedelta(hours=1)        # an ask with no answer: asked again after

At  = tuple[int, str, str]          # an ask: its record's id, its field's key, its channel
Row = TypeVar("Row")


@dataclass(frozen=True)
class Field:
    """A field of yours: its value from the first of its sources with one.

        Field("hours", "how long it takes", [{"from": "user"}, {"from": "llm", "context": "How long?"}], "number")

        {"from": "user"}                                        set by you
        {"from": "auto", "initial": 0}                          set by a program, `initial` until it is
        {"from": "expr", "expr": ...}                           worked out
        {"from": "jev", "type": ..., "question": ..., ...}      asked of jev, as ask_jev asks
        {"from": "llm", "context": ..., "schema": ...}          asked of the LLM, in its type unless it says

    An ask's `expr` reads its answer as `answer`; its `timeout` is how many seconds it waits.
    """

    key  : str
    desc : str        = ""
    srcs : list[dict] = field(default_factory=list)
    type : Type       = "any"

    def __post_init__(self):
        """ValueError for a name an expression can't read, a type there isn't, or a source
        there isn't, given twice, or not as it's written."""
        if not ident(self.key):                             raise ValueError(f"{self.key!r} can't be a field's name")
        if not oftype(self.srcs, listof("object")):         raise ValueError(f"srcs are a list of {{from, ...}} ({self.srcs!r})")
        froms = [s.get("from") for s in self.srcs]
        if bad := [f for f in froms if f not in SOURCES]:   raise ValueError(f"no source {bad[0]!r}: {', '.join(SOURCES)}")
        if len(set(froms)) < len(froms):                    raise ValueError("each source once at most")
        schema(self.type)  # ValueError: not a type
        for s in self.srcs:
            if s["from"] == "expr" and not s.get("expr"):                       raise ValueError("an expr has an expression")
            if s["from"] == "llm" and not str(s.get("context", "")).strip():    raise ValueError("the LLM's ask has a context")
            if s["from"] == "jev":      JevQuestion.check({k: s[k] for k in ("type", "question", "criteria") if k in s})
            if "expr" in s:             Expr(s["expr"])
            if "schema" in s:           schema(s["schema"])

    @property
    def kept(self) -> bool:
        """Whether it's kept with a record: set by you, or by a program."""
        return any(s["from"] in KEPT for s in self.srcs)


@dataclass(frozen=True)
class Preface:
    """What an ask's question is read under, for every record: jev's or the LLM's."""

    channel : str
    text    : str


class Store(Protocol[Row]):
    """Where a kind of record keeps its fields of yours, or its prefaces, each by its key (a
    field's, a preface's channel). The app gives them."""

    def read(self, key: Any = None, /) -> list[Row]: ...  # the one with `key` (None: all)
    def create(self, row: Row) -> Any: ...                # added, in place of one with its key
    def delete(self, key: Any) -> None: ...


class Cache(Protocol):
    """Where each ask's last question and its answer are kept, by its record, field and
    channel: {"of": the question, "answer": ..., "at": when it was asked}."""

    def read(self, at: At) -> dict | None: ...      # none yet: None
    def keep(self, at: At, kept: dict) -> None: ...
    def pop(self, at: At) -> None: ...              # forgotten: asked again for real


class Asker:
    """A table's asks out for an answer, each by its record, field and channel, one at a time
    on each channel: each answer kept in `cache` as it comes."""

    def __init__(self, cache: Cache):
        self.asking : dict[At, asyncio.Task] = {}
        self.room   = {channel: asyncio.Semaphore(1) for channel in ASKS}
        self.cache  = cache

    def ask(self, at: At, word: Callable[[], dict], timeout: float | None) -> None:
        """`at` asked, unless it's out already or what it'd ask now (`word`) was asked and
        answered, or asked under an hour ago. One with nothing kept is asked for real, not
        answered from what the channel remembers. Read outside the engine: not asked yet."""
        if at in self.asking:  return
        msg, cached, now = word(), self.cache.read(at), datetime.now(UTC)
        if cached and cached["of"] == msg and (cached["answer"] is not None or now - datetime.fromisoformat(cached["at"]) < RETRY):
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        channel, fresh, wait = at[2], cached is None, timeout or TIMEOUT[at[2]]

        async def run() -> None:
            try:
                async with self.room[channel]:
                    if channel == "jev":
                        req = {"question": msg["said"]} | {k: msg[k] for k in ("type", "criteria") if k in msg}
                        res = (await JevQuestion(msg["about"], {"q": req}, wait, fresh).invoke()).get("q")
                    else:
                        res = await LLMQuestion(f"{msg['about']}\n\n{msg['said']}", msg["schema"], wait, fresh).invoke()
                self.cache.keep(at, {"of": msg, "answer": res, "at": now.isoformat()})
            finally:
                del self.asking[at]

        self.asking[at] = loop.create_task(run())

    async def drain(self) -> None:
        """Until every ask out has its answer."""
        while self.asking:
            await asyncio.gather(*self.asking.values())
