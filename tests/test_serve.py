"""What the engine answers for the UI (proki/serve.py), over an in-process bus."""

import sqlite3

import pytest

from conftest import built, programs_folder, with_notes
from proki.core.signals import Stream
from proki.programs.code.work import Work
from proki.storage import SCHEMA
from proki.tools import records
from proki.serve import serve
from proki.services.nats import LocalBus


def noting(tmp_path):
    """The shipped notes, made as the engine makes them, today an hour old."""
    from datetime import datetime, timezone
    from proki.utils import minutes

    today = minutes(datetime.now(timezone.utc)) - 60
    built(programs_folder(tmp_path / "programs", with_notes({"variables": [{"name": "today", "value": today}]})))


@pytest.fixture
async def bus(tmp_path):
    db = sqlite3.connect(":memory:")
    db.executescript(SCHEMA)
    local, stopped = LocalBus(), []
    noting(tmp_path)
    await serve(local, Work(db), quit=lambda: stopped.append(True))
    local.stopped = stopped
    return local


async def test_the_board_through_the_bus(bus):
    tasks = lambda request: bus.request("proki.app.tasks", request, 1)
    thesis = (await tasks({"op": "add", "record": "work.groups", "name": "Thesis", "tags": ["papers", "jobs"]}))["id"]
    task = (await tasks({"op": "add", "record": "work.tasks", "group": thesis, "name": "Write the intro", "estimate": 40,
                         "deadline": "2026-10-12T23:59:00+02:00"}))["id"]
    await tasks({"op": "change", "record": "work.tasks", "id": task, "status": "done", "note": "short"})
    board = await tasks({"op": "read"})
    [done] = board["tasks"]
    assert (done["name"], done["deadline"], done["status"], done["note"]) == ("Write the intro", "2026-10-12T21:59:00+00:00", "done", "short")
    assert board["groups"][0]["tags"] == ["papers", "jobs"] and "papers" in board["rows"]["study"]

    await tasks({"op": "change", "record": "work.groups", "id": thesis, "tags": ["jobs", "papers"]})  # into the work row
    assert (await tasks({"op": "read"}))["groups"][0]["tags"] == ["jobs", "papers"]
    await tasks({"op": "remove", "record": "work.groups", "id": thesis})  # with its task
    assert await tasks({"op": "read"}) == {"groups": [], "tasks": [], "ops": [], "rows": board["rows"]}


async def test_notes_through_the_bus(bus):
    notes = lambda request: bus.request("proki.app.notes", request, 1)
    idea = (await notes({"op": "add", "bucket": "Idea", "text": "a focus timer"}))["id"]
    await notes({"op": "change", "bucket": "Idea", "id": idea, "text": "a focus timer that learns"})
    await notes({"op": "move", "id": idea, "from": "Idea", "to": "Thought"})
    buckets = await notes({"op": "read"})
    assert [n["text"] for n in buckets["Thought"]] == ["a focus timer that learns"] and buckets["Idea"] == []
    await notes({"op": "remove", "bucket": "Thought", "id": idea})
    assert (await notes({"op": "read"}))["Thought"] == []

    unsorted = (await notes({"op": "add", "bucket": "Inbox", "text": "call mom"}))["id"]
    [note] = (await notes({"op": "read"}))["Inbox"]
    assert note["sorts_at"] == note["due"] > note["at"]  # the next 04:00
    await notes({"op": "change", "bucket": "Inbox", "id": unsorted, "due": note["at"]})  # sort it now
    assert (await notes({"op": "read"}))["Inbox"][0]["sorts_at"] == note["at"]
    await notes({"op": "move", "id": unsorted, "from": "Inbox", "to": "Todo"})  # filed by you
    assert [n["text"] for n in (await notes({"op": "read"}))["Todo"]] == ["call mom"]


async def test_mistakes_are_answered(bus):
    assert "no record None" in (await bus.request("proki.app.tasks", {"op": "add"}, 1))["error"]
    assert "op is read, add" in (await bus.request("proki.app.tasks", {"op": "rename", "record": "work.tasks"}, 1))["error"]
    assert "notes is of type" in (await bus.request("proki.app.notes", {"op": "add", "bucket": "chores", "text": "x"}, 1))["error"]


async def test_a_note_goes_into_the_inbox_and_quit_stops(tmp_path):
    db = sqlite3.connect(":memory:")
    db.executescript(SCHEMA)
    bus, stopped = LocalBus(), []
    noting(tmp_path)
    await serve(bus, Work(db), quit=lambda: stopped.append(True))
    bus.stopped = stopped
    assert await bus.request("proki.app.note", {"text": "call mom"}, 1) == {}
    assert [(n["content"], n["bucket"]) for n in Stream.registry["notes"].current()] == [("call mom", "Inbox")]  # a new note, in the inbox
    assert "some text" in (await bus.request("proki.app.note", {"text": "  "}, 1))["error"]
    await bus.request("proki.app.quit", {}, 1)
    import asyncio
    await asyncio.sleep(0)
    assert bus.stopped == [True]


async def test_metrics_and_today_through_the_bus():
    from datetime import datetime, timedelta, timezone
    from proki.storage import HistoryDB

    db = sqlite3.connect(":memory:")
    from proki.storage import SCHEMA
    db.executescript(SCHEMA)
    history = HistoryDB(db)
    now = datetime.now(timezone.utc)
    history.save("focus_hourly", now - timedelta(hours=2), 0.4)
    history.save("focus_hourly", now - timedelta(days=9), 0.9)  # older than asked for
    from proki.core.signals import Signal, Stream
    Stream.registry["focus"] = Signal("focus", "0.5")
    hourly = Signal("focus_hourly", "every(focus, 60)", backfill=True, window=timedelta(days=30), persist=True)
    every_cycle = Signal("focus_now", "focus", desc="focus, this cycle")
    local = LocalBus()
    from proki.metrics import Metrics
    metrics, changed = Metrics(db, history), []
    model = type("Model", (), {"update": lambda self, kind, ident, changes: changed.append((kind, ident, changes))})()
    await serve(local, Work(db), quit=lambda: None, metrics=metrics, signals=lambda: [hourly, every_cycle], model=model)
    metrics_ = lambda request: local.request("proki.app.metrics", request, 1)

    listed = (await metrics_({"op": "list"}))["metrics"]
    assert [(m["name"], m["persist"], m["on"], m["keep"], m["method"], m["pace"]) for m in listed] == [
        ("focus_hourly", True, True, 43200.0, "mean", 60.0), ("focus_now", False, False, None, "mean", None)]
    read = await metrics_({"op": "read", "name": "focus_hourly", "horizon": "week"})
    assert read["size"] == 30 and len(read["buckets"]) == 336 and [v for _, v in read["buckets"] if v is not None] == [0.4]
    assert len((await metrics_({"op": "read", "name": "focus_hourly", "horizon": "year"}))["buckets"]) == 365

    assert "isn't persisted" in (await metrics_({"op": "change", "name": "focus_now", "on": True}))["error"]
    assert await metrics_({"op": "change", "name": "focus_hourly", "on": False, "method": "max"}) == {}
    listed = (await metrics_({"op": "list"}))["metrics"]
    assert (listed[0]["on"], listed[0]["method"]) == (False, "max")
    assert await metrics_({"op": "change", "name": "focus_hourly", "keep": 525600}) == {}
    assert changed == [("signal", {"name": "focus_hourly"}, {"backfill": 525600})]  # a year
    assert "no method" in (await metrics_({"op": "change", "name": "focus_hourly", "method": "median"}))["error"]
    assert "no signal" in (await metrics_({"op": "read", "name": "nope"}))["error"]

    from proki.programs.code.base import make_variable
    from proki.utils import minutes as at
    make_variable("time", at(now))  # the config's clock: what's weighed reads it
    Work(db)
    intro = records.add("work.groups", now, name="Intro", deadline=now, tags=["papers"])
    records.add("work.tasks", now, group=intro, name="Write the intro", estimate=40)
    upcoming = (await local.request("proki.app.today", {}, 1))["next"]
    assert (upcoming["task"]["name"], upcoming["group"]["name"], upcoming["group"]["tags"]) == ("Write the intro", "Intro", ["papers"])
    assert upcoming["deadline"] == now.isoformat()  # its group's


async def test_the_apps_through_the_bus():
    from datetime import datetime, timezone
    from proki.programs.code.classify import SHIPPED, App, AppDB, Apps

    db = sqlite3.connect(":memory:")
    db.executescript(SCHEMA)
    AppDB(db).create(App("Krita", True, 3, "jev", datetime(2026, 10, 5, tzinfo=timezone.utc), conf=0.8))
    local = LocalBus()
    await serve(local, Work(db), quit=lambda: None, apps=Apps(AppDB(db)))
    answer = await local.request("proki.app.apps", {"op": "read"}, 1)
    [krita] = [app for app in answer["apps"] if app["key"] == "Krita"]
    assert (krita["label"], krita["source"], krita["conf"]) == (3, "jev", 0.8)
    [label] = [label for label in answer["labels"] if label["id"] == 3]
    assert {k: label[k] for k in ("name", "depth")} == {k: SHIPPED["labels"][2][k] for k in ("name", "depth")}  # the shipped ones, in order


async def test_an_app_changed_in_the_view_counts_at_once():
    from proki.programs.code.classify import DEPTH, AppDB, Apps

    db = sqlite3.connect(":memory:")
    db.executescript(SCHEMA)
    apps, local = Apps(AppDB(db)), LocalBus()
    apps.keep("Krita", apps.get("youtube.com").set_at, label=3, source="jev", conf=0.5)
    await serve(local, Work(db), quit=lambda: None, apps=apps)

    assert await local.request("proki.app.apps", {"op": "change", "key": "Krita", "label": 1}, 1) == {}
    krita = apps.get("Krita")
    assert (krita.label, krita.source, krita.conf, krita.confirmed) == (1, "usr", None, True)  # yours
    assert apps.depth("Krita", None) == DEPTH[apps.known()[1].depth]  # the one @classify reads
    assert AppDB(db).read() and Apps(AppDB(db)).get("Krita").label == 1  # and kept

    assert await local.request("proki.app.apps", {"op": "change", "key": "Krita", "track": False}, 1) == {}
    assert (apps.get("Krita").track, apps.get("Krita").label) == (False, 1)  # its label is kept


async def test_a_wrong_change_to_an_app_is_answered():
    from proki.programs.code.classify import AppDB, Apps

    db = sqlite3.connect(":memory:")
    db.executescript(SCHEMA)
    local, apps = LocalBus(), Apps(AppDB(db))
    await serve(local, Work(db), quit=lambda: None, apps=apps)
    ask = lambda request: local.request("proki.app.apps", {"op": "change", **request}, 1)
    assert "no app or website" in (await ask({"key": "Krita", "label": 1}))["error"]
    assert "no label" in (await ask({"key": "youtube.com", "label": max(apps.known()) + 1}))["error"]
    assert "no label" in (await ask({"key": "youtube.com", "label": True}))["error"]
    assert "its label or track" in (await ask({"key": "youtube.com"}))["error"]
    assert "op is read or change" in (await local.request("proki.app.apps", {"op": "remove"}, 1))["error"]


async def test_the_fields_through_the_bus():
    from datetime import datetime, timedelta, timezone
    from proki.programs.code.base import make_variable
    from proki.storage import SCHEMA

    db = sqlite3.connect(":memory:")
    db.executescript(SCHEMA)
    board, now, reloads = Work(db), datetime.now(timezone.utc), []
    local = LocalBus()
    await serve(local, board, quit=lambda: None, reload=lambda: (reloads.append(1), board.make()))
    fields = lambda request: local.request("proki.app.fields", request, 1)
    assert "no record" in (await fields({"op": "read", "record": "nope"}))["error"]

    make_variable("time", now.timestamp() / 60)
    thesis = records.add("work.groups", now, name="Thesis")
    soon   = records.add("work.tasks", now, group=thesis, name="Due soon", deadline=now + timedelta(days=1))
    records.add("work.tasks", now, group=thesis, name="Someday")
    ranked = lambda read: [t["name"] for t in sorted(read["rows"], key=lambda t: -(t["values"]["score"] or 0))]   # as the app ranks them
    read   = await fields({"op": "read"})
    assert ranked(read) == ["Due soon", "Someday"]  # the weightiest first
    assert read["rows"][0]["values"]["pressing"] > 0 and "ready" in read["own"] and "work.groups" in read["records"]
    score = next(f for f in read["fields"] if f["key"] == "score")
    assert score["shipped"] and score["type"] == "number" and score["srcs"][0]["from"] == "expr"
    assert next(f for f in read["fields"] if f["key"] == "spent")["srcs"] == [{"from": "auto", "initial": 0}]
    assert "{me.name}" in read["contexts"]["jev"]

    formula = lambda expr: {"key": "score", "srcs": [{"from": "expr", "expr": expr}]}
    assert await fields({"op": "define", "field": formula("me.untouched - me.pressing")}) == {}
    assert reloads == [1] and ranked(await fields({"op": "read"})) == ["Someday", "Due soon"]
    assert "nope" in (await fields({"op": "define", "field": formula("nope + 1")}))["error"]
    assert await fields({"op": "remove", "key": "score"}) == {}  # back as it came
    assert ranked(await fields({"op": "read"})) == ["Due soon", "Someday"]
    assert await fields({"op": "set", "key": "away", "id": soon, "value": True}) == {}  # yours, for a record
    assert board.tasks.get_row(soon)["away"] is True


def test_todays_focus_each_five_minutes_you_were_active_and_the_lines_between_its_bands():
    from datetime import datetime, timedelta, timezone
    from proki.core.signals import Stream
    from proki.serve import day
    from proki.storage import SCHEMA, HistoryDB

    db = sqlite3.connect(":memory:")
    db.executescript(SCHEMA)
    history, kept = HistoryDB(db), Stream.storage
    midnight = datetime(2026, 10, 22, tzinfo=timezone.utc)
    for minute, focus, engaged in [(0, 0.8, 1), (10, 0.4, 1), (20, 0.1, 1), (30, 0.0, 0)]:  # each held until the next
        history.save("focus_history", midnight + timedelta(minutes=minute), focus)
        history.save("engaged_history", midnight + timedelta(minutes=minute), engaged)
    Stream.storage = history
    try:
        made = day(midnight + timedelta(minutes=40), [0.5, 0.2, 0.35], 240)
    finally:
        Stream.storage = kept
    assert made["samples"] == [0.8, 0.8, 0.4, 0.4, 0.1, 0.1]  # away from 30 on: not counted
    assert (made["lines"], made["focused"], made["goal"]) == ([0.2, 0.35, 0.5], 10, 240)  # low to high; above the highest
