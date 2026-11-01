"""The message bus (services/nats.py): the in-process one, and NATS when nats-server is installed."""
import asyncio
import socket

import pytest

from proki import platforms
from proki.services.nats import LocalBus, NatsBus
from proki.services.supervisor import Supervisor
from proki.utils import find_commands

HOST = "127.0.0.1"
FOUND = find_commands(["nats-server"], platforms.current().NATS_DIRS, platforms.current().EXE)


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
async def test_nats_takes_only_who_has_its_token(tmp_path):
    with socket.socket() as s:  # a free port: a server an earlier run left can't answer for this one
        s.bind((HOST, 0))
        port = s.getsockname()[1]
    conf = tmp_path / "nats.conf"
    conf.write_text('authorization { token: "secret" }\n')
    server = Supervisor("NATS", {"nats-server": [*FOUND["nats-server"], "-a", HOST, "-p", str(port), "-c", str(conf)]},
                        lambda: NatsBus.is_up(HOST, port), tmp_path)
    try:
        assert server.start() == "NATS started by Proki"
        with pytest.raises(Exception):
            await asyncio.wait_for(NatsBus.connect(HOST, port, timeout=1), 3)
        bus = await NatsBus.connect(HOST, port, token="secret")
        try:
            await exercise(bus)
        finally:
            await bus.close()
    finally:
        server.stop()
