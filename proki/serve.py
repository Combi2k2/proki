"""What the engine answers for the app, on the message bus.

    proki.app.note     {"text": ...}         a new note, unsorted
    proki.app.quit     {}                    stop proki
    proki.app.session  {"op": "start" or "stop"}   a focus session: the session program takes it
    proki.app.tasks    {"op": ..., ...}      the board: groups, their tasks and the ops suggested
    proki.app.notes    {"op": ..., ...}      the notes' buckets
    proki.app.fields   {"op": ..., ...}      the fields of yours, and the open tasks' values
    proki.app.apps     {"op": ...}           the apps and websites classify knows, and the labels
    proki.app.today    {}                    now: the focus, the last 24 hours, the next task
    proki.app.metrics  {"op": "list"}        every global signal: reported or not, and how its buckets are made
                       {"op": "change", "name": ..., "on": true, "keep": 43200, "method": "mean"}
                                             a persisted one: reported or not, the minutes it keeps, its buckets
                       {"op": "read", "name": ..., "horizon": "week"}   {"buckets": [[start, value], ...], "size": minutes}

The board: a group or a task by its kind of record ("work.groups", "work.tasks"), and the changes
suggested ("ops"):

    {"op": "read"}                                                → {"groups": [...], "tasks": [...], "ops": [...], "rows": {...}}
    {"op": "add", "record": "work.tasks", "group": 3, "name": "..."}    → {"id": 7}
    {"op": "change", "record": "work.tasks", "id": 7, "name": "..."}    → {}
    {"op": "move", "record": "work.tasks", "id": 7, "before": 9}        → {}    last without `before`; not an op
    {"op": "remove", "record": "work.groups", "id": 7}                  → {}    a group with its tasks
    {"op": "work", "id": 7}                                             → {}    work on it now: a session on it
                                                                                 (asked for, if there's none)

The fields of a kind of record (the tasks', "work.tasks", unless the request's "record" says), and
for the tasks', how they weigh them. A change is checked first, then everything's built again
with it (`reload`):

    {"op": "read"}                                                → {"records": [...], "fields": [...], "own": [...],
                                                                     "rows": [...], "contexts": {"jev": ..., "llm": ...}}
                                                                     each field with its type, whether proki came with
                                                                     it, and the programs that set it; each record with
                                                                     its fields' values (the ready tasks, the
                                                                     weightiest first)
    {"op": "define", "field": {"key": "official", "srcs": [...]}} → {}       a new one, or one changed
    {"op": "rename", "key": "official", "to": "formal"}          → {}          its values, and what reads it, with it
    {"op": "remove", "key": "official"}                           → {}          one proki came with: back as it came
    {"op": "rerun", "key": "official", "source": "jev", "id": 7}  → {}          worked out again: without `source`,
                                                                                 each it works out; without `id`,
                                                                                 for every record
    {"op": "context", "channel": "jev", "text": "..."}            → {}          what every question is read under
                                                                                 (empty: back as it came)
    {"op": "set", "key": "official", "id": 7, "value": true}      → {}          yours, for a record

The notes, by bucket ("Unsorted", "Todo", "Idea", "Thought"):

    {"op": "read"}                                                → {"Unsorted": [...], "Todo": [...], ...}
                                                                     an unsorted note with its "sorts_at"; a
                                                                     note dealt with, where (its "link")
    {"op": "add", "bucket": "Idea", "text": "..."}                → {"id": 12}
    {"op": "change", "id": 12, "text": "..."}                     → {}
    {"op": "change", "id": 12, "due": "..."}                      → {}          when it's sorted (ISO)
    {"op": "move", "id": 12, "to": "Todo"}                        → {}
    {"op": "remove", "id": 12}                                    → {}

The apps and websites, by key (an app's name, or a website's host). A change is yours: a label
you pick is confirmed, so it's never asked about again, and `track` is whether it's asked about:

    {"op": "read"}                                                → {"apps": [...], "labels": [...]}
    {"op": "change", "key": "vimeo.com", "label": 3}              → {}          a label's id
    {"op": "change", "key": "vimeo.com", "track": false}          → {}          its label is kept

A mistake answers {"error": "..."}. Times, deadlines too, go as ISO text.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Any

from proki.core.programs import Program
from proki.core.records import ASKS, STAMPS, Field, Records
from proki.core.signals import Signal, Stream
from proki.metrics import Metrics
from proki.model.model import Model
from proki.programs.code.base import find_variable
from proki.programs.code.classify import Apps
from proki.programs.code.work import ROWS, TaskOp, Work
from proki.services.nats import Bus
from proki.storage import plain
from proki.tools import records
from proki.utils import minutes, moment

BUCKETS = ["Unsorted", "Todo", "Idea", "Thought"]  # where a note is, the unsorted first, as the notes say

READS = {  # what the app reads of the config, each of its type: checked as it's built
    "session.active":         "boolean",
    "session.requested":      "boolean",
    "session.stop_requested": "boolean",
    "session.minutes":        "number",
    "focus":                  "number",
    "focus_lines":            {"type": "array", "items": {"type": "number"}},
    "focus_5m":               "number",
    "deep_24h":               "number",
    "shallow_24h":            "number",
    "active_24h":             "number",
    "tasks_open":             "number",
    "note.next_due":          "number",
}


async def serve(bus: Bus, work: Work, quit: Callable[[], None],
                metrics: Metrics | None = None, signals: Callable[[], list[Signal]] = list, apps: Apps | None = None,
                reload: Callable[[], None] = lambda: None, model: Model | None = None) -> None:
    """What the app asks for, answered on `bus` from now on.

        quit        proki stopped
        metrics     what's reported of the signals' history
        signals     the signals as they are now
        apps        the apps and websites, what the app's changes count in from the next cycle
        reload      everything built again, as a field's changed
        model       your programs, changed as a metric keeps more or less
    """
    async def note(request: dict) -> dict:
        text = request.get("text")
        if not isinstance(text, str) or not text.strip():
            return {"error": "a note has some text"}
        noted(text.strip())
        return {}

    async def stop(request: dict) -> dict:
        asyncio.get_running_loop().call_soon(quit)
        return {}

    await bus.subscribe("proki.app.note", note)
    await bus.subscribe("proki.app.quit", stop)
    await bus.subscribe("proki.app.session", answering(on_session))
    await bus.subscribe("proki.app.tasks", answering(lambda request: on_tasks(request, work)))
    await bus.subscribe("proki.app.notes", answering(on_notes))
    await bus.subscribe("proki.app.fields", answering(lambda request: on_fields(request, work, reload)))
    await bus.subscribe("proki.app.apps", answering(lambda request: on_apps(request, apps)))
    await bus.subscribe("proki.app.today", answering(lambda request: today(work)))
    await bus.subscribe("proki.app.metrics", answering(lambda request: on_metrics(request, metrics, signals(), model)))


def answering(handle: Callable[[dict], dict]) -> Callable[[dict], Any]:
    """A handler that answers {"error": ...} for a mistake, instead of no answer."""
    async def answer(request: dict) -> dict:
        try:
            return handle(request)
        except (KeyError, TypeError, ValueError) as e:
            return {"error": f"{e.__class__.__name__}: {e}"}
    return answer


def on_session(request: dict) -> dict:
    """A focus session asked to start or stop: the session program takes it."""
    op = request.get("op")
    if op not in ("start", "stop"):
        raise ValueError(f"op is start or stop ({op!r})")
    find_variable("session.requested" if op == "start" else "session.stop_requested").set(True)
    return {}


def on_tasks(request: dict, work: Work) -> dict:
    """The board read, a group, a task or an op changed, or a task worked on now."""
    op, name, now = request.get("op"), request.get("record"), datetime.now(timezone.utc)
    fields = {k: v for k, v in request.items() if k not in ("op", "record", "id", "before")}
    if op == "read":
        return {"groups": records.read("work.groups"), "tasks": records.read("work.tasks"), "ops": [vars(o) for o in work.ops.read()], "rows": ROWS}
    if op == "work":
        Stream.registry["work.task"].set(work.tasks.get_row(int(request["id"])))  # its time counted from now
        if not find_variable("session.active").value:
            find_variable("session.requested").set(True)
        return {}
    if name == "ops" and op == "add":       return {"id": work.ops.create(TaskOp(None, **fields))}
    if op == "add":                         return {"id": records.add(name, now, **fields)}
    if name == "ops" and op == "change":    work.ops.update(int(request["id"]), **fields)
    elif name == "ops" and op == "remove":  work.ops.delete(int(request["id"]))
    elif op == "change":                    records.change(name, int(request["id"]), now, **fields)
    elif op == "move":                      records.move(name, int(request["id"]), now, request.get("before"))
    elif op == "remove":                    records.remove(name, int(request["id"]))
    else:                                   raise ValueError(f"op is read, add, change, move, remove or work ({op!r})")
    return {}


def on_fields(request: dict, work: Work, reload: Callable[[], None]) -> dict:
    """A kind of record's fields (the tasks', unless `record` says): read, with each record's
    values, or one changed."""
    op, table = request.get("op"), records.table(request.get("record", "work.tasks"))
    if op == "read":
        keys = [*STAMPS, *table.fields, *table.code]
        return {
            "records" : records.kinds(),
            "fields"  : [asdict(f) | {"worked": f.type, "shipped": f.key in table.shipped, "setters": setters(table, f.key)} for f in table.fields.values()],
            "own"     : [*STAMPS, *table.code],
            "rows"    : [{"id": row["id"], "name": str(row.get("name") or row["id"]), "values": {k: row.get(k) for k in keys}} for row in table.current()],
            "contexts": {channel: table.context(channel) for channel in ASKS},
        }
    if op == "define":
        table.define(Field(**request["field"]))
    elif op == "rename":
        table.rename(request["key"], request["to"])
    elif op == "remove":
        table.remove(request["key"])
    elif op == "rerun":
        table.rerun(request["key"], request.get("source"), request.get("id"))
    elif op == "context":
        table.reword(request["channel"], request["text"])
    elif op == "set":
        if (row := table.get_row(request["id"])) is None:
            raise ValueError(f"no record {request['id']!r}")
        row[request["key"]] = request.get("value")
        row.save()
        return {}
    else:
        raise ValueError(f"op is read, define, rename, remove, rerun, context or set ({op!r})")
    reload()
    return {}


def setters(table: Records, key: str) -> list[str]:
    """The programs that set a field of a record."""
    return [p.name for p in Program.registry.values() if any(
        str(getattr(a, "name", "")).endswith(f".{key}") and any(v is table or getattr(v, "table", None) is table for v in a.write())
        for state in p.states.values() for a in state.do)]


def on_notes(request: dict) -> dict:
    """The notes by bucket, or one added, changed, moved or removed."""
    op, id, notes = request.get("op"), request.get("id"), find_variable("note")
    iso = lambda m: None if m is None else moment(m).isoformat()
    if op == "read":
        return {bucket: [{"id": n["id"], "text": n["content"], "at": iso(n.get("at")), "due": iso(n.get("due")),
                          "guess": n.get("guess"), "conf": n.get("conf"), "sorts_at": iso(n.get("due")), "link": n.get("link")}
                         for n in notes.value or [] if n.get("bucket") == bucket] for bucket in BUCKETS}
    if op == "add":
        return {"id": noted(request["text"], request.get("bucket", BUCKETS[0]))}
    if op not in ("change", "move", "remove"):          raise ValueError(f"op is read, add, change, move or remove ({op!r})")
    if all(n["id"] != id for n in notes.value or []):   raise ValueError(f"no note {id!r}")
    changed = {"content": request["text"]} if "text" in request else {}
    if "due" in request:  changed["due"] = minutes(datetime.fromisoformat(request["due"])) if request["due"] else current("note.next_due")
    if op == "move":      changed["bucket"] = request["to"]
    notes.set([n | changed if n["id"] == id else n for n in notes.value if n["id"] != id or op != "remove"])
    return {}


def noted(text: str, bucket: str = BUCKETS[0]) -> int:
    """A new note, as a program notes one: its id."""
    notes, at = find_variable("note"), minutes(datetime.now(timezone.utc))
    made      = {"id": max((n["id"] for n in notes.value or []), default=0) + 1, "content": text, "bucket": bucket,
                 "at": at, "due": current("note.next_due") or at, "link": None}  # before a cycle: at once
    notes.set([*(notes.value or []), made])
    return made["id"]


def on_apps(request: dict, apps: Apps | None) -> dict:
    """Each app and website, its label by its id (None: none yet), and every label, or one app changed."""
    op, key = request.get("op"), request.get("key")
    if op == "read":
        if apps is None:
            return {"apps": [], "labels": []}
        known = apps.known()
        return {"apps"  : [plain(app) | {"label": app.label if app.label in known else None} for app in apps.rows.values()],
                "labels": [plain(label) | {"depth": label.depth.value} for label in known.values()]}
    if op != "change":                         raise ValueError(f"op is read or change ({op!r})")
    if apps is None or apps.get(key) is None:  raise ValueError(f"no app or website {key!r}")
    changed = {}
    if "label" in request:
        label = request["label"]
        if type(label) is not int or label not in apps.known():
            raise ValueError(f"no label {label!r}")
        changed |= {"label": label, "source": "usr", "conf": None, "track": True}  # yours: confirmed
    if "track" in request:  changed["track"] = bool(request["track"])
    if not changed:         raise ValueError("a change is to its label or track")
    apps.keep(key, datetime.now(timezone.utc), **changed)
    return {}


def today(work: Work, now: Callable[[], datetime] = lambda: datetime.now().astimezone()) -> dict:
    """Now: focus now, and today's (`day`: the minutes focused as the day clock counts them, the
    week's, the days in a row the goal was reached), the last 24 hours (minutes of deep and
    shallow work, active), whether a session runs, the next task (the one to start now, the
    weightiest first): with its group, and its deadline (its own, or else its group's), and the
    three after it."""
    tasks   = sorted((t for t in work.tasks.current() if t["start"] is not None), key=lambda t: -t["start"])
    shown   = lambda task: {"task": records.shown(task), "group": records.shown(work.groups.get_row(task["group"]))}
    counted = {"focused": v} if (v := current("focused_today")) is not None else {}
    return {
        "focus"          : current("focus"),
        "day"            : day(now(), current("focus_lines") or [0.35, 0.5], current("focus_goal") or 240)
                           | counted | {"week": current("focused_week"), "streak": current("goal_streak")},
        "deep_minutes"   : current("deep_24h"),
        "shallow_minutes": current("shallow_24h"),
        "active_minutes" : current("active_24h"),
        "in_session"     : bool(current("session.active")),
        "tasks_open"     : current("tasks_open"),
        "next"           : shown(tasks[0]) | {"deadline": moment(due).isoformat() if (due := tasks[0]["deadline"]) else None} if tasks else None,
        "after"          : [shown(task) for task in tasks[1:4]],
    }


def current(name: str) -> Any:
    """What the config's `name` is now (None: there's no such name)."""
    return Stream.registry[name].current() if name in Stream.registry else None


def day(now: datetime, lines: list[float], goal: float, every: int = 5) -> dict:
    """Today's focus, from midnight: its value each `every` minutes you were active (its
    history's, as it was then), the lines between its bands (low to high), the minutes of it
    above the highest (focused), and the minutes focused you aim for."""
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    kept     = lambda name: sorted(Stream.storage.load(name, midnight - timedelta(minutes=every))) if Stream.storage else []
    focus, engaged = kept("focus_history"), kept("engaged_history")
    def at(rows: list, t: datetime) -> Any:  # the value it had at t: its last row before
        found = [v for when, v in rows if when <= t]
        return found[-1] if found else None
    samples = [f for i in range(int((now - midnight).total_seconds() // 60 // every))
               if (f := at(focus, t := midnight + timedelta(minutes=i * every))) is not None and (at(engaged, t) or 0) >= 0.5]
    return {"samples": samples, "every": every, "lines": sorted(lines), "goal": goal,
            "focused": every * sum(f >= max(lines) for f in samples)}


def on_metrics(request: dict, metrics: Metrics | None, signals: list[Signal], model: Model | None) -> dict:
    """Every global signal as a metric, one's buckets over a horizon, or how one's reported and kept."""
    op, named = request.get("op"), {s.name: s for s in signals}
    if metrics is None:                     raise ValueError("no metrics here")
    if op == "list":                        return {"metrics": metrics.list(signals)}
    if request.get("name") not in named:    raise KeyError(f"no signal {request.get('name')!r}")
    if op == "read":                        return metrics.read(named[request["name"]], request.get("horizon", "week"))
    if op != "change":                      raise ValueError(f"op is list, change or read ({op!r})")
    if not (signal := named[request["name"]]).persist:
        raise ValueError(f"{signal.name} isn't persisted: its history isn't saved")
    metrics.choose(signal.name, **{k: request[k] for k in ("on", "method") if k in request})
    if "keep" in request:
        if model is None:
            raise ValueError("no programs here to change")
        model.update("signal", {"name": signal.name}, {"backfill": request["keep"]})
    return {}
