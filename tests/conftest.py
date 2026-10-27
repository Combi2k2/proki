from __future__ import annotations

import asyncio
from collections import Counter
from datetime import timedelta

import keyring
import pytest

from proki.channels import Channels, Popup
from proki.channels.base import Question
from proki.core.actions import Lock, Open, Poke
from proki.core.programs import Program
from proki.services.nats import LocalBus
from proki.core.rules import Rule
from proki.core.primitives import Depth, Label, Primitive, Recording
from proki.core.signals import Stream, Variable
from proki.engine import Engine


@pytest.fixture(autouse=True)
def fresh_signals():
    """Each test starts with no signals, no rules and no run (the registry and the clock are global)."""
    saved, saved_rules = dict(Stream.registry), dict(Rule.registry)
    Stream.registry.clear()
    Rule.registry.clear()
    Program.stop()
    Program.registry.clear()
    Recording.client, Recording.rec = None, None  # no ActivityWatch: tests hand in recordings (`replay`)
    Stream.now = None
    Stream.live = None
    Stream.cycle = timedelta(seconds=10)
    Variable.store = None
    Channels.bus, Channels.out = LocalBus(), Counter()  # a bus of its own: nothing answers until a test says so
    Question.kept.clear()  # no answers kept from another test
    Poke.handler, Open.handler = Popup.poke, Popup.open
    Lock.handler = lambda: Popup.send({"type": "lock"})  # a stand-in: tests never lock the screen
    label_of, depth_of = Label.label_of, Depth.depth_of
    build = Engine.build
    Engine.build = lambda engine, specs: (made(), build(engine, specs))[1]  # the programs in code's `note` first, as in the app
    yield
    Engine.build = build
    Label.label_of, Depth.depth_of = label_of, depth_of
    Stream.registry.clear()
    Stream.registry.update(saved)
    Rule.registry.clear()
    Rule.registry.update(saved_rules)


@pytest.fixture(autouse=True)
def keychain(monkeypatch) -> dict:
    """A keychain of the test's own: no test reads or changes yours. The keys kept, by name."""
    kept: dict[tuple[str, str], str] = {}
    monkeypatch.setattr(keyring, "get_password", lambda service, name: kept.get((service, name)))
    monkeypatch.setattr(keyring, "set_password", lambda service, name, key: kept.__setitem__((service, name), key))
    monkeypatch.setattr(keyring, "delete_password", lambda service, name: kept.pop((service, name)))
    return kept


def programs_folder(path, data: dict, files: dict | None = None):
    """A programs' folder at `path` (made if missing): main.json from `data`, and a file of
    <name>.json beside it for each program of `data["programs"]` (a test's shorthand, by its "name") and of
    `files` (name → the file's JSON). Returns the folder."""
    import json

    data = dict(data)
    path.mkdir(parents=True, exist_ok=True)
    for old in path.glob("*.json"):  # from a folder written before at `path`
        old.unlink()
    for spec in data.pop("programs", []):
        spec = dict(spec)
        (path / f"{spec.pop('name')}.json").write_text(json.dumps({"program": spec}))
    for name, spec in (files or {}).items():
        (path / f"{name}.json").write_text(json.dumps(spec))
    (path / "main.json").write_text(json.dumps(data))
    return path


def with_notes(data: dict) -> dict:
    """`data`, a main.json's, with the shipped one's notes: their variables and signals."""
    import json
    from proki import settings

    main = json.loads((settings.SHIPPED_DIR / "main.json").read_text())
    pick = lambda kind: [spec for spec in main[kind] if spec["name"].split(".")[0] == "notes"]
    return data | {kind: [*data.get(kind, []), *pick(kind)] for kind in ("variables", "signals")}


def built(path, programs=None):
    """What the programs' folder at `path` makes (its files read into specs, then built), in
    place of what's made before. `programs`: which program files, all of them by default."""
    from proki.model import Builder, Defaults

    made()
    return Builder(Defaults(path).specs(programs)).build()


def made() -> None:
    """What the code makes before the config is built, that the config reads, if nothing made
    it yet: the track space, on a store of its own, `asking`, and the task and plan spaces, on a
    board of their own."""
    import sqlite3

    from proki.programs.code.base import Live, popup_open
    from proki.programs.code.classify import AppDB, Apps, Track
    from proki.programs.code.work import Work

    if "track" not in Stream.registry:   Track(Apps(AppDB(sqlite3.connect(":memory:")))).make()
    if "asking" not in Stream.registry:  Live("asking", popup_open, type="boolean")
    if "work.task" not in Stream.registry:
        Work(sqlite3.connect(":memory:")).make()


def replay(now, rec) -> None:
    """The cycles up to `now`, on recording `rec` (in place of what ActivityWatch would give)."""
    Recording.rec = rec
    Primitive.run(now)


async def replay_cycle(engine, *args, rec) -> None:
    """An engine's cycle, on recording `rec`."""
    Recording.rec = rec
    await engine.cycle(*args)
    await settle()  # a question just asked reaches the UI


async def tick(now) -> None:
    """The cycle at `now`, as the engine runs it: every stream, then the programs whose wait is
    over."""
    Stream.tick(now)
    Program.tick(now)
    await settle()


async def settle(turns: int = 5) -> None:
    """Let the loop run a few turns: answers reach the ones waiting for them."""
    for _ in range(turns):
        await asyncio.sleep(0)


class FakeUi:
    """A stand-in UI on the bus: it gets your questions ("proki.ask.usr") and keeps the
    one-way messages ("proki.ui"). `click` answers a question."""

    def __init__(self):
        self.requests: list[dict] = []
        self.answers: dict = {}  # question id → the future its answer completes
        self.sent: list[dict] = []

    async def serve(self) -> FakeUi:
        await Channels.bus.subscribe("proki.ask.usr", self._asked, workers=100)
        await Channels.bus.subscribe("proki.ui", self._shown)
        return self

    async def _asked(self, request):
        self.requests.append(request)
        self.answers[request["id"]] = asyncio.get_running_loop().create_future()
        return {"answer": await self.answers[request["id"]]}

    async def _shown(self, message):
        self.sent.append(message)

    def questions(self) -> list[dict]:
        return list(self.requests)

    def labels(self, request: dict) -> list[str] | None:
        return None if request["options"] is None else [label for label, _ in request["options"]]

    async def click(self, option, request: dict | None = None) -> None:
        """Answer (the last question by default) with an option's label, a text, or None;
        the one who asked has it when this returns."""
        request = request or self.requests[-1]
        labels = self.labels(request)
        answer = option if labels is None else (labels.index(option) if option in labels else None)
        self.answers.pop(request["id"]).set_result(answer)
        await settle()


@pytest.fixture
async def ui(tmp_path):
    """The stand-in UI, and the media library as shipped, with a questions' pool (in a
    database in memory): what a popup draws its pictures and sounds from."""
    import sqlite3

    from proki import settings
    from proki.services.media import Library

    Popup.lib = Library(sqlite3.connect(":memory:"), settings.ASSETS_DIR, tmp_path / "media", pools=[Popup.POOL])
    Popup.lib.set_pool("questions", ["bugcat/what", "bugcat/hi"])  # as you'd choose them
    yield await FakeUi().serve()
    Popup.lib = None
