"""A message bus: parts of an app, in one process or several, sending each other JSON.

    await bus.subscribe("orders.new", handle)                  answer that subject: `async def handle(data)`,
                                                               what it returns the reply
    await bus.request("orders.new", {"item": ...}, timeout=5)  ask, and wait for the reply (None: none in time)
    await bus.publish("orders.shipped", {"id": ...})           a message, no reply

    NatsBus    over a NATS server: each part can be its own process
    LocalBus   in this process: no server, and for tests
"""

from __future__ import annotations

import asyncio
import json
import socket
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Any, Protocol

import nats

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
    """The bus in this process."""

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
    """The bus over a NATS server: several processes can answer one subject, each message answered once."""

    def __init__(self, client: Any):
        self.client = client  # nats-py's connection (`NatsBus.connect`)

    @classmethod
    async def connect(cls, host: str, port: int, timeout: float = 2) -> NatsBus:
        """Connect to the server at `host`:`port`."""
        client = await nats.connect(
            f"nats://{host}:{port}",
            connect_timeout=timeout,
            allow_reconnect=True,
            max_reconnect_attempts=-1,  # a restarted server is found again
        )
        return cls(client)

    @staticmethod
    def is_up(host: str, port: int) -> bool:
        """Whether a server is up at `host`:`port`."""
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
