"""Slow calls (reading a week of history, ...) off the engine's turn: `Later.run(fn, then)`
calls fn() in a worker thread. `then(result)` runs at the engine's next turn
(`Later.deliver()`), never in between. A call that fails gives None. `Later.put(then,
result)` hands over a result that came some other way (an answer over the bus, core/ask.py).
"""

from __future__ import annotations

import queue
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any, ClassVar


class Later:
    pool: ClassVar[ThreadPoolExecutor | None] = None  # made when first needed
    _done: ClassVar[queue.Queue[tuple[Callable[[Any], None], Any]]] = queue.Queue()

    @classmethod
    def run(cls, fn: Callable[[], Any], then: Callable[[Any], None]) -> None:
        if cls.pool is None:
            cls.pool = ThreadPoolExecutor(max_workers=2)

        def work() -> None:
            try:
                result = fn()
            except Exception:  # a failure arrives as None
                result = None
            cls._done.put((then, result))

        cls.pool.submit(work)

    @classmethod
    def put(cls, then: Callable[[Any], None], result: Any) -> None:
        """`then(result)` at the engine's next turn (from any thread: a reply over the bus)."""
        cls._done.put((then, result))

    @classmethod
    def deliver(cls) -> None:
        while True:
            try:
                then, result = cls._done.get_nowait()
            except queue.Empty:
                return
            then(result)

    @classmethod
    def reset(cls) -> None:
        cls._done = queue.Queue()
