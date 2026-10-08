import threading
import time
from collections import Counter
from datetime import timedelta

import pytest

from proki.core.ask import Asking
from proki.core.later import Later
from proki.core.programs import Program
from proki.services.nats import LocalBus
from proki.core.rules import Rule
from proki.core.primitives import Depth, Label, Primitive, Recording
from proki.core.signals import Stream, Variable


@pytest.fixture(autouse=True)
def fresh_signals():
    """Each test starts with no signals, no rules and no run (the registry and the clock are global)."""
    saved, saved_rules = dict(Stream.registry), dict(Rule.registry)
    Stream.registry.clear()
    Rule.registry.clear()
    Program.registry.clear()
    Recording.client, Recording.rec = None, None  # no ActivityWatch: tests hand in recordings (`replay`)
    Stream.now = None
    Stream.live = None
    Stream.cycle = timedelta(seconds=10)
    Variable.store = None
    Asking.bus, Asking.out = LocalBus(inline=True), Counter()  # a bus of its own: nothing answers until a test says so
    Later.reset()
    Program.context = None
    label_of, depth_of = Label.label_of, Depth.depth_of
    yield
    Asking.bus.close()  # questions still waiting get no answer at once: no thread outlives the test
    Label.label_of, Depth.depth_of = label_of, depth_of
    Stream.registry.clear()
    Stream.registry.update(saved)
    Rule.registry.clear()
    Rule.registry.update(saved_rules)


def replay(now, rec) -> None:
    """The cycles up to `now`, on recording `rec` (in place of what ActivityWatch would give)."""
    Recording.rec = rec
    Primitive.run(now)


def replay_cycle(engine, *args, rec) -> None:
    """An engine's cycle, on recording `rec`."""
    Recording.rec = rec
    engine.cycle(*args)


def settle() -> None:
    """Wait (2 s at most) until a background call has finished, its result ready for the next turn."""
    deadline = time.monotonic() + 2
    while Later._done.empty() and time.monotonic() < deadline:
        time.sleep(0.005)


class FakeUi:
    """A stand-in UI on the bus: it gets your questions ("proki.ask.usr") and keeps the
    one-way messages ("proki.ui"). `click` answers a question, `questions` waits for them."""

    def __init__(self):
        self.requests: list[dict] = []
        self.replies: dict = {}
        self.sent: list[dict] = []
        self.lock = threading.Lock()
        Asking.bus.subscribe("proki.ask.usr", self._asked)
        Asking.bus.subscribe("proki.ui", lambda message, reply: self.sent.append(message))

    def _asked(self, request, reply):
        with self.lock:
            self.requests.append(request)
            self.replies[request["id"]] = reply

    def questions(self, at_least: int = 0) -> list[dict]:
        """The questions asked so far (waiting a moment for `at_least` of them: they're asked from other threads)."""
        deadline = time.monotonic() + 2
        while len(self.requests) < at_least and time.monotonic() < deadline:
            time.sleep(0.005)
        return list(self.requests)

    def labels(self, request: dict) -> list[str] | None:
        return None if request["options"] is None else [label for label, _ in request["options"]]

    def click(self, option, request: dict | None = None) -> None:
        """Answer (the last question by default) with an option's label, a text, or None; the
        answer is ready for the engine's next turn when this returns."""
        request = request or self.questions(1)[-1]
        labels = self.labels(request)
        answer = option if labels is None else (labels.index(option) if option in labels else None)
        waiting = Later._done.qsize()
        self.replies.pop(request["id"])({"answer": answer})
        deadline = time.monotonic() + 2
        while Later._done.qsize() <= waiting and time.monotonic() < deadline:
            time.sleep(0.005)


@pytest.fixture
def ui():
    return FakeUi()
