"""The planner's board (groups of tasks, tagged) and which task is the one to start now."""

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from proki.core.signals import Stream
from proki.core.signals.expr import Expr
from proki.programs.code.work import ROW, TAGS, TaskOp, Work
from proki.tools import records
from proki.utils import minutes

NOW = datetime(2026, 10, 5, 10, tzinfo=timezone.utc)
DAY = lambda n: NOW + timedelta(days=n)


@pytest.fixture
def board():
    return Work(sqlite3.connect(":memory:"))


def names(rows):
    return [row["name"] for row in rows]


def start():
    """The task to start now, as the config picks it: the weightiest to start, a cycle each."""
    Stream.tick(NOW)
    return Expr("work.tasks[argmax(work.tasks.start)].name").value()


def test_a_board_is_groups_of_tasks(board):
    intro = records.add("work.groups", NOW, name="Write the intro", desc="the first page", deadline=DAY(4), estimate=120,
                      tags=["papers", "research"])
    outline = records.add("work.tasks", NOW, group=intro, name="Outline it", estimate=15)
    records.add("work.tasks", NOW, group=intro, name="Draft it", note="start from the abstract")

    [group] = board.groups.current()
    assert (group["tags"], group["estimate"], group["created_at"], group["updated_at"]) == (["papers", "research"], 120, minutes(NOW), minutes(NOW))
    assert [(t["name"], t["estimate"]) for t in board.tasks.current()] == [("Outline it", 15), ("Draft it", 25)]
    assert board.tasks.current()[0]["deadline"] == minutes(DAY(4))  # its group's
    assert [(t["key"], t["deadline"]) for t in records.read("work.tasks")] == [("outline_it", None), ("draft_it", None)]  # the app's: its own

    later = NOW + timedelta(hours=1)
    records.change("work.tasks", outline, later, status="done", desc="headings only")
    records.change("work.groups", intro, later, status="done")
    done = board.tasks.get_row(outline)
    assert (done["status"], done["desc"], done["done_at"], done["updated_at"]) == ("done", "headings only", minutes(later), minutes(later))
    assert board.groups.get_row(intro)["done_at"] == minutes(later)
    records.change("work.tasks", outline, later, status="open")
    assert board.tasks.get_row(outline)["done_at"] is None  # open again
    with pytest.raises(ValueError, match="no field colour"):
        records.change("work.tasks", outline, colour="red")
    with pytest.raises(ValueError, match="tags is of type"):
        records.change("work.groups", intro, tags=["study"])  # a row, not a tag

    records.remove("work.groups", intro)  # with its tasks
    assert board.groups.current() == board.tasks.current() == []


def test_a_group_checks_its_own_tags(board):
    records.add("work.groups", NOW, name="Thesis", tags=["papers"])
    with pytest.raises(ValueError, match="tags is of type"):
        records.add("work.groups", NOW, name="Thesis", tags=["study"])  # a row, not a tag
    with pytest.raises(ValueError, match="tags is of type"):
        records.add("work.groups", NOW, name="Thesis", tags=["papers", "courses", "skills", "jobs"])
    with pytest.raises(ValueError, match="work.groups needs its name"):
        records.add("work.groups", NOW, desc="no name")


def test_a_field_of_the_boards_keeps_its_type_and_yours_are_added(board):
    from proki.core.records.field import Field
    board.tasks.define(Field("estimate", srcs=[{"from": "expr", "expr": "30"}], type="number"))  # its own type: yours to work out
    board.tasks.define(Field("colour", srcs=[{"from": "user"}], type="string"))
    with pytest.raises(ValueError, match="work.tasks.estimate is the board's: of type number"):
        board.tasks.define(Field("estimate", srcs=[{"from": "user"}], type="string"))
    with pytest.raises(ValueError, match="work.groups.tags is the board's"):
        board.groups.define(Field("tags", srcs=[{"from": "user"}], type="string"))


def test_the_tags_are_the_rows_parts():
    assert TAGS[:3] == ["jobs", "projects", "career"] and TAGS.count("network") == 1
    assert (ROW["papers"], ROW["visa"], ROW["network"]) == ("study", "admin", "work")  # in two rows: the first


def test_moving_keeps_your_order(board):
    thesis = records.add("work.groups", NOW, name="Thesis", tags=["papers"])
    a, b, c = (records.add("work.tasks", NOW, group=thesis, name=name) for name in "abc")
    records.move("work.tasks", c, NOW, before=a)
    assert names(board.tasks.current()) == ["c", "a", "b"]

    visa = records.add("work.groups", NOW, name="Visa", tags=["visa", "trips"])
    records.move("work.groups", visa, DAY(1), before=thesis)
    [first, _] = board.groups.current()
    assert (first["name"], first["updated_at"]) == ("Visa", minutes(NOW))  # moving it alone isn't a change
    with pytest.raises(ValueError, match="tags is of type"):
        records.change("work.groups", thesis, tags=["papers", "courses", "skills", "jobs"])


def test_a_task_is_ready_once_the_tasks_it_needs_are_done(board):
    thesis = records.add("work.groups", NOW, name="Thesis")
    outline = records.add("work.tasks", NOW, group=thesis, name="Outline it", done_when=["5 headings"])
    draft = records.add("work.tasks", NOW, group=thesis, name="Draft it", after=[outline])
    records.add("work.tasks", NOW, group=thesis, name="Check it reads well", after=[draft], checkpoint=True)
    ready = lambda: names(t for t in board.tasks.current() if t["ready"])
    assert ready() == ["Outline it"] and [t["waiting"] for t in board.tasks.current()] == [1, 1, 0]
    records.change("work.tasks", outline, NOW, status="done")
    assert ready() == ["Draft it"]
    records.change("work.groups", thesis, NOW, status="dropped")
    assert ready() == []  # in a group set aside
    assert board.tasks.current()[0]["done_when"] == ["5 headings"] and board.tasks.current()[2]["checkpoint"] is True


def test_the_task_to_start_has_the_earliest_deadline_then_comes_first(board):
    from proki.programs.code.base import make_variable

    make_variable("time", NOW.timestamp() / 60)  # the config's clock
    intro   = records.add("work.groups", NOW, name="Intro", deadline=DAY(3))
    related = records.add("work.groups", NOW, name="Related work")
    surveys = records.add("work.tasks", NOW, group=related, name="Read the surveys")
    outline = records.add("work.tasks", NOW, group=intro, name="Outline it")
    records.add("work.tasks", NOW, group=intro, name="Draft it")
    assert start() == "Outline it"  # its group's deadline
    records.change("work.tasks", surveys, NOW, deadline=DAY(1))
    assert start() == "Read the surveys"  # its own, earlier
    records.change("work.tasks", surveys, NOW, after=[outline])  # needs "Outline it" first
    assert start() == "Outline it"


def test_a_task_has_a_handle_of_its_own_in_its_group_and_its_ops_go_with_it(board):
    thesis = records.add("work.groups", NOW, name="Thesis")
    read   = records.add("work.tasks", NOW, group=thesis, name="Read the papers")
    notes  = records.add("work.tasks", NOW, group=thesis, name="Take notes", after=[read])
    records.add("work.tasks", NOW, group=thesis, name="Take notes")
    assert [t["key"] for t in board.tasks.current()] == ["read_the_papers", "take_notes", "take_notes_2"]
    assert "- [ ] take_notes: Take notes (after read_the_papers)" in board.outline(board.groups.current()[0])

    board.ops.create(TaskOp(None, group=thesis, op="change", task="take_notes", fields={"estimate": 90}))
    board.ops.create(TaskOp(None, group=thesis, op="remove", task="take_notes_2"))
    with pytest.raises(ValueError):
        board.ops.create(TaskOp(None, group=thesis, op="add", fields={"desc": "no name"}))
    with pytest.raises(ValueError):  # not kept: else no read of the board would work
        board.ops.update(board.ops.read()[0].id, fields={"bogus": 1})
    assert board.ops.read()[0].fields == {"estimate": 90}
    records.remove("work.tasks", notes)
    assert [op.task for op in board.ops.read()] == ["take_notes_2"]  # its op, with it


def test_a_task_weighs_by_your_exprs_its_deadline_its_time_untouched_and_its_progress(board):
    from proki.core.records.field import Field
    from proki.errors import ExprError, VariableError
    from proki.programs.code.base import make_variable
    expr = lambda said: {"from": "expr", "expr": said}

    make_variable("time", NOW.timestamp() / 60)  # the config's clock
    tasks  = board.tasks
    value  = lambda key, id: (Stream.tick(NOW), tasks.get_row(id)[key])[1]  # a cycle each: what's changed, read
    keep   = lambda id, **values: tasks.add_row(tasks.get_row(id) | values)  # as a program sets them
    thesis = records.add("work.groups", NOW, name="Thesis")
    due    = {when: records.add("work.tasks", NOW, group=thesis, name=f"Due {when}", estimate=estimate, deadline=deadline)
              for when, estimate, deadline in [("never", 30, None), ("overdue", 30, DAY(-1)), ("tomorrow", 30, DAY(1)), ("big", 480, DAY(1))]}
    assert [value("pressing", task) for task in due.values()] == [0, 1, 0.5, 1]  # two days' work, a day left: 1
    for task in due.values():
        records.remove("work.tasks", task)

    intro  = records.add("work.tasks", DAY(-14), group=thesis, name="Write the intro", estimate=40)
    paint  = records.add("work.tasks", NOW, group=thesis, name="Paint", estimate=40)
    assert value("untouched", intro) == 1 and value("progress", intro) == 0  # two weeks untouched
    keep(intro, spent=20, last_worked=NOW.timestamp() / 60)
    assert value("untouched", intro) == 0 and value("progress", intro) == 0.5 and value("quick", intro) == 0.6  # 20 of 40 min

    keep(paint, put_offs=1, last_put_off=NOW.timestamp() / 60 - 60)  # as the reminder keeps them
    assert value("put_off", paint) == 1 / 3
    tasks.define(Field("official", srcs=[{"from": "user"}, expr("False")]))   # yours
    tasks.define(Field("score", srcs=[expr("(2 * me.pressing + me.untouched + me.quick - me.put_off) * (1 + me.official / 2)")]))
    keep(paint, official=True)
    assert value("score", paint) == (value("quick", paint) - 1 / 3) * 1.5
    tasks.define(Field("put_off", srcs=[expr("0")]))   # every part is yours to change
    assert value("score", paint) == value("quick", paint) * 1.5
    assert value("name", paint) == "Paint" and value("deadline", paint) is None

    with pytest.raises(ExprError, match="no field nope"):
        tasks.define(Field("bad", srcs=[expr("me.nope + 1")]))
    assert value("score", paint) == value("quick", paint) * 1.5  # the one before, kept
    with pytest.raises(ValueError, match="kept by its code"):
        tasks.define(Field("ready"))

    tasks.define(Field("double", srcs=[expr("me.estimate * 2")]))   # worked out as it's read: nothing kept
    assert value("double", paint) == 80 and "double" not in tasks.get_row(paint)
    records.change("work.tasks", paint, NOW + timedelta(minutes=1), estimate=30)
    assert value("double", paint) == 60
    assert Field("x").type == "any"  # what it is, said: never guessed
    with pytest.raises(ValueError, match="no type 'date'"):
        Field("x", type="date")
    tasks.define(Field("flag", srcs=[{"from": "user"}], type="boolean"))
    with pytest.raises(VariableError, match="work.tasks.flag is of type boolean"):
        keep(paint, flag=3)

    tasks.define(Field("away", srcs=[expr("me.official")]))
    assert start() == "Write the intro"  # Paint's away: not to start now


async def test_an_asked_field_is_asked_as_its_read_and_again_when_the_task_changes(board, monkeypatch):
    from proki.channels import base
    from proki.core.programs import Program
    from proki.core.records.field import Field
    from proki.errors import ExprError

    asked = []
    async def request(channel, data, timeout):  # each channel's worker, as it's asked
        if channel == "jev":
            about, q = data["context"], data["questions"]["q"]
            asked.append((about.splitlines()[0], q["instructions"], timeout))
            if q["type"] == "choice":  return {"q": {"choice": (labels := list(q["criteria"]))[1], "probabilities": {labels[1]: 0.7, labels[0]: 0.3}, "confidence": 0.7}}
            return {"q": {"noul": 0.8 if "embassy" in about else 0.1}}
        text = data["context"]
        asked.append((text.splitlines()[0], text.split("\n\n")[-1], data["schema"]))
        return {"people": 3, "hours": 2}
    monkeypatch.setattr(base, "request", request)

    with pytest.raises(ValueError, match="each source once"):
        Field("x", srcs=[{"from": "user"}, {"from": "user"}])
    with pytest.raises(ValueError, match="expected a mapping or a sequence"):
        Field("energy", srcs=[{"from": "jev", "type": "choice", "question": "How much energy?"}])
    with pytest.raises(ValueError, match="not a JSON Schema"):
        Field("x", srcs=[{"from": "llm", "context": "?", "schema": {"type": "date"}}])

    Program.now = NOW
    tasks = board.tasks
    with pytest.raises(ExprError, match="no field nme"):
        tasks.define(Field("travel", srcs=[{"from": "jev", "type": "noul", "question": "Does “{me.nme}” take going somewhere?"}]))
    tasks.define(Field("travel", "it takes going somewhere", [
        {"from": "user"},
        {"from": "jev", "type": "noul", "question": "Does it take going somewhere?", "expr": "res >= 0.5"},
        {"from": "expr", "expr": "False"}]))
    tasks.define(Field("energy", srcs=[{"from": "jev", "type": "choice", "question": "How much energy does it take?",
                                        "criteria": {"low": "a quiet hour", "high": "all of you"},
                                        "expr": "['low', 'high'][res.index]"}]))
    tasks.define(Field("hours", srcs=[{"from": "llm", "context": "How long, and how many people?", "expr": "res.hours * 60",
                                       "schema": {"type": "object", "properties": {"people": {"type": "number"},
                                                                                   "hours": {"type": "number"}}}}], type="number"))
    visa  = records.add("work.groups", NOW, name="Visa", desc="for the conference")
    forms = records.add("work.tasks", NOW, group=visa, name="Hand in the forms at the embassy")
    read  = lambda: (Stream.tick(Program.now or NOW), tuple(tasks.get_row(forms)[key] for key in ("travel", "energy", "hours")))[1]  # a cycle each
    cache = lambda key, source: tasks.get_row(forms).cache[key][source]["answer"]

    assert read() == (False, None, None)  # asked as it's read: until the answers come, the next source
    await tasks.asker.drain()
    assert {a[1] for a in asked} == {"Does it take going somewhere?", "How much energy does it take?", "How long, and how many people?"}
    assert {a[0] for a in asked} == {"A task: Hand in the forms at the embassy"}  # under what the task is
    assert ("A task: Hand in the forms at the embassy", "Does it take going somewhere?", 2) in asked  # jev's 2 s
    assert read() == (True, "high", 120) and cache("hours", "llm")["people"] == 3  # its answer, kept with it
    read()
    await tasks.asker.drain()
    assert len(asked) == 3  # asked once
    records.change("work.tasks", forms, NOW + timedelta(seconds=30), checkpoint=True)
    read()
    await tasks.asker.drain()
    assert len(asked) == 3  # a change to what it doesn't ask: not again

    Program.now = NOW + timedelta(minutes=1)
    records.change("work.tasks", forms, Program.now, name="Post the forms")  # it changed: asked again
    read()
    await tasks.asker.drain()
    assert len(asked) == 6 and read()[0] is False

    tasks.add_row(tasks.get_row(forms) | {"travel": True})  # set: wins
    Program.now = NOW + timedelta(minutes=3)
    records.change("work.tasks", forms, NOW + timedelta(minutes=2), name="Post the forms at the embassy")
    read()
    await tasks.asker.drain()
    assert read()[0] is True  # what's set wins: jev isn't asked
    tasks.add_row(tasks.get_row(forms) | {"travel": None})  # until you take it back
    read()
    await tasks.asker.drain()
    assert read()[0] is True and cache("travel", "jev") == 0.8  # at the embassy again: yes
    before = len(asked)
    tasks.rerun("hours", "llm", forms)  # asked again: not answered from what the channel kept
    read()
    await tasks.asker.drain()
    assert [a[1] for a in asked[before:]] == ["How long, and how many people?"]


async def test_a_fields_sources_in_order_the_context_every_question_reads_and_who_sets_it(board, monkeypatch):
    from proki.channels import base
    from proki.core.programs import Program
    from proki.core.records.field import Field
    from proki.errors import ExprError

    said = []
    async def request(channel, data, timeout):  # the LLM's worker, as it's asked
        said.append(data["context"])
        return {"value": 90}
    monkeypatch.setattr(base, "request", request)

    Program.now = NOW
    tasks = board.tasks
    tasks.reword("llm", "Task: {me.name}\nDue {me.deadline}\nIn {me.group_name}")
    with pytest.raises(ExprError, match="no field nme"):
        tasks.reword("llm", "{me.nme}")
    tasks.define(Field("minutes", srcs=[{"from": "user"}, {"from": "llm", "context": "How long?"}, {"from": "auto", "initial": 30}],
                       type="number"))  # the LLM answers in its type
    visa  = records.add("work.groups", NOW, name="Visa")
    forms = records.add("work.tasks", NOW, group=visa, name="Forms")

    assert tasks.get_row(forms)["minutes"] == 30  # no answer yet: where a new task starts
    await tasks.asker.drain()
    assert said == ["Task: Forms\nIn Visa\n\nHow long?"]  # no deadline: its line left out
    assert tasks.get_row(forms)["minutes"] == 90 and tasks.get_row(forms).cache["minutes"]["llm"]["answer"] == 90
    tasks.add_row(tasks.get_row(forms) | {"minutes": 15})  # by you
    assert tasks.get_row(forms)["minutes"] == 15 and dict.get(tasks.get_row(forms), "minutes") == 15

    tasks.define(Field("hours", srcs=[{"from": "expr", "expr": "me.minutes / 60"}]))
    tasks.rename("minutes", "length")  # its values, and what reads it, with it
    assert dict.get(tasks.get_row(forms), "length") == 15 and tasks.get_row(forms)["hours"] == 0.25
    assert [f.srcs[0]["expr"] for f in tasks.defined.read() if f.key == "hours"] == ["me.length / 60"]
    with pytest.raises(ValueError, match="came with proki"):
        tasks.rename("spent", "worked")


def test_a_tasks_key_is_its_name_slugified_and_yours_to_change(board):
    now = datetime.now(timezone.utc)
    thesis = records.add("work.groups", now, name="Thesis")
    intro = records.add("work.tasks", now, group=thesis, name="Write the intro")
    again = records.add("work.tasks", now, group=thesis, name="Write the intro")
    board.ops.create(TaskOp(None, group=thesis, op="change", task="write_the_intro", fields={"estimate": 20}, after=["write_the_intro_2"]))
    assert [t["key"] for t in board.tasks.current()] == ["write_the_intro", "write_the_intro_2"]  # one of its group's
    records.change("work.tasks", intro, now, key="intro")
    [op] = board.ops.read()
    assert op.task == "intro" and board.tasks.current()[0]["key"] == "intro"  # the change suggested says it still
    records.change("work.tasks", again, now, key="draft")
    assert board.ops.read()[0].after == ["draft"]
    for bad in ("intro", "Not a key", ""):
        with pytest.raises(ValueError):
            records.change("work.tasks", again, now, key=bad)
