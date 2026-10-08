"""NATS, proki's message bus: questions to you, jev and an LLM, and messages to the UI.
proki runs the NATS server itself (services/supervisor.py), like ActivityWatch's.

    bus.subscribe("proki.ask.llm", handle)                        this part answers that subject
    bus.request("proki.ask.usr", {"context": ...}, timeout=120)   ask, and wait for the reply
    bus.request(..., callback=got)                                ask, and don't wait: got(reply) later
    bus.publish("proki.ui", {"type": "alarm", ...})               a one-way message

A subject is a mailbox's name. A request goes to one of the subject's subscribers, and the
reply comes back to a private one-off mailbox the bus makes for that request. No reply
(nobody answered, or not in time) is None. A subscriber answers with `reply(dict)`, from
any thread, now or later. Its handler runs on a worker thread of its own pool (`workers`
at a time), so a slow one (an LLM, a question you haven't answered) never holds up others.

    NatsBus    a NATS server: every part can be its own process, each subject a queue
    LocalBus   in this process, for when there's no NATS server, and for tests
"""

from __future__ import annotations

import asyncio
import json
import socket
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from typing import Any, Protocol

# the programs proki runs (services/supervisor.py); the server's address (the config's
# [nats] host and port) is added to its command where it's started
MODULES = ["nats-server"]

Reply    = Callable[[dict], None]               # answers a request: reply({"answer": ...})
Handler  = Callable[[dict, Reply], None]        # a subscriber: handler(data, reply)
Callback = Callable[[dict | None], None]        # gets a request's reply, or None


class Bus(Protocol):
    def subscribe(self, subject: str, handler: Handler, workers: int = 1) -> None:
        """Handle `subject`'s messages: `workers` at a time, each on a thread of its pool."""

    def request(self, subject: str, data: dict, timeout: float, callback: Callback | None = None) -> dict | None:
        """Send, and wait for the reply (None: nobody answered, or not in `timeout` seconds).
        With a `callback`, don't wait: `callback(reply or None)`, once, from any thread."""

    def publish(self, subject: str, data: dict) -> None:
        """A one-way message to every subscriber of `subject`."""

    def close(self) -> None:
        """Stop. What's still waiting gets no reply."""


class LocalBus(Bus):
    """Subjects in this process: a request goes to the subject's first subscriber.
    `inline`: handlers run on the caller's thread, not a pool's (tests: nothing races)."""

    def __init__(self, inline: bool = False):
        self.handlers: dict[str, list[tuple[Handler, ThreadPoolExecutor]]] = {}
        self.waiting:  dict[threading.Timer, Callback] = {}    # each request's timeout, and how to finish it
        self.inline = inline
        self.closed = False

    def subscribe(self, subject: str, handler: Handler, workers: int = 1) -> None:
        pool = ThreadPoolExecutor(max_workers=workers)
        self.handlers.setdefault(subject, []).append((handler, pool))

    def request(self, subject: str, data: dict, timeout: float, callback: Callback | None = None) -> dict | None:
        if callback is None:  # wait: a callback of our own, and an event
            done, box = threading.Event(), []
            self.request(subject, data, timeout, lambda reply: (box.append(reply), done.set()))
            done.wait()
            return box[0]

        if self.closed or not self.handlers.get(subject):  # no responders
            callback(None)
            return None

        handler, pool = self.handlers[subject][0]
        lock, finished = threading.Lock(), []

        def finish(reply: dict | None) -> None:  # the reply, or the timeout: whichever comes first
            with lock:
                if finished:  return
                finished.append(True)
            timer.cancel()
            self.waiting.pop(timer, None)
            callback(reply)

        timer = threading.Timer(timeout, finish, [None])
        timer.daemon = True
        self.waiting[timer] = finish

        timer.start()
        self._call(pool, handler, data, finish)
        return None

    def publish(self, subject: str, data: dict) -> None:
        for handler, pool in self.handlers.get(subject, []):
            self._call(pool, handler, data, lambda reply: None)

    def close(self) -> None:
        self.closed = True
        for finish in list(self.waiting.values()):
            finish(None)
        for handlers in self.handlers.values():
            for _, pool in handlers:
                pool.shutdown(wait=False, cancel_futures=True)

    def _call(self, pool: ThreadPoolExecutor, handler: Handler, data: dict, reply: Reply) -> None:
        if self.inline:     _safely(handler, data, reply)
        else:               pool.submit(_safely, handler, data, reply)


class NatsBus(Bus):
    """A connection to a NATS server, on an asyncio loop of its own thread (the rest of
    proki isn't async). Subscribers of a subject share a queue group, so several processes
    can serve one subject and each message goes to one of them."""

    def __init__(self, host: str, port: int, connect_timeout: float = 2):
        """Connect to the server at `host`:`port` (the config's [nats])."""
        import nats

        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.loop.run_forever, name="nats", daemon=True).start()

        connecting = nats.connect(
            f"nats://{host}:{port}",
            connect_timeout=connect_timeout,
            allow_reconnect=True,
            max_reconnect_attempts=-1,  # a restarted server is found again
        )
        self.client = self._run(connecting, connect_timeout + 1)
        self.pools: list[ThreadPoolExecutor] = []

    @staticmethod
    def is_up(host: str, port: int) -> bool:
        """Whether a server listens at `host`:`port` (before connecting: proki may have to start it)."""
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            return False

    def subscribe(self, subject: str, handler: Handler, workers: int = 1) -> None:
        pool = ThreadPoolExecutor(max_workers=workers)
        self.pools.append(pool)

        async def received(message: Any) -> None:
            def reply(answer: dict) -> None:
                if message.reply:  self._soon(message.respond(_encode(answer)))

            pool.submit(_safely, handler, _decode(message.data), reply)

        self._run(self.client.subscribe(subject, queue=subject, cb=received), 5)

    def request(self, subject: str, data: dict, timeout: float, callback: Callback | None = None) -> dict | None:
        sent = self._soon(self.client.request(subject, _encode(data), timeout=timeout))

        def reply(future: Any) -> dict | None:
            try:
                return _decode(future.result().data)
            except Exception:  # no responders, a timeout, a lost connection: no answer
                return None

        if callback is not None:
            sent.add_done_callback(lambda future: callback(reply(future)))
            return None

        with suppress(Exception):
            sent.result(timeout + 1)  # wait
        return reply(sent)

    def publish(self, subject: str, data: dict) -> None:
        self._soon(self.client.publish(subject, _encode(data)))

    def close(self) -> None:
        with suppress(Exception):
            self._run(self.client.drain(), 5)
        for pool in self.pools:
            pool.shutdown(wait=False, cancel_futures=True)
        self.loop.call_soon_threadsafe(self.loop.stop)

    def _soon(self, coroutine: Any) -> Any:
        """Run `coroutine` on the bus's loop, without waiting (a future)."""
        return asyncio.run_coroutine_threadsafe(coroutine, self.loop)

    def _run(self, coroutine: Any, timeout: float | None = None) -> Any:
        """Run `coroutine` on the bus's loop, and wait for its result."""
        return self._soon(coroutine).result(timeout)


def _encode(data: dict) -> bytes:
    return json.dumps(data).encode()


def _decode(raw: bytes) -> dict:
    return json.loads(raw)


def _safely(handler: Handler, data: dict, reply: Reply) -> None:
    """A handler that fails answers nothing (its request times out to no answer)."""
    with suppress(Exception):
        handler(data, reply)
