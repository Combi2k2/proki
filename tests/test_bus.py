"""The message bus (services/nats.py): the in-process one, and NATS when nats-server is installed."""
import threading
import time

import pytest

from proki import platforms
from proki.services import nats
from proki.services.nats import LocalBus, NatsBus
from proki.services.supervisor import Supervisor
from proki.utils import find_commands

HOST, PORT = "127.0.0.1", 14223
FOUND = find_commands(nats.MODULES, platforms.current().NATS_DIRS, platforms.current().EXECUTABLE_SUFFIX)


def exercise(bus):
    bus.subscribe("t.double", lambda data, reply: reply({"got": data["x"] * 2}))
    waiting = []
    bus.subscribe("t.later", lambda data, reply: waiting.append(reply))
    seen = []
    bus.subscribe("t.news", lambda data, reply: seen.append(data))

    assert bus.request("t.double", {"x": 21}, timeout=2) == {"got": 42}
    assert bus.request("t.nobody", {}, timeout=0.5) is None  # no responders
    threading.Timer(0.1, lambda: waiting[-1]({"late": True})).start()
    assert bus.request("t.later", {}, timeout=2) == {"late": True}  # answered from another thread, later
    assert bus.request("t.later", {}, timeout=0.2) is None  # not in time

    got = []
    done = threading.Event()
    bus.request("t.double", {"x": 1}, 2, callback=lambda reply: (got.append(reply), done.set()))
    done.wait(2)
    assert got == [{"got": 2}]
    done.clear()
    bus.request("t.later", {}, 0.2, callback=lambda reply: (got.append(reply), done.set()))
    done.wait(2)
    assert got[-1] is None  # timed out, once

    bus.publish("t.news", {"a": 1})
    deadline = time.monotonic() + 2
    while not seen and time.monotonic() < deadline:
        time.sleep(0.01)
    assert seen == [{"a": 1}]


def test_the_local_bus():
    bus = LocalBus()
    exercise(bus)
    bus.close()


def test_closing_the_local_bus_answers_whats_waiting():
    bus = LocalBus()
    bus.subscribe("t.never", lambda data, reply: None)
    got = []
    bus.request("t.never", {}, 60, callback=got.append)
    bus.close()
    assert got == [None]


@pytest.mark.skipif(FOUND is None, reason="nats-server isn't installed")
def test_nats(tmp_path):
    FOUND["nats-server"] += ["-a", HOST, "-p", str(PORT)]
    server = Supervisor("NATS", FOUND,
                        lambda: NatsBus.is_up(HOST, PORT), tmp_path)
    assert server.start() == "NATS started by proki"
    bus = NatsBus(HOST, PORT)
    try:
        exercise(bus)
    finally:
        bus.close()
        server.stop()
