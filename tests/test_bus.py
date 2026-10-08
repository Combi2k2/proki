"""The message bus (services/nats.py): the in-process one, and NATS when nats-server is installed."""
import asyncio

import pytest

from proki import platforms
from proki.services import nats
from proki.services.nats import LocalBus, NatsBus
from proki.services.supervisor import Supervisor
from proki.utils import find_commands

HOST, PORT = "127.0.0.1", 14223
FOUND = find_commands(nats.MODULES, platforms.current().NATS_DIRS, platforms.current().EXECUTABLE_SUFFIX)


async def exercise(bus):
    async def double(data):
        return {"got": data["x"] * 2}

    clicked = asyncio.Event()

    async def later(data):  # answers once "you click"
        await clicked.wait()
        return {"late": True}

    seen = []

    async def news(data):
        seen.append(data)

    await bus.subscribe("t.double", double)
    await bus.subscribe("t.later", later)
    await bus.subscribe("t.news", news)

    assert await bus.request("t.double", {"x": 21}, timeout=2) == {"got": 42}
    assert await bus.request("t.nobody", {}, timeout=0.5) is None  # no responders
    asyncio.get_running_loop().call_later(0.1, clicked.set)
    assert await bus.request("t.later", {}, timeout=2) == {"late": True}  # answered later
    clicked.clear()
    assert await bus.request("t.later", {}, timeout=0.2) is None  # not in time

    waiting = asyncio.create_task(bus.request("t.double", {"x": 1}, timeout=2))  # others go on meanwhile
    assert await bus.request("t.double", {"x": 2}, timeout=2) == {"got": 4}
    assert await waiting == {"got": 2}

    await bus.publish("t.news", {"a": 1})
    for _ in range(100):
        if seen:
            break
        await asyncio.sleep(0.01)
    assert seen == [{"a": 1}]


async def test_the_local_bus():
    bus = LocalBus()
    await exercise(bus)
    await bus.close()


@pytest.mark.skipif(FOUND is None, reason="nats-server isn't installed")
async def test_nats(tmp_path):
    FOUND["nats-server"] += ["-a", HOST, "-p", str(PORT)]
    server = Supervisor("NATS", FOUND, lambda: NatsBus.is_up(HOST, PORT), tmp_path)
    assert server.start() == "NATS started by proki"
    bus = await NatsBus.connect(HOST, PORT)
    try:
        await exercise(bus)
    finally:
        await bus.close()
        server.stop()
