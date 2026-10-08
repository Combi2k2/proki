"""NATS, proki's message bus: questions to you, jev and an LLM, and messages to the UI.
proki runs the NATS server itself (services/supervisor.py), like ActivityWatch's.

    await bus.subscribe("proki.ask.llm", handle)                       this part answers that subject
    await bus.request("proki.ask.usr", {"context": ...}, timeout=120)  ask, and wait for the reply
    await bus.publish("proki.ui", {"type": "alarm", ...})              a one-way message

A subject is a mailbox's name. A request goes to one of the subject's subscribers, and the
reply comes back to a private one-off mailbox the bus makes for that request. No reply
(nobody answered, or not in time) is None. A subscriber is `async def handle(data)`, and
what it returns is the reply: it can take its time (an LLM, a question you haven't
answered yet) without holding anything else up.

    NatsBus    a NATS server: every part can be its own process, each subject a queue
    LocalBus   in this process, for when there's no NATS server, and for tests
"""

from __future__ import annotations

import asyncio
import socket
import json
import nats
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Any, Protocol

# the programs proki runs (services/supervisor.py). The server's address (the config's
# [nats] host and port) is added to its command where it's started
MODULES = ["nats-server",]

Handler = Callable[[dict], Awaitable[dict | None]]  # a subscriber: its reply (ignored for one-way messages)


class Bus(Protocol):
    async def subscribe(self, subject: str, handler: Handler, workers: int = 1) -> None:
        """Handle `subject`'s messages, `workers` at a time."""

    async def request(self, subject: str, data: dict, timeout: float) -> dict | None:
        """The reply (None: nobody answered, or not in `timeout` seconds)."""

    async def publish(self, subject: str, data: dict) -> None:
        """A one-way message to every subscriber of `subject`."""

    async def close(self) -> None:
        """Stop."""


class LocalBus(Bus):
    """Subjects in this process: a request goes to the subject's first subscriber."""

    def __init__(self):
        self.handlers: dict[str, list[tuple[Handler, asyncio.Semaphore]]] = {}

    async def subscribe(self, subject: str, handler: Handler, workers: int = 1) -> None:
        self.handlers.setdefault(subject, []).append((handler, asyncio.Semaphore(workers)))

    async def request(self, subject: str, data: dict, timeout: float) -> dict | None:
        if not self.handlers.get(subject):  return None  # no responders

        handler, workers = self.handlers[subject][0]
        with suppress(Exception):  # a timeout, a handler that fails: no reply
            async with workers:
                return await asyncio.wait_for(handler(data), timeout)
        return None

    async def publish(self, subject: str, data: dict) -> None:
        for handler, workers in self.handlers.get(subject, []):
            with suppress(Exception):
                async with workers:
                    await handler(data)

    async def close(self) -> None:
        self.handlers.clear()


class NatsBus(Bus):
    """A connection to a NATS server. Subscribers of a subject share a queue group, so
    several processes can serve one subject and each message goes to one of them."""

    def __init__(self, client: Any):
        self.client = client  # nats-py's connection (`NatsBus.connect`)

    @classmethod
    async def connect(cls, host: str, port: int, timeout: float = 2) -> NatsBus:
        """Connect to the server at `host`:`port` (the config's [nats])."""
        client = await nats.connect(
            f"nats://{host}:{port}",
            connect_timeout=timeout,
            allow_reconnect=True,
            max_reconnect_attempts=-1,  # a restarted server is found again
        )
        return cls(client)

    @staticmethod
    def is_up(host: str, port: int) -> bool:
        """Whether a server listens at `host`:`port` (before connecting: proki may have to start it)."""
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            return False

    async def subscribe(self, subject: str, handler: Handler, workers: int = 1) -> None:
        limit = asyncio.Semaphore(workers)

        async def answer(message: Any) -> None:
            reply = None
            with suppress(Exception):  # a handler that fails: no reply
                async with limit:
                    reply = await handler(_decode(message.data))
            if message.reply and reply is not None:  await message.respond(_encode(reply))

        async def received(message: Any) -> None:  # NATS waits for this: the work goes on a task of its own
            asyncio.create_task(answer(message))

        await self.client.subscribe(subject, queue=subject, cb=received)

    async def request(self, subject: str, data: dict, timeout: float) -> dict | None:
        try:
            return _decode((await self.client.request(subject, _encode(data), timeout=timeout)).data)
        except Exception:  # no responders, a timeout, a lost connection: no reply
            return None

    async def publish(self, subject: str, data: dict) -> None:
        await self.client.publish(subject, _encode(data))

    async def close(self) -> None:
        with suppress(Exception):
            await self.client.drain()


def _encode(data: dict) -> bytes:
    return json.dumps(data).encode()


def _decode(raw: bytes) -> dict:
    return json.loads(raw)
